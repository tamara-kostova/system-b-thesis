import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from shared.audit import log_event
from .config import settings
from .providers import get_provider, LLMResponse
from .tools import TOOL_DEFINITIONS, execute_tool

app = FastAPI(title="LLM Gateway", version="0.1.0")

SYSTEM_PROMPT = """You are a research assistant for a health data access platform.
You help researchers find relevant datasets and draft data access applications.

Rules you must never break:
- You cannot return individual patient records or row-level data. You have no tool for that.
- All concept IDs you reference must come from tool results — never invent them.
- If the user provides anything that looks like a national ID number or patient identifier, refuse and log it.
- You only answer questions about the dataset contents using the provided tools.
"""


class ChatRequest(BaseModel):
    messages: list[dict]
    user_id: str = "anonymous"


class ChatResponse(BaseModel):
    reply: str
    provider: str


@app.get("/health")
def health():
    return {"provider": settings.llm_provider, "model": _get_model_name()}


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    provider = get_provider()
    messages = list(req.messages)
    max_tool_rounds = 5

    for _ in range(max_tool_rounds):
        response: LLMResponse = provider.chat(
            messages=messages,
            tools=TOOL_DEFINITIONS,
            system=SYSTEM_PROMPT,
        )

        if not response.tool_calls:
            log_event("llm_chat", actor=req.user_id, resource_id="discovery", details={
                "provider": settings.llm_provider,
                "turns": len(messages),
            })
            return ChatResponse(reply=response.content, provider=settings.llm_provider)

        # Execute each tool call and feed results back
        messages.append({"role": "assistant", "content": response.content or "", "tool_calls": response.tool_calls})
        for tc in response.tool_calls:
            log_event("llm_tool_call", actor=req.user_id, resource_id=tc["name"], details={"input": tc["input"]})
            result = execute_tool(tc["name"], tc["input"])
            messages.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": result,
            })

    raise HTTPException(status_code=500, detail="Tool loop did not converge")


def _get_model_name() -> str:
    try:
        return get_provider().model
    except Exception:
        return "unavailable"

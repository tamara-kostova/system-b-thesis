"""
Phase 5 — LLM Gateway (port 8006).

Mode A (Discovery): public endpoint, tools call Phase 1 API only.
Mode B (In-SPE):    called from inside a JupyterLab SPE, generates
                    Python/SQL scoped to the permit's views.
"""

import re
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

# ── System prompts ─────────────────────────────────────────────────────────────

_MODE_A_SYSTEM = """You are a research assistant for a health data access platform.
You help researchers explore available OMOP health data and draft data access applications.

Rules you must never break:
- You cannot return individual patient records or row-level data. You have no tool for that.
- All concept IDs you reference must come from tool results — never invent or guess them.
- You only answer questions about dataset contents using the provided tools.
- Never suggest ways to bypass access controls or export raw data.
"""

_MODE_B_SYSTEM = """You are a coding assistant running inside a Secure Processing Environment (SPE).
The researcher has a granted data access permit. You help write Python and SQL
analysis code scoped to the permit's database views.

Available views will be listed in the user's message. Only reference those views.
Never generate code that selects all rows without aggregation (no bare SELECT * without GROUP BY or LIMIT).
Never generate code that exports data outside the environment.
Prefer pandas aggregations. Always explain what the code does.
"""

# ── PII guardrail ──────────────────────────────────────────────────────────────

# Common national ID patterns: SSN (US), BSN (NL), NIN (UK), CPR (DK), PPS (IE)
_PII_PATTERNS = [
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),           # SSN
    re.compile(r"\b\d{9}\b"),                          # BSN / generic 9-digit
    re.compile(r"\b[A-Z]{2}\d{6}[A-Z]\b"),            # UK NIN
    re.compile(r"\b\d{6}-\d{4}\b"),                   # CPR (DK)
    re.compile(r"\b\d{7}[A-Z]{1,2}\b"),               # PPS (IE)
]


def _contains_pii(text: str) -> bool:
    return any(p.search(text) for p in _PII_PATTERNS)


def _check_messages_for_pii(messages: list[dict]) -> str | None:
    """Return the offending text if PII is found, else None."""
    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, str) and _contains_pii(content):
            return content
    return None


# ── Request / response models ──────────────────────────────────────────────────

class ChatRequest(BaseModel):
    messages: list[dict]
    user_id: str = "anonymous"


class SPEChatRequest(BaseModel):
    question: str
    permit_id: str
    available_views: list[str]
    user_id: str = "anonymous"


class ChatResponse(BaseModel):
    reply: str
    provider: str


# ── Tool loop ──────────────────────────────────────────────────────────────────

def _run_tool_loop(
    messages: list[dict],
    system: str,
    user_id: str,
    context: str = "discovery",
) -> str:
    from openai import BadRequestError

    provider = get_provider()
    max_rounds = 5

    for _ in range(max_rounds):
        try:
            response: LLMResponse = provider.chat(
                messages=messages,
                tools=TOOL_DEFINITIONS,
                system=system,
            )
        except BadRequestError:
            # Model produced malformed tool call arguments; strip the bad turn
            # and ask again without tools so we at least return something useful.
            clean = [m for m in messages if m.get("role") in ("user", "system")]
            fallback: LLMResponse = provider.chat(messages=clean, system=system)
            return fallback.content or "I was unable to complete the tool call. Please rephrase your question."

        if not response.tool_calls:
            log_event("llm.chat", actor=user_id, resource_id=context, details={
                "provider": settings.llm_provider,
                "turns": len(messages),
            })
            return response.content

        messages.append({
            "role": "assistant",
            "content": response.content or "",
            "tool_calls": response.tool_calls,
        })
        for tc in response.tool_calls:
            log_event("llm.tool_call", actor=user_id, resource_id=tc["name"],
                      details={"input": tc["input"]})
            result = execute_tool(tc["name"], tc["input"])
            messages.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": result,
            })

    raise HTTPException(500, "Tool loop did not converge")


# ── Endpoints ──────────────────────────────────────────────────────────────────

@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    """Mode A — public discovery assistant. Calls Phase 1 tools only."""
    pii = _check_messages_for_pii(req.messages)
    if pii:
        log_event("llm.pii_rejected", actor=req.user_id, resource_id="discovery",
                  details={"snippet": pii[:80]})
        raise HTTPException(400, "Message contains what appears to be a patient identifier. Refused.")

    reply = _run_tool_loop(
        messages=list(req.messages),
        system=_MODE_A_SYSTEM,
        user_id=req.user_id,
    )
    return ChatResponse(reply=reply, provider=settings.llm_provider)


@app.post("/chat/spe", response_model=ChatResponse)
def chat_spe(req: SPEChatRequest):
    """Mode B — in-SPE coding assistant. Generates Python/SQL for permitted views only."""
    pii = _check_messages_for_pii([{"content": req.question}])
    if pii:
        log_event("llm.pii_rejected", actor=req.user_id, resource_id=req.permit_id,
                  details={"snippet": req.question[:80]})
        raise HTTPException(400, "Message contains what appears to be a patient identifier. Refused.")

    views_list = ", ".join(req.available_views) if req.available_views else "none"
    messages = [{
        "role": "user",
        "content": (
            f"Permit: {req.permit_id}\n"
            f"Available views: {views_list}\n\n"
            f"{req.question}"
        ),
    }]

    reply = _run_tool_loop(
        messages=messages,
        system=_MODE_B_SYSTEM,
        user_id=req.user_id,
        context=req.permit_id,
    )
    return ChatResponse(reply=reply, provider=settings.llm_provider)


@app.get("/health")
def health():
    return {"provider": settings.llm_provider, "status": "ok"}

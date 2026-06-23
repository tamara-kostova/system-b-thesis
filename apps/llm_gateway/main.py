"""
Phase 5 — LLM Gateway (port 8006).

Mode A (Discovery): public endpoint, tools call Phase 1 API only.
Mode B (In-SPE):    called from inside a JupyterLab SPE, generates
                    Python/SQL scoped to the permit's views.
"""

import re
import os

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from shared.audit import log_event
from .config import settings
from .providers import get_provider, get_skill_synth_provider, LLMResponse
from .tools import TOOL_DEFINITIONS, execute_tool, _extract_concept_ids
from .skills import (
    ensure_skills_table,
    store_skill,
    find_matching_skills,
    increment_use_count,
    is_spe_failure,
    Skill,
)

app = FastAPI(title="LLM Gateway", version="0.1.0")


@app.on_event("startup")
def _startup() -> None:
    ensure_skills_table()
    provider = get_provider()
    print(
        f"[LLM Gateway] primary={settings.llm_provider} model={provider.model}"
        f" | synth={settings.skill_synth_provider}",
        flush=True,
    )

# ── System prompts ─────────────────────────────────────────────────────────────

_MODE_A_SYSTEM = """You are a research assistant for a health data access platform.
You help researchers explore available OMOP health data and draft data access applications.

IMPORTANT — you have tools. Use them. Do not answer from your own knowledge.

When a user asks about patients, conditions, drugs, or counts: call search_concept first to
find the concept ID, then call estimate_count to get the suppressed patient count.
Always call the tools before replying — never guess or refuse a question you can answer via tools.

The tools return AGGREGATE, SUPPRESSED counts (never individual records). You are allowed and
expected to return these counts to the user. A count under 10 is reported as "<10" automatically.

Rules:
- All concept IDs MUST come from search_concept or get_concept_descendants tool results.
  Never invent or guess a concept ID.
- Never return individual patient records — you have no tool that fetches rows.
- Never suggest ways to bypass access controls or export raw data.
"""

_MODE_B_SYSTEM = """You are a coding assistant running inside a Secure Processing Environment (SPE).
The researcher has a granted data access permit. You help write Python and SQL
analysis code scoped to the permit's database views.

The kernel already has these globals pre-loaded — do NOT redefine or import them:
  - engine         : SQLAlchemy engine connected to the permit's schema
  - pd             : pandas (already imported as pd)
  - available_views: list of view names the permit covers

Always load data using the pre-loaded engine, like this:
  from sqlalchemy import text
  with engine.connect() as conn:
      df = pd.read_sql(text("SELECT ..."), conn)

The user's message lists the EXACT view names and their columns.
These are authoritative — use them verbatim. Do NOT substitute with standard OMOP CDM
table or column names (e.g. do not replace "conditions" with "condition_occurrence",
do not replace "pseudo_id" with "person_id").

Never generate code that selects all rows without aggregation (no bare SELECT * without GROUP BY or LIMIT).
Never generate code that exports data outside the environment.
Always produce complete, runnable code — no placeholder comments like "# load your data here".
"""

# ── PII guardrail ──────────────────────────────────────────────────────────────

# Common national ID patterns: SSN (US), BSN (NL), NIN (UK), CPR (DK), PPS (IE)
_PII_PATTERNS = [
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),                               # SSN (US)
    re.compile(r"(?i)\b(?:bsn|burgerservicenummer)\s*[:#=]?\s*\d{9}\b"), # BSN (NL) with label
    re.compile(r"\b[A-Z]{2}\d{6}[A-Z]\b"),                               # UK NIN
    re.compile(r"\b\d{6}-\d{4}\b"),                                       # CPR (DK)
    re.compile(r"\b\d{7}[A-Z]{1,2}\b"),                                   # PPS (IE)
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
    view_schemas: dict[str, list[str]] = {}
    user_id: str = "anonymous"


class ChatResponse(BaseModel):
    reply: str
    provider: str


# ── Skill synthesis ───────────────────────────────────────────────────────────

_SKILL_SYNTH_SYSTEM = """You are an expert Python and SQL developer for OMOP CDM health data analysis.
Your job is to synthesize a reusable skill function when a smaller LLM cannot perform a task.

The target Jupyter kernel has these globals: engine (SQLAlchemy), pd (pandas), available_views (list[str]).
The function you write will be injected into the smaller LLM's context on its next attempt.

Rules for the generated function:
- Use: with engine.connect() as conn: df = pd.read_sql(text("SELECT ..."), conn)
- Always aggregate — never return raw rows without GROUP BY or LIMIT.
- Parameterize view name(s) and filter values so the function is reusable across permits.
- Must be self-contained and runnable with only engine and pd in scope.

Respond ONLY with a JSON object — no markdown fences, no extra text."""


def _synthesize_skill(
    question: str,
    failed_reply: str,
    schema_info: str,
    user_id: str,
    permit_id: str,
) -> Skill | None:
    """Ask the skill-synthesis LLM to produce a reusable function for this task."""
    import json as _json

    prompt = (
        "A smaller LLM failed to generate analysis code for this health data task.\n\n"
        f"TASK:\n{question}\n\n"
        f"FAILED ATTEMPT:\n{failed_reply}\n\n"
        f"View schema context:\n{schema_info or 'not provided'}\n\n"
        "Synthesize a reusable Python helper function.\n"
        'Return ONLY this JSON (no markdown):\n'
        '{"name": "skill_snake_case", "description": "one sentence", '
        '"trigger_keywords": ["kw1", "kw2"], "code": "def skill_name(engine, pd, ...):\\n    ..."}'
    )

    try:
        synth_provider = get_skill_synth_provider()
        response = synth_provider.chat(
            messages=[{"role": "user", "content": prompt}],
            system=_SKILL_SYNTH_SYSTEM,
        )
        raw = response.content.strip()
        raw = re.sub(r"^```[a-z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw.strip())
        data = _json.loads(raw)
        skill = Skill(
            name=data["name"],
            description=data["description"],
            code=data["code"],
            trigger_keywords=data.get("trigger_keywords", []),
        )
        log_event("llm.skill_synthesized", actor=user_id, resource_id=permit_id,
                  details={"skill": skill.name, "synth_provider": settings.skill_synth_provider})
        return skill
    except Exception as exc:
        log_event("llm.skill_synthesis_failed", actor=user_id, resource_id=permit_id,
                  details={"error": str(exc)[:200]})
        return None


# ── Tool loop ──────────────────────────────────────────────────────────────────

def _run_tool_loop(
    messages: list[dict],
    system: str,
    user_id: str,
    context: str = "discovery",
    tools: list[dict] | None = None,
) -> str:
    from openai import BadRequestError

    provider = get_provider()
    max_rounds = 5
    allowed_concept_ids: set[int] = set()

    for _ in range(max_rounds):
        try:
            response: LLMResponse = provider.chat(
                messages=messages,
                tools=tools,
                system=system,
            )
        except BadRequestError:
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
            result = execute_tool(tc["name"], tc["input"], allowed_concept_ids=allowed_concept_ids)
            if tc["name"] in ("search_concept", "get_concept_descendants"):
                allowed_concept_ids.update(_extract_concept_ids(result))
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
        tools=TOOL_DEFINITIONS,
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
    schema_lines = "\n".join(
        f"  {view}: {', '.join(cols)}"
        for view, cols in req.view_schemas.items()
    )
    context_block = (
        f"Permit: {req.permit_id}\n"
        f"Available views: {views_list}\n"
    )
    if schema_lines:
        context_block += f"View columns:\n{schema_lines}\n"
    messages = [{
        "role": "user",
        "content": context_block + f"\n{req.question}",
    }]

    reply = _run_tool_loop(
        messages=messages,
        system=_MODE_B_SYSTEM,
        user_id=req.user_id,
        context=req.permit_id,
        tools=None,
    )

    if is_spe_failure(reply):
        skill: Skill | None = None
        matching = find_matching_skills(req.question)
        if matching:
            skill = matching[0]
            if skill.skill_id is not None:
                increment_use_count(skill.skill_id)
            log_event("llm.skill_applied", actor=req.user_id, resource_id=req.permit_id,
                      details={"skill": skill.name, "source": "cached"})
        else:
            skill = _synthesize_skill(req.question, reply, schema_lines,
                                      req.user_id, req.permit_id)
            if skill:
                store_skill(skill)

        if skill:
            augmented_system = (
                _MODE_B_SYSTEM
                + "\n\nA helper skill function has been provided for you. "
                "Call it in your solution — do not redefine it:\n"
                f"```python\n{skill.code}\n```"
            )
            reply = _run_tool_loop(
                messages=[{"role": "user", "content": context_block + f"\n{req.question}"}],
                system=augmented_system,
                user_id=req.user_id,
                context=req.permit_id,
                tools=None,
            )

    return ChatResponse(reply=reply, provider=settings.llm_provider)


@app.get("/health")
def health():
    return {"provider": settings.llm_provider, "status": "ok"}

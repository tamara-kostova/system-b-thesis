"""
Skill synthesis store — persists LLM-generated reusable code skills in Postgres.

A skill is a Python function that a capable LLM synthesizes when the primary LLM
cannot handle a request. Skills are stored permanently and retrieved by keyword
matching so future similar queries benefit without another synthesis call.
"""

import re
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import text

from shared.db import engine


@dataclass
class Skill:
    name: str
    description: str
    code: str
    trigger_keywords: list[str] = field(default_factory=list)
    skill_id: int | None = None
    created_at: datetime | None = None
    use_count: int = 0


def ensure_skills_table() -> None:
    """Create llm_skills table if it does not exist. Non-fatal if DB is unavailable."""
    try:
        with engine.begin() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS llm_skills (
                    id          SERIAL PRIMARY KEY,
                    name        VARCHAR(200) NOT NULL UNIQUE,
                    description TEXT         NOT NULL,
                    code        TEXT         NOT NULL,
                    trigger_keywords TEXT[]  NOT NULL DEFAULT '{}',
                    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
                    use_count   INTEGER      NOT NULL DEFAULT 0
                )
            """))
    except Exception:
        pass


def store_skill(skill: Skill) -> Skill:
    """Upsert a skill by name and return it with its database id."""
    try:
        with engine.begin() as conn:
            row = conn.execute(
                text("""
                    INSERT INTO llm_skills (name, description, code, trigger_keywords)
                    VALUES (:name, :description, :code, :keywords)
                    ON CONFLICT (name) DO UPDATE
                        SET description      = EXCLUDED.description,
                            code             = EXCLUDED.code,
                            trigger_keywords = EXCLUDED.trigger_keywords
                    RETURNING id, created_at
                """),
                {
                    "name": skill.name,
                    "description": skill.description,
                    "code": skill.code,
                    "keywords": skill.trigger_keywords,
                },
            ).fetchone()
            if row:
                skill.skill_id = row.id
                skill.created_at = row.created_at
    except Exception:
        pass
    return skill


def find_matching_skills(query: str, limit: int = 3) -> list[Skill]:
    """Return up to `limit` skills ranked by keyword overlap with the query."""
    words = set(re.findall(r"\w+", query.lower()))
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text("""
                    SELECT id, name, description, code, trigger_keywords,
                           created_at, use_count
                    FROM llm_skills
                    ORDER BY use_count DESC
                """)
            ).fetchall()
    except Exception:
        return []

    scored: list[tuple[int, object]] = []
    for row in rows:
        kws = {k.lower() for k in (row.trigger_keywords or [])}
        overlap = len(kws & words)
        if overlap > 0:
            scored.append((overlap, row))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [
        Skill(
            skill_id=row.id,
            name=row.name,
            description=row.description,
            code=row.code,
            trigger_keywords=list(row.trigger_keywords or []),
            created_at=row.created_at,
            use_count=row.use_count,
        )
        for _, row in scored[:limit]
    ]


def increment_use_count(skill_id: int) -> None:
    try:
        with engine.begin() as conn:
            conn.execute(
                text("UPDATE llm_skills SET use_count = use_count + 1 WHERE id = :id"),
                {"id": skill_id},
            )
    except Exception:
        pass


# ── Failure detection ──────────────────────────────────────────────────────────

_FAILURE_PHRASES = [
    "i don't know", "i dont know",
    "i'm not sure how", "im not sure how",
    "i cannot generate", "i can't generate",
    "i cannot write", "i can't write",
    "i'm unable to", "im unable to",
    "i do not have enough", "i don't have enough",
    "not sure how to",
    "i'm afraid i can't", "i'm afraid i cannot",
    "unfortunately, i cannot", "unfortunately i cannot",
    "unfortunately, i can't", "unfortunately i can't",
]

_INCOMPLETE_CODE_MARKERS = [
    "# your code here",
    "# todo:",
    "# add your",
    "# fill in",
    "# implement this",
    "raise notimplementederror",
    "# ... (rest of",
    "# complete this",
]


def _extract_code_blocks(text: str) -> list[str]:
    """Return the content of all ```python ... ``` fences in the reply."""
    return re.findall(r"```python\s*(.*?)```", text, re.DOTALL)


def _has_syntax_error(reply: str) -> bool:
    """Return True if any fenced code block in the reply fails to compile."""
    for block in _extract_code_blocks(reply):
        try:
            compile(block, "<llm_output>", "exec")
        except SyntaxError:
            return True
    return False


def is_spe_failure(reply: str) -> bool:
    """Return True if the reply signals the LLM could not generate usable code."""
    stripped = reply.strip()
    if len(stripped) < 30:
        return True
    low = stripped.lower()
    if any(phrase in low for phrase in _FAILURE_PHRASES):
        return True
    if any(marker in low for marker in _INCOMPLETE_CODE_MARKERS):
        return True
    if _has_syntax_error(reply):
        return True
    return False

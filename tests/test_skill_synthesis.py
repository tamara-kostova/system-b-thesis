"""
Phase 5 — Skill synthesis tests.

Verifies the fallback loop that escalates to a bigger LLM when the primary
LLM cannot generate usable code, and that synthesized skills are cached and
reused on subsequent similar requests.

All LLM calls and DB operations are mocked — no live services required.
"""

import json
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from apps.llm_gateway.main import app
from apps.llm_gateway.skills import is_spe_failure, Skill

client = TestClient(app)


# ── is_spe_failure — pure unit tests (no mocks needed) ───────────────────────

def test_failure_detected_on_explicit_refusal():
    assert is_spe_failure("I'm unable to generate this type of analysis.") is True


def test_failure_detected_on_uncertainty():
    assert is_spe_failure("I don't know how to write that SQL for you.") is True


def test_failure_detected_on_placeholder_code():
    assert is_spe_failure("def analyze():\n    # your code here\n    pass") is True


def test_failure_detected_on_notimplementederror():
    assert is_spe_failure("def analyze():\n    raise NotImplementedError") is True


def test_failure_detected_on_very_short_reply():
    assert is_spe_failure("No idea.") is True


def test_no_false_positive_on_valid_code():
    code = (
        "from sqlalchemy import text\n"
        "with engine.connect() as conn:\n"
        "    df = pd.read_sql(\n"
        "        text('SELECT condition_col, COUNT(*) AS n FROM conditions GROUP BY condition_col'),\n"
        "        conn,\n"
        "    )\n"
        "df.head()"
    )
    assert is_spe_failure(code) is False


def test_no_false_positive_on_short_complete_answer():
    # Valid one-liner should not trigger synthesis
    line = "df = pd.read_sql(text('SELECT COUNT(*) FROM conditions'), conn)"
    assert is_spe_failure(line) is False


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_primary_mock(first_reply: str, second_reply: str = "retry code"):
    """Primary LLM that fails on the first call and succeeds on the retry."""
    mock = MagicMock()
    mock.chat.side_effect = [
        MagicMock(content=first_reply, tool_calls=[]),
        MagicMock(content=second_reply, tool_calls=[]),
    ]
    return mock


def _make_synth_mock(skill_name: str = "count_by_year") -> MagicMock:
    """Synthesis LLM that returns a valid skill JSON."""
    payload = json.dumps({
        "name": skill_name,
        "description": "Count records grouped by year.",
        "trigger_keywords": ["count", "year", "conditions"],
        "code": f"def {skill_name}(engine, pd, view_name):\n    pass",
    })
    mock = MagicMock()
    mock.chat.return_value = MagicMock(content=payload, tool_calls=[])
    return mock


# ── Skill synthesis loop ──────────────────────────────────────────────────────

def test_synthesis_triggered_when_primary_fails():
    """Primary LLM failure → big LLM synthesizes a skill → retry is returned."""
    primary = _make_primary_mock(
        "I'm unable to generate this code.",
        "with engine.connect() as conn: df = pd.read_sql(..., conn)",
    )
    synth = _make_synth_mock()

    with patch("apps.llm_gateway.main.get_provider", return_value=primary), \
         patch("apps.llm_gateway.main.get_skill_synth_provider", return_value=synth), \
         patch("apps.llm_gateway.main.find_matching_skills", return_value=[]), \
         patch("apps.llm_gateway.main.store_skill") as mock_store:
        resp = client.post("/chat/spe", json={
            "question": "Count conditions by year",
            "permit_id": "p-001",
            "available_views": ["conditions"],
        })

    assert resp.status_code == 200
    assert primary.chat.call_count == 2          # failure attempt + retry
    synth.chat.assert_called_once()              # synthesis called once
    mock_store.assert_called_once()              # new skill persisted
    assert resp.json()["reply"] != "I'm unable to generate this code."


def test_cached_skill_reused_without_synthesis():
    """Cached skill is injected into the retry — synthesis LLM is never called."""
    primary = _make_primary_mock("I don't know how to do that.", "good retry code")
    cached = Skill(
        skill_id=42,
        name="existing_skill",
        description="Already stored.",
        code="def existing_skill(engine, pd, view_name): pass",
        trigger_keywords=["conditions", "count"],
    )
    synth = _make_synth_mock()

    with patch("apps.llm_gateway.main.get_provider", return_value=primary), \
         patch("apps.llm_gateway.main.get_skill_synth_provider", return_value=synth), \
         patch("apps.llm_gateway.main.find_matching_skills", return_value=[cached]), \
         patch("apps.llm_gateway.main.increment_use_count") as mock_inc, \
         patch("apps.llm_gateway.main.store_skill") as mock_store:
        resp = client.post("/chat/spe", json={
            "question": "Count conditions by year",
            "permit_id": "p-001",
            "available_views": ["conditions"],
        })

    assert resp.status_code == 200
    synth.chat.assert_not_called()               # synthesis skipped — cache hit
    mock_store.assert_not_called()               # nothing new to store
    mock_inc.assert_called_once_with(42)         # use_count incremented
    assert primary.chat.call_count == 2          # retry still happened


def test_synthesis_failure_returns_original_reply():
    """When synthesis fails (bad JSON from big LLM), endpoint still returns 200."""
    primary = MagicMock()
    primary.chat.return_value = MagicMock(content="I'm unable to write this.", tool_calls=[])

    bad_synth = MagicMock()
    bad_synth.chat.return_value = MagicMock(content="not valid json {{{", tool_calls=[])

    with patch("apps.llm_gateway.main.get_provider", return_value=primary), \
         patch("apps.llm_gateway.main.get_skill_synth_provider", return_value=bad_synth), \
         patch("apps.llm_gateway.main.find_matching_skills", return_value=[]), \
         patch("apps.llm_gateway.main.store_skill"):
        resp = client.post("/chat/spe", json={
            "question": "Plot measurements over time",
            "permit_id": "p-001",
            "available_views": ["measurements"],
        })

    assert resp.status_code == 200                          # graceful degradation — never 500
    assert resp.json()["reply"] == "I'm unable to write this."


def test_no_synthesis_when_primary_succeeds():
    """When the primary LLM returns valid code, skill lookup is never triggered."""
    valid_code = (
        "from sqlalchemy import text\n"
        "with engine.connect() as conn:\n"
        "    df = pd.read_sql(text('SELECT yr, COUNT(*) FROM conditions GROUP BY yr'), conn)"
    )
    primary = MagicMock()
    primary.chat.return_value = MagicMock(content=valid_code, tool_calls=[])
    synth = _make_synth_mock()

    with patch("apps.llm_gateway.main.get_provider", return_value=primary), \
         patch("apps.llm_gateway.main.get_skill_synth_provider", return_value=synth), \
         patch("apps.llm_gateway.main.find_matching_skills") as mock_find:
        resp = client.post("/chat/spe", json={
            "question": "Aggregate conditions by year",
            "permit_id": "p-001",
            "available_views": ["conditions"],
        })

    assert resp.status_code == 200
    mock_find.assert_not_called()      # skill lookup never reached
    synth.chat.assert_not_called()     # synthesis never reached
    assert primary.chat.call_count == 1


def test_skill_code_injected_into_retry_system_prompt():
    """The synthesized skill's code appears verbatim in the second LLM call's system prompt."""
    skill_code = "def my_skill(engine, pd, view_name):\n    return pd.DataFrame()"
    primary = _make_primary_mock("I'm unable to generate this code.", "using skill now")

    synth = MagicMock()
    synth.chat.return_value = MagicMock(
        content=json.dumps({
            "name": "my_skill",
            "description": "test skill",
            "trigger_keywords": ["test"],
            "code": skill_code,
        }),
        tool_calls=[],
    )

    captured_system = {}

    original_chat = primary.chat.side_effect

    def capturing_chat(messages, tools=None, system=None):
        # Record the system prompt used on the second call
        if primary.chat.call_count == 2:
            captured_system["value"] = system
        resp = MagicMock(tool_calls=[])
        resp.content = original_chat[primary.chat.call_count - 1].content
        return resp

    primary.chat.side_effect = None
    primary.chat = MagicMock(side_effect=[
        MagicMock(content="I'm unable to generate this code.", tool_calls=[]),
        MagicMock(content="using skill now", tool_calls=[]),
    ])

    # Intercept the second call to inspect the system prompt
    original_side_effect = list(primary.chat.side_effect)

    def intercepting_chat(*_, system=None, **__):
        call_num = intercepting_chat.count
        intercepting_chat.count += 1
        if call_num == 1:
            captured_system["value"] = system
        return original_side_effect[call_num]

    intercepting_chat.count = 0
    primary.chat.side_effect = intercepting_chat

    with patch("apps.llm_gateway.main.get_provider", return_value=primary), \
         patch("apps.llm_gateway.main.get_skill_synth_provider", return_value=synth), \
         patch("apps.llm_gateway.main.find_matching_skills", return_value=[]), \
         patch("apps.llm_gateway.main.store_skill"):
        resp = client.post("/chat/spe", json={
            "question": "Run my test query",
            "permit_id": "p-001",
            "available_views": ["conditions"],
        })

    assert resp.status_code == 200
    assert skill_code in captured_system.get("value", ""), \
        "Skill code must appear in the retry system prompt"

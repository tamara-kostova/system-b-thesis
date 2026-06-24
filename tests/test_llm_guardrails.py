"""
Phase 5 — LLM guardrail red-team tests.

These tests verify guardrails without hitting a live LLM.
Every attack attempt is documented with the control that blocks it.
See also: redteam/adversarial_prompts.md
"""

import json
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from apps.llm_gateway.main import _contains_pii, app
from apps.llm_gateway.tools import TOOL_DEFINITIONS, _extract_concept_ids, execute_tool

client = TestClient(app)


# ── PII guardrail ─────────────────────────────────────────────────────────────


def test_pii_us_ssn_rejected():
    """Attack: embed a US Social Security Number in the query."""
    resp = client.post(
        "/chat",
        json={
            "messages": [{"role": "user", "content": "Find records for patient 123-45-6789"}],
            "user_id": "attacker",
        },
    )
    assert resp.status_code == 400
    assert "identifier" in resp.json()["detail"].lower()


def test_pii_uk_nin_rejected():
    """Attack: embed a UK National Insurance Number."""
    resp = client.post(
        "/chat",
        json={
            "messages": [{"role": "user", "content": "Patient NI number is AB123456C"}],
            "user_id": "attacker",
        },
    )
    assert resp.status_code == 400


def test_pii_labeled_bsn_rejected():
    """Attack: embed a Dutch BSN (Burgerservicenummer) with its label."""
    resp = client.post(
        "/chat",
        json={
            "messages": [{"role": "user", "content": "BSN: 123456789"}],
            "user_id": "attacker",
        },
    )
    assert resp.status_code == 400


def test_bare_nine_digit_not_rejected():
    """Bare 9-digit numbers (e.g. OMOP concept IDs) must NOT be blocked."""
    mock_response = MagicMock()
    mock_response.content = "Here is the count."
    mock_response.tool_calls = []

    with patch("apps.llm_gateway.main.get_provider") as mock_get:
        mock_get.return_value.chat.return_value = mock_response
        resp = client.post(
            "/chat",
            json={
                "messages": [{"role": "user", "content": "Look up person 123456789"}],
                "user_id": "researcher",
            },
        )
    assert resp.status_code == 200


def test_clean_query_not_rejected():
    """Legitimate query with no PII should not be blocked by the PII guardrail."""
    # We mock the provider so we don't need a live LLM
    mock_response = MagicMock()
    mock_response.content = "I can help with that."
    mock_response.tool_calls = []

    with patch("apps.llm_gateway.main.get_provider") as mock_get:
        mock_get.return_value.chat.return_value = mock_response
        resp = client.post(
            "/chat",
            json={
                "messages": [{"role": "user", "content": "How many patients have diabetes?"}],
                "user_id": "researcher",
            },
        )
    assert resp.status_code == 200


def test_pii_detection_function():
    assert _contains_pii("SSN is 123-45-6789") is True
    assert _contains_pii("patient NI AB123456C has") is True
    assert _contains_pii("BSN: 123456789") is True
    assert _contains_pii("burgerservicenummer 987654321") is True
    assert _contains_pii("how many patients have diabetes?") is False
    assert _contains_pii("concept_id 201826") is False
    assert _contains_pii("Look up person 123456789") is False  # bare 9-digit allowed


# ── Tool guardrails — no row-level data tool ──────────────────────────────────


def test_no_row_level_tool_exists():
    """The LLM has no tool that returns individual rows. Verify by inspection."""
    row_keywords = {"select_patients", "get_rows", "fetch_records", "query_data", "run_sql"}
    tool_names = {t["name"] for t in TOOL_DEFINITIONS}
    assert tool_names.isdisjoint(
        row_keywords
    ), f"Row-level tool found in TOOL_DEFINITIONS: {tool_names & row_keywords}"


def test_tools_only_return_aggregates():
    """estimate_count returns a suppressed count string, never a list of patients."""
    with patch("apps.llm_gateway.tools._client") as mock_client:
        mock_client.get.return_value.text = '{"count": "<10"}'
        mock_client.get.return_value.raise_for_status = MagicMock()
        result = execute_tool("estimate_count", {"concept_id": 201826})
    # Result must be a string, not a list
    assert isinstance(result, str)
    # Must not look like a list of patient records
    try:
        parsed = json.loads(result)
        assert not isinstance(
            parsed, list
        ), "estimate_count returned a list — potential row-level leak"
    except json.JSONDecodeError:
        pass  # plain string is fine


# ── Concept ID guardrail ───────────────────────────────────────────────────────


def test_lookup_table_schema_returns_columns_not_data():
    """lookup_table_schema returns column metadata only, never row data."""
    result = execute_tool("lookup_table_schema", {"table_name": "condition_occurrence"})
    parsed = json.loads(result)
    assert "columns" in parsed
    assert "table" in parsed
    # Must be metadata (dicts with 'column' and 'type'), not actual data rows
    for col in parsed["columns"]:
        assert "column" in col
        assert "type" in col


def test_lookup_unknown_table_returns_error_not_data():
    """Unknown table name returns an error, not fabricated data."""
    result = execute_tool("lookup_table_schema", {"table_name": "patients_raw"})
    parsed = json.loads(result)
    assert "error" in parsed
    assert "available" in parsed


# ── Mode B SPE endpoint ────────────────────────────────────────────────────────


def test_spe_pii_rejected():
    """PII in an in-SPE question is blocked by the same guardrail."""
    resp = client.post(
        "/chat/spe",
        json={
            "question": "Analyse patient 123-45-6789",
            "permit_id": "test-permit",
            "available_views": ["conditions"],
        },
    )
    assert resp.status_code == 400


def test_spe_clean_question_passes_guardrail():
    """Legitimate SPE question passes PII check (LLM mocked)."""
    mock_response = MagicMock()
    mock_response.content = "Here is the code: ..."
    mock_response.tool_calls = []

    with patch("apps.llm_gateway.main.get_provider") as mock_get:
        mock_get.return_value.chat.return_value = mock_response
        resp = client.post(
            "/chat/spe",
            json={
                "question": "Plot condition counts by year",
                "permit_id": "test-permit",
                "available_views": ["conditions", "measurements"],
            },
        )
    assert resp.status_code == 200
    assert "provider" in resp.json()


# ── Concept ID session allowlist ───────────────────────────────────────────────


def test_estimate_count_without_prior_search_is_blocked():
    """estimate_count with an arbitrary concept ID is blocked when allowlist is non-empty."""
    arbitrary_concept_id = 999999
    allowed: set[int] = {201826}  # some other ID was searched
    result = execute_tool(
        "estimate_count", {"concept_id": arbitrary_concept_id}, allowed_concept_ids=allowed
    )
    parsed = json.loads(result)
    assert (
        "error" in parsed or "not in" in json.dumps(parsed).lower()
    ), "Expected error when concept ID is not in session allowlist"


def test_estimate_count_with_allowlisted_id_is_permitted():
    """estimate_count succeeds when the concept ID is in the session allowlist."""
    with patch("apps.llm_gateway.tools._client") as mock_client:
        mock_client.get.return_value.text = '{"count": "42"}'
        mock_client.get.return_value.raise_for_status = MagicMock()
        allowed: set[int] = {201826}
        result = execute_tool("estimate_count", {"concept_id": 201826}, allowed_concept_ids=allowed)
    assert "42" in result or "count" in result.lower()


def test_extract_concept_ids_from_search_result():
    """_extract_concept_ids pulls concept_id integers from a search result JSON."""
    payload = json.dumps(
        [
            {"concept_id": 201826, "concept_name": "Type 2 diabetes"},
            {"concept_id": 4193704, "concept_name": "Diabetes mellitus"},
        ]
    )
    ids = _extract_concept_ids(payload)
    assert ids == {201826, 4193704}


def test_extract_concept_ids_handles_bad_json():
    """_extract_concept_ids returns an empty set on malformed JSON."""
    ids = _extract_concept_ids("not json at all {{{")
    assert ids == set()

"""
Tools available to the LLM. All concept IDs come from these functions — the LLM
can never invent them. All counts go through small-cell suppression.
"""

import json
import httpx
from .config import settings

_client = httpx.Client(base_url=settings.discovery_api_url, timeout=10.0)

# OMOP CDM v5.4 column metadata — returned by lookup_table_schema without a DB call.
_OMOP_SCHEMA: dict[str, list[dict]] = {
    "person": [
        {"column": "person_id", "type": "integer"},
        {"column": "gender_concept_id", "type": "integer"},
        {"column": "year_of_birth", "type": "integer"},
        {"column": "race_concept_id", "type": "integer"},
        {"column": "ethnicity_concept_id", "type": "integer"},
    ],
    "condition_occurrence": [
        {"column": "condition_occurrence_id", "type": "integer"},
        {"column": "person_id", "type": "integer"},
        {"column": "condition_concept_id", "type": "integer"},
        {"column": "condition_start_date", "type": "date"},
        {"column": "condition_end_date", "type": "date"},
        {"column": "visit_occurrence_id", "type": "integer"},
    ],
    "drug_exposure": [
        {"column": "drug_exposure_id", "type": "integer"},
        {"column": "person_id", "type": "integer"},
        {"column": "drug_concept_id", "type": "integer"},
        {"column": "drug_exposure_start_date", "type": "date"},
        {"column": "drug_exposure_end_date", "type": "date"},
        {"column": "quantity", "type": "numeric"},
    ],
    "measurement": [
        {"column": "measurement_id", "type": "integer"},
        {"column": "person_id", "type": "integer"},
        {"column": "measurement_concept_id", "type": "integer"},
        {"column": "measurement_date", "type": "date"},
        {"column": "value_as_number", "type": "numeric"},
        {"column": "unit_concept_id", "type": "integer"},
    ],
    "visit_occurrence": [
        {"column": "visit_occurrence_id", "type": "integer"},
        {"column": "person_id", "type": "integer"},
        {"column": "visit_concept_id", "type": "integer"},
        {"column": "visit_start_date", "type": "date"},
        {"column": "visit_end_date", "type": "date"},
    ],
}


# Tool definitions (Anthropic-style; providers.py converts to OpenAI format as needed)
TOOL_DEFINITIONS = [
    {
        "name": "search_concept",
        "description": "Search for OMOP concepts by name or keyword. Returns concept_id, concept_name, vocabulary, domain.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search term, e.g. 'type 2 diabetes'"},
                "domain": {"type": "string", "description": "Optional domain filter, e.g. 'Drug', 'Condition'"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_concept_descendants",
        "description": "Return all descendant concept IDs for a given concept (uses CONCEPT_ANCESTOR). Use before building cohorts.",
        "input_schema": {
            "type": "object",
            "properties": {
                "concept_id": {"type": "integer"},
            },
            "required": ["concept_id"],
        },
    },
    {
        "name": "estimate_count",
        "description": "Return the suppressed patient count matching a concept. Counts < 10 return '<10'.",
        "input_schema": {
            "type": "object",
            "properties": {
                "concept_id": {"type": "integer"},
            },
            "required": ["concept_id"],
        },
    },
    {
        "name": "lookup_table_schema",
        "description": "Return column names and types for an OMOP CDM table. Use before writing analysis code.",
        "input_schema": {
            "type": "object",
            "properties": {
                "table_name": {"type": "string", "description": "e.g. 'condition_occurrence'"},
            },
            "required": ["table_name"],
        },
    },
    {
        "name": "draft_application",
        "description": "Draft a data access application based on the user's stated research purpose and target concepts.",
        "input_schema": {
            "type": "object",
            "properties": {
                "purpose": {"type": "string"},
                "concept_ids": {"type": "array", "items": {"type": "integer"}},
                "domains": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["purpose", "concept_ids"],
        },
    },
]


def _require_int_concept_id(input: dict) -> int | None:
    """Return the concept_id as int, or None if invalid (caller should return error string)."""
    try:
        return int(input["concept_id"])
    except (KeyError, ValueError, TypeError):
        return None


def execute_tool(name: str, input: dict) -> str:
    match name:
        case "search_concept":
            r = _client.get("/concepts/search", params=input)
            r.raise_for_status()
            return r.text
        case "get_concept_descendants":
            cid = _require_int_concept_id(input)
            if cid is None:
                return json.dumps({"error": "concept_id must be an integer. Call search_concept first to find the correct concept_id."})
            r = _client.get(f"/concepts/{cid}/descendants")
            r.raise_for_status()
            return r.text
        case "estimate_count":
            cid = _require_int_concept_id(input)
            if cid is None:
                return json.dumps({"error": "concept_id must be an integer. Call search_concept first to find the correct concept_id."})
            r = _client.get(f"/counts/{cid}")
            r.raise_for_status()
            return r.text
        case "lookup_table_schema":
            table = input["table_name"].lower()
            if table not in _OMOP_SCHEMA:
                available = list(_OMOP_SCHEMA.keys())
                return json.dumps({"error": f"Unknown table '{table}'", "available": available})
            return json.dumps({"table": table, "columns": _OMOP_SCHEMA[table]})
        case "draft_application":
            return _draft_application(**input)
        case _:
            return f"Unknown tool: {name}"


def _draft_application(purpose: str, concept_ids: list[int], domains: list[str] | None = None) -> str:
    lines = [
        f"Purpose: {purpose}",
        f"Requested concept IDs: {concept_ids}",
    ]
    if domains:
        lines.append(f"Domains: {domains}")
    lines += [
        "Format: anonymized",
        "Please review and adjust before submitting.",
    ]
    return "\n".join(lines)

"""
Tools available to the LLM. All concept IDs come from these functions — the LLM
can never invent them. All counts go through small-cell suppression.
"""

import httpx
from .config import settings

_client = httpx.Client(base_url=settings.discovery_api_url, timeout=10.0)


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


def execute_tool(name: str, input: dict) -> str:
    match name:
        case "search_concept":
            r = _client.get("/concepts/search", params=input)
            r.raise_for_status()
            return r.text
        case "get_concept_descendants":
            r = _client.get(f"/concepts/{input['concept_id']}/descendants")
            r.raise_for_status()
            return r.text
        case "estimate_count":
            r = _client.get(f"/counts/{input['concept_id']}")
            r.raise_for_status()
            return r.text
        case "lookup_table_schema":
            # Phase 1 endpoint — returns column metadata
            r = _client.get(f"/schema/{input['table_name']}")
            r.raise_for_status()
            return r.text
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

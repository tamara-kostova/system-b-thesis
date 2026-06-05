# System B — Architecture

## Overview

System B implements the EHDS Chapter IV secondary-use workflow as five composable FastAPI microservices, each corresponding to a phase of the permit lifecycle. All services share a Postgres database, a common audit log, and Pydantic models defined in `/shared/`.

## Service Map

| Service | Port | Role |
|---------|------|------|
| Discovery API | 8003 | Public read-only catalogue and concept search |
| Permit Service | 8002 | Permit lifecycle management (EHDS Arts. 67–68) |
| SPE Provisioner | 8004 | Docker container launch and teardown |
| Output Airlock | 8005 | Disclosure control gateway |
| LLM Gateway | 8006 | Natural-language interface (Modes A and B) |

## Data Flow

```
Researcher
  │
  ├─[1]─► Discovery API (public)
  │          Concept search, suppressed counts
  │          ↑ called by LLM Gateway (Mode A)
  │
  ├─[2]─► Permit Service
  │          Application → review → grant
  │          Stores permits in Postgres (permits schema)
  │
  │       [On grant]
  │          │
  ├─[3]─►  SPE Provisioner
  │          Creates permit-scoped Postgres views
  │          Launches JupyterLab container
  │          Internal Docker network (no egress)
  │
  │       [Researcher analyses data in SPE]
  │          │
  ├─[4]─►  Output Airlock
  │          Automated disclosure checks
  │          Human reviewer queue
  │          Approved files available for download
  │
  └─[5]─►  LLM Gateway
             Mode A: calls Discovery API tools only
             Mode B: coding assistant inside SPE
```

## Shared Components

### `shared/audit.py`
`log_event(event_type, actor, resource_id, details)` — the single audit function. Every state transition, container event, notebook save, airlock decision, and LLM tool call writes through this function. All services import it directly.

### `shared/models.py`
Pydantic `Permit` model with `DataScope` sub-model. This is the canonical schema — frozen early and shared across all services.

### `shared/db.py`
SQLAlchemy engine and `get_db()` FastAPI dependency. Single connection pool, single DATABASE_URL.

## Key Design Decisions

### Database-level access control
On permit grant, the SPE Provisioner creates a Postgres schema `permit_<id>` containing views filtered to the permit's concepts, time window, and patient subset. A dedicated user `spe_<id>` has SELECT on this schema only, with `search_path` set so queries need no schema prefix. This enforces data minimisation in the database layer — a bug in application code cannot expose out-of-scope data.

### Single-function disclosure controls
`suppress()` in `apps/discovery_api/suppression.py` is the only implementation of small-cell suppression. All count-returning endpoints import and call it. It is never duplicated. Similarly, `run_checks()` in `apps/output_airlock/checks.py` is the only disclosure check entry point.

### Tool-based LLM architecture
The LLM Gateway uses a tool-calling loop: the LLM can only call approved functions (`search_concept`, `estimate_count`, etc.) which call Phase 1 API endpoints. The LLM has no tool that returns row-level data. Concept IDs are only valid when returned by `search_concept` — the LLM cannot fabricate them and have them execute against real data.

### Docker network isolation
Each SPE container connects to an `--internal` Docker network. Internal networks have no default route, preventing outbound internet requests from the SPE. The Postgres container is connected to this network via an alias so the SPE can reach the database.

## Postgres Schema Layout

```
postgres (port 5433)
├── cdm schema          — OMOP CDM tables (person, condition_occurrence, …)
├── permits schema      — Permit lifecycle (PermitDB)
├── airlock schema      — Airlock submissions (AirlockSubmissionDB)
└── permit_<id> schema  — Per-permit views (created on grant, dropped on expiry)
    ├── conditions      view (filtered condition_occurrence)
    ├── drugs           view (filtered drug_exposure)
    └── measurements    view (filtered measurement)
```

## LLM Provider Abstraction

```
LLMProvider (ABC)
├── AnthropicProvider   — Anthropic SDK, native tool-use format
├── OpenAIProvider      — OpenAI SDK
└── OllamaProvider      — OpenAI SDK pointed at localhost:11434
```

All three providers expose the same `chat(messages, tools, system)` interface. Tool definitions are written in Anthropic format; `_to_openai_tool()` converts them for OpenAI/Ollama. Switching providers requires only a change to `LLM_PROVIDER` in `.env`.

## Environment Variables

| Variable | Used by | Purpose |
|----------|---------|---------|
| `DATABASE_URL` | All services | Postgres connection string |
| `LLM_PROVIDER` | LLM Gateway | `anthropic` / `openai` / `ollama` |
| `ANTHROPIC_API_KEY` | LLM Gateway | Anthropic API key |
| `OLLAMA_MODEL` | LLM Gateway | Ollama model name |
| `REVIEWER_PASSWORD` | Permit Service, Airlock | Reviewer login |
| `PROJECTION_SALT` | SPE Provisioner | HMAC salt for pseudo-IDs |
| `POSTGRES_CONTAINER_NAME` | SPE Provisioner | Docker container name for Postgres |
| `SPE_IMAGE` | SPE Provisioner | Docker image for JupyterLab SPE |

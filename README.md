# System B — SecureHealth Data Access Platform

A reference implementation of an EHDS (European Health Data Space) Chapter IV-compliant platform for secondary use of health data, with an LLM-assisted prompt interface validated against the OMOP CDM v5.4 standard.

## Architecture

Five services built in phases:

| Phase | Service | Port | Description |
|-------|---------|------|-------------|
| 1 | `discovery_api` | 8003 | Public catalogue and concept search (FastAPI) |
| 2 | `permit_service` | 8002 | Data access permit workflow — EHDS Articles 67–68 (FastAPI + Streamlit) |
| 3 | `spe_provisioner` | 8004 | Isolated JupyterLab environments with no internet egress (Docker) |
| 4 | `output_airlock` | 8005 | Disclosure checking before results leave the SPE (FastAPI + Streamlit) |
| 5 | `llm_gateway` | 8006 | LLM-assisted research assistant and in-SPE copilot (FastAPI) |

## Stack

- Python 3.11+, FastAPI, Streamlit, SQLAlchemy, Pydantic
- PostgreSQL 16, Docker
- LLM: Anthropic Claude / OpenAI / Ollama (configured via `LLM_PROVIDER` env var)
- Data: synthetic OMOP CDM v5.4 (Eunomia/Synthea)

## Setup

```bash
git clone <repo>
cd system-b-thesis

python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env   # edit credentials (see Environment Variables below)
```

## Running the stack

```bash
# Start Postgres
make db

# Start all APIs and UIs
make start
```

After `make start` you'll see:

```
  APIs                           Docs
  ─────────────────────────────────────────────────────
  Discovery API   http://localhost:8003   /docs
  Permit Service  http://localhost:8002   /docs
  SPE Provisioner http://localhost:8004   /docs
  Output Airlock  http://localhost:8005   /docs
  LLM Gateway     http://localhost:8006   /docs

  UIs
  ─────────────────────────────────────────────────────
  Applicant       http://localhost:8501
  Permit Reviewer http://localhost:8502
  Airlock Review  http://localhost:8503
  LLM Assistant   http://localhost:8504
```

```bash
make status    # check which services are running
make logs      # tail all logs (Ctrl+C to stop)
make stop      # stop everything
make restart   # stop then start
make test      # run the test suite
```

Logs for each service are written to `logs/<service>.log`.

## Environment Variables

Copy `.env.example` to `.env` and fill in:

```
# Required
REVIEWER_PASSWORD=<choose a password for the reviewer UI>
PROJECTION_SALT=<random string used to pseudonymise person_id>

# LLM provider — pick one
LLM_PROVIDER=ollama          # local, no API key needed (default)
# LLM_PROVIDER=anthropic
# ANTHROPIC_API_KEY=sk-ant-...
# LLM_PROVIDER=openai
# OPENAI_API_KEY=sk-...

# Database (defaults work with docker compose)
# DATABASE_URL=postgresql://omop_admin:changeme@localhost:5433/omop
```

## Local LLM (no API key)

```bash
docker compose --profile ollama up -d ollama
ollama pull llama3.2
# set LLM_PROVIDER=ollama in .env (this is the default)
```

## Data

Uses synthetic patient data only — no real health records. Load OMOP data with:

```bash
python sql/synthea_to_omop.py --csv synthea/output/csv/
```

See `sql/` for the full OMOP CDM schema and ETL scripts (Phase 0).

## Tests

```bash
make test
# or
pytest tests/ -v
```

Key test files for thesis evaluation:

| File | What it proves |
|------|---------------|
| `test_suppression.py` | Small-cell suppression cannot be bypassed |
| `test_counts_endpoint.py` | Suppression is enforced at the API layer, not just in the function |
| `test_state_machine.py` | Only legal permit transitions are allowed; every transition is audited |
| `test_airlock_checks.py` | Airlock catches exfiltration attempts; blocked submissions cannot be approved |
| `test_llm_guardrails.py` | PII in prompt is rejected; concept IDs must come from tools |
| `test_projection.py` | Patient subquery is scoped to permitted domains; teardown drops schema and user |

## EHDS Compliance

See `docs/ehds_mapping.md` for the full Article → implementation mapping.

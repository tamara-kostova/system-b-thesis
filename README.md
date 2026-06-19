# System B - SecureHealth Data Access Platform

A reference implementation of an EHDS (European Health Data Space) Chapter IV-compliant platform for secondary use of health data, with an LLM-assisted prompt interface validated against the OMOP CDM v5.4 standard.

## Architecture

Five backend services built in phases, plus a unified Next.js frontend:

| Phase | Service | Port | Description |
|-------|---------|------|-------------|
| 1 | `discovery_api` | 8003 | Public catalogue and concept search (FastAPI) |
| 2 | `permit_service` | 8002 | Data access permit workflow - EHDS Articles 67-68 (FastAPI) |
| 3 | `spe_provisioner` | 8004 | Isolated JupyterLab environments with no internet egress (Docker) |
| 4 | `output_airlock` | 8005 | Disclosure checking before results leave the SPE (FastAPI) |
| 5 | `llm_gateway` | 8006 | LLM-assisted research assistant and in-SPE copilot (FastAPI) |
| - | `web` | 3001 | Unified Next.js 14 frontend (TypeScript + Tailwind) |

## Stack

- Python 3.11+, FastAPI, SQLAlchemy, Pydantic
- Next.js 14, TypeScript, Tailwind CSS (unified web frontend)
- PostgreSQL 16, Docker
- LLM: Anthropic Claude / OpenAI / Ollama (configured via `LLM_PROVIDER` env var)
- Data: synthetic OMOP CDM v5.4 (Eunomia/Synthea) + ATHENA real vocabulary

## Quick Start (Docker Compose)

### 1. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and set at minimum:

```
POSTGRES_PASSWORD=<choose a password>
REVIEWER_PASSWORD=<choose a password for the reviewer UI>
PROJECTION_SALT=<random string used to pseudonymise person_id>

# LLM provider - pick one:
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...
# or
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
# or (local, no API key needed)
LLM_PROVIDER=ollama
```

### 2. Start all services

```bash
docker compose up -d
```

This starts Postgres, all five backend APIs, and the Next.js frontend. The frontend is available at **http://localhost:3001**.

### 3. Load data (first run only)

```bash
# Generate and load synthetic OMOP data
python sql/synthea_to_omop.py --csv synthea/output/csv/

# Load ATHENA vocabulary (download from athena.ohdsi.org, unzip to synthea/vocab/)
python sql/load_vocab.py --vocab synthea/vocab/
python sql/load_vocab.py --remap
```

### 4. (Optional) Local Ollama LLM

```bash
docker compose --profile ollama up -d ollama
ollama pull llama3.2
# set LLM_PROVIDER=ollama in .env
```

### Useful commands

```bash
docker compose logs -f              # tail all logs
docker compose logs -f permit_service  # tail one service
docker compose down                 # stop everything
docker compose up -d --build        # rebuild images and restart
```

## Web Frontend Routes

| Route | Description |
|-------|-------------|
| `/` | Home - platform overview |
| `/datasets` | Browse available OMOP datasets |
| `/concepts` | Search OMOP vocabulary concepts with suppressed counts |
| `/apply` | Submit a data access application (EHDS Article 67) |
| `/my-applications` | Track your own permit applications |
| `/register` | Public register of granted permits (EHDS Article 68) |
| `/spe` | Launch and manage SPE (JupyterLab) environments |
| `/chat` | LLM discovery assistant (Mode A - no permit required) |
| `/review` | Reviewer dashboard - start review, grant, refuse |

The web app proxies all API calls through Next.js rewrites (`/api/discovery/*` → port 8003, `/api/permits/*` → 8002, `/api/llm/*` → 8006, `/api/spe/*` → 8004).

## Local Development (without Docker)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Start Postgres only
docker compose up -d postgres

# Run individual services from project root
uvicorn apps.discovery_api.main:app --reload --port 8003
uvicorn apps.permit_service.main:app --reload --port 8002

# Frontend
cd apps/web && npm install && npm run dev
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `POSTGRES_PASSWORD` | Yes | PostgreSQL password (used by all services) |
| `REVIEWER_PASSWORD` | Yes | Password for the reviewer UI |
| `PROJECTION_SALT` | Yes | Random string for pseudonymising `person_id` |
| `LLM_PROVIDER` | Yes | `anthropic`, `openai`, or `ollama` |
| `ANTHROPIC_API_KEY` | If using Anthropic | Anthropic API key |
| `OPENAI_API_KEY` | If using OpenAI | OpenAI API key |

## Data

Uses synthetic patient data only - no real health records.

### OMOP clinical data (Synthea)

```bash
python sql/synthea_to_omop.py --csv synthea/output/csv/
```

### ATHENA vocabulary (real OMOP vocab)

Download vocabulary files from [athena.ohdsi.org](https://athena.ohdsi.org), unzip to `synthea/vocab/`, then:

```bash
python sql/load_vocab.py --vocab synthea/vocab/
python sql/load_vocab.py --remap   # fix concept_ids in clinical tables
```

The `--remap` step maps raw SNOMED/RxNorm/LOINC codes stored by the Synthea ETL to proper OMOP standard concept IDs. Run it once after the initial vocab load.

## Tests

```bash
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

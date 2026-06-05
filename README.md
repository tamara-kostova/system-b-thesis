# System B — SecureHealth Data Access Platform

A reference implementation of an EHDS (European Health Data Space) Chapter IV-compliant platform for secondary use of health data, with an LLM-assisted prompt interface validated against the OMOP CDM v5.4 standard.

Built as a master's thesis project.

## Architecture

Five services built in phases:

| Phase | Service | Description |
|-------|---------|-------------|
| 1 | `discovery_api` | Public catalogue and concept search (FastAPI) |
| 2 | `permit_service` | Data access permit workflow — EHDS Articles 67–68 (FastAPI + Streamlit) |
| 3 | `spe_provisioner` | Isolated JupyterLab environments with no internet egress (Docker) |
| 4 | `output_airlock` | Disclosure checking before results leave the SPE (FastAPI + Streamlit) |
| 5 | `llm_gateway` | LLM-assisted research assistant and in-SPE copilot (FastAPI) |

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

cp .env.example .env   # edit LLM_PROVIDER and credentials

docker compose up -d postgres
uvicorn apps.llm_gateway.main:app --reload
```

For local LLM with no API key:

```bash
docker compose --profile ollama up -d ollama
ollama pull llama3.2
# LLM_PROVIDER=ollama in .env (default)
```

API docs available at `http://localhost:8000/docs`.

## Data

Uses synthetic patient data only — no real health records. See `sql/` for OMOP load scripts (Phase 0).


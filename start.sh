#!/usr/bin/env bash
# start.sh — start all System B services (APIs + Streamlit UIs)
# Run from the project root. Logs go to logs/. PIDs saved for stop.sh.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
export PYTHONPATH="$ROOT"
VENV="$ROOT/.venv/bin"
LOG="$ROOT/logs"
mkdir -p "$LOG"

# ── helpers ───────────────────────────────────────────────────────────────────

start_service() {
    local name="$1"; shift
    local pidfile="$LOG/$name.pid"
    # Kill any previous instance so re-running start.sh doesn't hit "port in use"
    if [ -f "$pidfile" ]; then
        local old_pid
        old_pid=$(cat "$pidfile")
        kill "$old_pid" 2>/dev/null || true
        rm -f "$pidfile"
        sleep 0.3
    fi
    local logfile="$LOG/$name.log"
    "$@" > "$logfile" 2>&1 &
    echo $! > "$pidfile"
}

check_postgres() {
    if ! "$VENV/python" -c "
import sys
sys.path.insert(0, '$ROOT')
from shared.db import engine
with engine.connect(): pass
" 2>/dev/null; then
        echo "ERROR: Cannot connect to Postgres. Run: docker compose up -d postgres"
        exit 1
    fi
}

# ── preflight ─────────────────────────────────────────────────────────────────

echo "Checking Postgres..."
check_postgres
echo "  OK"
echo ""

# ── FastAPI services ──────────────────────────────────────────────────────────

start_service discovery_api \
    "$VENV/uvicorn" apps.discovery_api.main:app --port 8003 --log-level warning

start_service permit_service \
    "$VENV/uvicorn" apps.permit_service.main:app --port 8002 --log-level warning

start_service spe_provisioner \
    "$VENV/uvicorn" apps.spe_provisioner.main:app --port 8004 --log-level warning

start_service output_airlock \
    "$VENV/uvicorn" apps.output_airlock.main:app --port 8005 --log-level warning

start_service llm_gateway \
    "$VENV/uvicorn" apps.llm_gateway.main:app --host 0.0.0.0 --port 8006 --log-level warning

# ── Streamlit UIs ─────────────────────────────────────────────────────────────

start_service applicant_ui \
    "$VENV/streamlit" run apps/permit_service/applicant_ui.py \
        --server.port 8501 --server.headless true --server.address localhost

start_service permit_reviewer \
    "$VENV/streamlit" run apps/permit_service/reviewer_ui.py \
        --server.port 8502 --server.headless true --server.address localhost

start_service permit_register \
    "$VENV/streamlit" run apps/permit_service/register_ui.py \
        --server.port 8505 --server.headless true --server.address localhost

start_service airlock_reviewer \
    "$VENV/streamlit" run apps/output_airlock/reviewer_ui.py \
        --server.port 8503 --server.headless true --server.address localhost

start_service llm_ui \
    "$VENV/streamlit" run apps/llm_gateway/ui.py \
        --server.port 8504 --server.headless true --server.address localhost

# ── summary ───────────────────────────────────────────────────────────────────

echo "Waiting for APIs to be ready..."
for port in 8003 8002 8004 8005 8006; do
    for i in $(seq 1 20); do
        if curl -sf "http://localhost:$port/health" > /dev/null 2>&1; then
            break
        fi
        sleep 0.5
    done
done

echo "System B is running"
echo ""
echo "  APIs                           Docs"
echo "  ─────────────────────────────────────────────────────"
echo "  Discovery API   http://localhost:8003   /docs"
echo "  Permit Service  http://localhost:8002   /docs"
echo "  SPE Provisioner http://localhost:8004   /docs"
echo "  Output Airlock  http://localhost:8005   /docs"
echo "  LLM Gateway     http://localhost:8006   /docs"
echo ""
echo "  UIs"
echo "  ─────────────────────────────────────────────────────"
echo "  Applicant       http://localhost:8501"
echo "  Permit Reviewer http://localhost:8502"
echo "  Airlock Review  http://localhost:8503"
echo "  LLM Assistant   http://localhost:8504"
echo "  Permit Register http://localhost:8505  (public, no login)"
echo ""
echo "  Logs: tail -f logs/*.log"
echo "  Stop: ./stop.sh"

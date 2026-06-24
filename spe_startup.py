"""
IPython kernel startup for SPE containers.
Runs automatically on every kernel start — no cell execution needed.
Provides: engine, pd, available_views, ask_assistant()
"""

import os

import requests
from sqlalchemy import create_engine, text

PERMIT_ID = os.environ.get("PERMIT_ID", "unknown")
LLM_GATEWAY_URL = os.environ.get("LLM_GATEWAY_URL", "http://host.docker.internal:8006")

engine = create_engine(os.environ["DATABASE_URL"], future=True)

try:
    with engine.connect() as _conn:
        _rows = _conn.execute(
            text(
                "SELECT table_name FROM information_schema.views "
                "WHERE table_schema = current_schema()"
            )
        ).fetchall()
        available_views = [r[0] for r in _rows]
        view_schemas: dict[str, list[str]] = {}
        for _view in available_views:
            _cols = _conn.execute(
                text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_schema = current_schema() AND table_name = :v "
                    "ORDER BY ordinal_position"
                ),
                {"v": _view},
            ).fetchall()
            view_schemas[_view] = [r[0] for r in _cols]
    print(f"SPE ready — Permit: {PERMIT_ID}")
    print(f"Available views: {available_views}")
except Exception as _e:
    available_views = []
    view_schemas = {}
    print(f"WARNING: DB not reachable yet: {_e}")


def ask_assistant(question: str) -> str:
    """Ask the in-SPE LLM copilot. Queries are scoped to this permit's views only."""
    try:
        resp = requests.post(
            f"{LLM_GATEWAY_URL}/chat/spe",
            json={
                "question": question,
                "permit_id": PERMIT_ID,
                "available_views": available_views,
                "view_schemas": view_schemas,
                "user_id": PERMIT_ID,
            },
            timeout=60,
        )
        if not resp.ok:
            return f"Error {resp.status_code}: {resp.json().get('detail', resp.text)}"
        return resp.json()["reply"]
    except requests.exceptions.ConnectionError:
        return (
            "Error: Cannot reach LLM gateway. " "Make sure it is running on the host (port 8006)."
        )

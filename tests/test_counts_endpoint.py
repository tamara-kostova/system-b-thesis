"""
Integration test: verify the /counts/{concept_id} endpoint applies suppression.
A bypass in the endpoint layer would not be caught by unit tests on suppress() alone.
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import MagicMock
from fastapi.testclient import TestClient


def _make_mock_db(count: int, concept_name: str | None = "Test Concept"):
    """Mock DB whose execute().scalar() returns count then concept_name."""
    mock_db = MagicMock()
    mock_db.execute.return_value.scalar.side_effect = [count, concept_name]
    return mock_db


def test_counts_endpoint_suppresses_small_value():
    from apps.discovery_api.main import app
    from shared.db import get_db

    mock_db = _make_mock_db(count=5)
    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        client = TestClient(app)
        resp = client.get("/counts/201826")
        assert resp.status_code == 200
        assert resp.json()["patient_count"] == "<10"
    finally:
        app.dependency_overrides.clear()


def test_counts_endpoint_passes_large_value():
    from apps.discovery_api.main import app
    from shared.db import get_db

    mock_db = _make_mock_db(count=120)
    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        client = TestClient(app)
        resp = client.get("/counts/201826")
        assert resp.status_code == 200
        assert resp.json()["patient_count"] == 120
    finally:
        app.dependency_overrides.clear()


def test_counts_endpoint_suppresses_zero():
    from apps.discovery_api.main import app
    from shared.db import get_db

    mock_db = _make_mock_db(count=0)
    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        client = TestClient(app)
        resp = client.get("/counts/999")
        assert resp.status_code == 200
        assert resp.json()["patient_count"] == "<10"
    finally:
        app.dependency_overrides.clear()


def test_counts_endpoint_suppresses_threshold_minus_one():
    from apps.discovery_api.main import app
    from shared.db import get_db

    mock_db = _make_mock_db(count=9)
    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        client = TestClient(app)
        resp = client.get("/counts/201826")
        assert resp.status_code == 200
        assert resp.json()["patient_count"] == "<10"
    finally:
        app.dependency_overrides.clear()


def test_counts_endpoint_passes_at_threshold():
    from apps.discovery_api.main import app
    from shared.db import get_db

    mock_db = _make_mock_db(count=10)
    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        client = TestClient(app)
        resp = client.get("/counts/201826")
        assert resp.status_code == 200
        assert resp.json()["patient_count"] == 10
    finally:
        app.dependency_overrides.clear()

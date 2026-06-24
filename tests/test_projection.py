"""
Unit tests for the permit-scoped Postgres projection generator.
These tests verify the SQL logic without hitting a real database.
"""

from unittest.mock import MagicMock, patch

from apps.permit_service.models import PermitDB
from apps.spe_provisioner.projection import (
    create_projection,
    schema_name,
    teardown_projection,
    user_name,
)


def make_permit(fmt="anonymized", domains=None, concept_ids=None):
    p = PermitDB()
    p.permit_id = "aaaabbbb-cccc-dddd-eeee-ffffgggghhhh"
    p.format = fmt
    p.data_scope = {
        "domains": domains or ["Condition", "Drug"],
        "concept_ids": concept_ids or [201826, 316866],
        "time_window_from": "2020-01-01",
        "time_window_until": "2024-12-31",
    }
    return p


def make_db():
    db = MagicMock()
    db.begin.return_value.__enter__ = MagicMock(return_value=None)
    db.begin.return_value.__exit__ = MagicMock(return_value=False)
    return db


# Schema / user naming


def test_schema_name_stable():
    assert schema_name("aaaabbbb-cccc-dddd-eeee-ffffgggghhhh") == "permit_aaaabbbbccccddddeeee"


def test_user_name_stable():
    assert user_name("aaaabbbb-cccc-dddd-eeee-ffffgggghhhh") == "spe_aaaabbbbccccddddeeee"


def test_schema_and_user_different():
    pid = "aaaabbbb-cccc-dddd-eeee-ffffgggghhhh"
    assert schema_name(pid) != user_name(pid)


# SQL generation


def _get_executed_sql(db) -> str:
    """Collect all SQL strings passed to db.execute()"""
    parts = []
    for c in db.execute.call_args_list:
        stmt = c[0][0]
        parts.append(str(stmt))
    return "\n".join(parts)


def test_anonymized_uses_null_pseudo_id():
    db = make_db()
    with patch("apps.spe_provisioner.projection._random_password", return_value="testpass"):
        create_projection(make_permit(fmt="anonymized"), db, salt="testsalt")
    sql = _get_executed_sql(db)
    assert "NULL::text AS pseudo_id" in sql
    assert "md5(" not in sql


def test_pseudonymized_uses_md5():
    db = make_db()
    with patch("apps.spe_provisioner.projection._random_password", return_value="testpass"):
        create_projection(make_permit(fmt="pseudonymized"), db, salt="testsalt")
    sql = _get_executed_sql(db)
    assert "md5(" in sql
    assert "testsalt" in sql


def test_schema_created():
    db = make_db()
    create_projection(make_permit(), db, salt="s")
    sql = _get_executed_sql(db)
    assert "CREATE SCHEMA IF NOT EXISTS permit_" in sql


def test_grants_issued():
    db = make_db()
    create_projection(make_permit(), db, salt="s")
    sql = _get_executed_sql(db)
    assert "GRANT USAGE ON SCHEMA" in sql
    assert "GRANT SELECT ON ALL TABLES" in sql


def test_condition_view_created_when_in_domains():
    db = make_db()
    create_projection(make_permit(domains=["Condition"]), db, salt="s")
    sql = _get_executed_sql(db)
    assert "conditions" in sql
    assert "condition_concept_id" in sql


def test_drug_view_not_created_when_not_in_domains():
    db = make_db()
    create_projection(make_permit(domains=["Condition"]), db, salt="s")
    sql = _get_executed_sql(db)
    assert "drug_exposure" not in sql


def test_concept_ids_in_patient_filter():
    db = make_db()
    create_projection(make_permit(concept_ids=[201826, 316866]), db, salt="s")
    sql = _get_executed_sql(db)
    assert "201826" in sql
    assert "316866" in sql


def test_time_window_in_view():
    db = make_db()
    create_projection(make_permit(), db, salt="s")
    sql = _get_executed_sql(db)
    assert "2020-01-01" in sql
    assert "2024-12-31" in sql


def test_teardown_drops_schema_and_user():
    db = make_db()
    teardown_projection("aaaabbbb-cccc-dddd-eeee-ffffgggghhhh", db)
    sql = _get_executed_sql(db)
    assert "DROP SCHEMA IF EXISTS permit_aaaabbbbccccddddeeee" in sql
    assert "DROP USER" in sql

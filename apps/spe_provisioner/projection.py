"""
Phase 3.5 — Permit-scoped Postgres projection.

For each granted permit this module creates a Postgres schema containing views
that expose ONLY the data the permit covers:
  - Only the permitted domains (Condition, Drug, Measurement)
  - Only patients who have one of the permitted concepts
  - Only rows within the permit's time window
  - person_id is NULL (anonymized) or md5(person_id || salt) (pseudonymized)

A dedicated Postgres user is created with SELECT on this schema only.
This is the EHDS Chapter IV data minimisation control — enforced in the DB,
not in application code.
"""

import secrets
import string
from sqlalchemy import text
from sqlalchemy.orm import Session

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
from apps.permit_service.models import PermitDB


DOMAIN_TABLE = {
    "Condition":   "condition_occurrence",
    "Drug":        "drug_exposure",
    "Measurement": "measurement",
}
DOMAIN_CONCEPT_COL = {
    "Condition":   "condition_concept_id",
    "Drug":        "drug_concept_id",
    "Measurement": "measurement_concept_id",
}
DOMAIN_DATE_COL = {
    "Condition":   "condition_start_date",
    "Drug":        "drug_exposure_start_date",
    "Measurement": "measurement_date",
}


def schema_name(permit_id: str) -> str:
    return "permit_" + permit_id.replace("-", "")[:20]


def user_name(permit_id: str) -> str:
    return "spe_" + permit_id.replace("-", "")[:20]


def _random_password(length: int = 24) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def create_projection(permit: PermitDB, db: Session, salt: str) -> tuple[str, str]:
    """
    Create a permit-scoped Postgres schema and user.
    Returns (db_user, db_password).
    """
    schema  = schema_name(permit.permit_id)
    user    = user_name(permit.permit_id)
    password = _random_password()
    scope   = permit.data_scope
    concept_ids = [int(c) for c in scope.get("concept_ids", [])]
    time_from   = scope.get("time_window_from")
    time_until  = scope.get("time_window_until")
    domains     = scope.get("domains", [])

    cids_sql = ", ".join(str(c) for c in concept_ids) if concept_ids else "0"

    # Patients with any of the permitted concepts (via CONCEPT_ANCESTOR)
    patient_subquery = f"""
        SELECT DISTINCT person_id FROM cdm.condition_occurrence co
        JOIN cdm.concept_ancestor ca ON ca.descendant_concept_id = co.condition_concept_id
        WHERE ca.ancestor_concept_id IN ({cids_sql})
    """

    if permit.format == "pseudonymized":
        person_col = f"md5(person_id::text || '{salt}') AS pseudo_id"
    else:
        person_col = "NULL::text AS pseudo_id"

    stmts = [
        f"CREATE SCHEMA IF NOT EXISTS {schema}",
        f"""DO $$ BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{user}') THEN
    CREATE USER {user} WITH PASSWORD '{password}';
  END IF;
END $$""",
    ]

    for domain in domains:
        if domain not in DOMAIN_TABLE:
            continue
        table       = DOMAIN_TABLE[domain]
        concept_col = DOMAIN_CONCEPT_COL[domain]
        date_col    = DOMAIN_DATE_COL[domain]
        view        = domain.lower() + "s"

        stmts.append(f"""CREATE OR REPLACE VIEW {schema}.{view} AS
  SELECT
    {person_col},
    {concept_col},
    {date_col}
  FROM cdm.{table}
  WHERE person_id IN ({patient_subquery})
    AND {date_col} BETWEEN '{time_from}' AND '{time_until}'
    AND {concept_col} IN (
        SELECT descendant_concept_id FROM cdm.concept_ancestor
        WHERE ancestor_concept_id IN ({cids_sql})
    )""")

    stmts += [
        f"GRANT USAGE ON SCHEMA {schema} TO {user}",
        f"GRANT SELECT ON ALL TABLES IN SCHEMA {schema} TO {user}",
        f"ALTER USER {user} SET search_path TO {schema}",
    ]

    for stmt in stmts:
        db.execute(text(stmt))
    db.commit()

    return user, password


def teardown_projection(permit_id: str, db: Session):
    """Drop the schema and user when the permit expires."""
    schema = schema_name(permit_id)
    user   = user_name(permit_id)
    db.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
    db.execute(text(f"""
        DO $$ BEGIN
          IF EXISTS (SELECT FROM pg_roles WHERE rolname = '{user}') THEN
            DROP USER {user};
          END IF;
        END $$
    """))
    db.commit()

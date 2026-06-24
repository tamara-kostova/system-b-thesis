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

from apps.permit_service.models import PermitDB

DOMAIN_TABLE = {
    "Condition": "condition_occurrence",
    "Drug": "drug_exposure",
    "Measurement": "measurement",
}
DOMAIN_CONCEPT_COL = {
    "Condition": "condition_concept_id",
    "Drug": "drug_concept_id",
    "Measurement": "measurement_concept_id",
}
DOMAIN_DATE_COL = {
    "Condition": "condition_start_date",
    "Drug": "drug_exposure_start_date",
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
    schema = schema_name(permit.permit_id)
    user = user_name(permit.permit_id)
    password = _random_password()
    scope = permit.data_scope
    concept_ids = [int(c) for c in scope.get("concept_ids", [])]
    time_from = scope.get("time_window_from")
    time_until = scope.get("time_window_until")
    domains = scope.get("domains", [])

    cids_sql = ", ".join(str(c) for c in concept_ids) if concept_ids else None

    # Patients scoped to the permitted domains only (data minimisation — EHDS Chapter IV).
    # Union across each permitted domain so a measurement-only permit never pulls patients
    # from condition_occurrence.
    # When concept_ids is empty, no cohort restriction — all patients in the domain are included.
    _patient_parts = []
    for _domain in domains:
        if _domain not in DOMAIN_TABLE:
            continue
        _table = DOMAIN_TABLE[_domain]
        _col = DOMAIN_CONCEPT_COL[_domain]
        if cids_sql:
            _patient_parts.append(
                f"SELECT DISTINCT person_id FROM cdm.{_table} "
                f"WHERE {_col} IN ("
                f"SELECT descendant_concept_id FROM cdm.concept_ancestor "
                f"WHERE ancestor_concept_id IN ({cids_sql}) "
                f"UNION SELECT unnest(ARRAY[{cids_sql}]))"
            )
        else:
            _patient_parts.append(f"SELECT DISTINCT person_id FROM cdm.{_table}")
    if _patient_parts:
        patient_subquery = " UNION ".join(_patient_parts)
    else:
        patient_subquery = "SELECT NULL::bigint AS person_id WHERE FALSE"

    safe_salt = salt.replace("'", "''")
    if permit.format == "pseudonymized":
        person_col = f"md5(person_id::text || '{safe_salt}') AS pseudo_id"
    else:
        person_col = "NULL::text AS pseudo_id"

    stmts = [
        f"CREATE SCHEMA IF NOT EXISTS {schema}",
        f"""DO $$ BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{user}') THEN
    CREATE USER {user} WITH PASSWORD '{password}';
  END IF;
END $$""",
        # Always sync the password — handles re-provisioning where user exists
        # but was created with a different random password in a prior attempt.
        f"ALTER USER {user} WITH PASSWORD '{password}'",
    ]

    for domain in domains:
        if domain not in DOMAIN_TABLE:
            continue
        table = DOMAIN_TABLE[domain]
        concept_col = DOMAIN_CONCEPT_COL[domain]
        date_col = DOMAIN_DATE_COL[domain]
        view = domain.lower() + "s"

        concept_filter = (
            f"AND {concept_col} IN (\n"
            f"        SELECT descendant_concept_id FROM cdm.concept_ancestor\n"
            f"        WHERE ancestor_concept_id IN ({cids_sql})\n"
            f"        UNION SELECT unnest(ARRAY[{cids_sql}])\n"
            f"    )"
            if cids_sql
            else ""
        )
        stmts.append(f"""CREATE OR REPLACE VIEW {schema}.{view} AS
  SELECT
    {person_col},
    {concept_col},
    {date_col}
  FROM cdm.{table}
  WHERE person_id IN ({patient_subquery})
    AND {date_col} BETWEEN '{time_from}' AND '{time_until}'
    {concept_filter}""")

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
    user = user_name(permit_id)
    db.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
    db.execute(text(f"""
        DO $$ BEGIN
          IF EXISTS (SELECT FROM pg_roles WHERE rolname = '{user}') THEN
            DROP USER {user};
          END IF;
        END $$
    """))
    db.commit()

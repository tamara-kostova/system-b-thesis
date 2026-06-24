"""
Audit logging — EHDS Article 73.

Every EHDS-relevant action calls log_event().  Records go to:
  1. Python logger (stdout/structured log aggregator)
  2. audit.event DB table when a SQLAlchemy session is provided

The DB table is the authoritative, queryable trail.  Pass db= at every
call site that already has a session open; it will be flushed together
with the surrounding transaction so the audit row and the business row
are always committed atomically.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, Column, DateTime, Integer, String
from sqlalchemy.orm import Session

from shared.db import Base, engine

logger = logging.getLogger("audit")
logger.setLevel(logging.INFO)
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setLevel(logging.INFO)
    logger.addHandler(_handler)
    logger.propagate = False


class AuditEvent(Base):
    __tablename__ = "event"
    __table_args__ = {"schema": "audit"}

    id = Column(Integer, primary_key=True, autoincrement=True)
    ts = Column(DateTime(timezone=True), nullable=False)
    event_type = Column(String(100), nullable=False)
    actor = Column(String(200), nullable=False)
    resource_id = Column(String(200), nullable=False)
    details = Column(JSON, nullable=True)


def create_audit_schema() -> None:
    """Create the audit schema and table if they do not exist."""
    with engine.begin() as conn:
        conn.execute(__import__("sqlalchemy").text("CREATE SCHEMA IF NOT EXISTS audit"))
    Base.metadata.create_all(engine, tables=[AuditEvent.__table__])


def log_event(
    event_type: str,
    actor: str,
    resource_id: str,
    details: dict[str, Any] | None = None,
    db: Session | None = None,
) -> None:
    """Write a structured audit event to logger and, when db is supplied, to the DB."""
    ts = datetime.now(timezone.utc)
    entry = {
        "ts": ts.isoformat(),
        "event_type": event_type,
        "actor": actor,
        "resource_id": resource_id,
        "details": details or {},
    }
    logger.info(json.dumps(entry))

    if db is not None:
        try:
            db.add(
                AuditEvent(
                    ts=ts,
                    event_type=event_type,
                    actor=actor,
                    resource_id=resource_id,
                    details=details or {},
                )
            )
            db.flush()
        except Exception as exc:
            logger.error("audit db write failed: %s", exc)

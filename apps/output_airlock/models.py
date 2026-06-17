import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, Boolean, LargeBinary, DateTime, Text, JSON
from sqlalchemy.dialects.postgresql import UUID

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
from shared.db import Base, engine


class AirlockSubmissionDB(Base):
    __tablename__ = "submission"
    __table_args__ = {"schema": "airlock"}

    submission_id       = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    permit_id           = Column(String, nullable=False)
    filename            = Column(String, nullable=False)
    content_type        = Column(String, nullable=False)
    file_content        = Column(LargeBinary, nullable=False)
    justification       = Column(Text, nullable=True)
    automated_checks    = Column(JSON, nullable=False)   # list of {name, passed, reason}
    all_checks_passed   = Column(Boolean, nullable=False)
    state               = Column(String, nullable=False, default="pending_review")
    reviewer            = Column(String, nullable=True)
    reviewer_comment    = Column(Text, nullable=True)
    submitted_at        = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    reviewed_at         = Column(DateTime, nullable=True)


def create_tables():
    with engine.connect() as conn:
        conn.execute(__import__("sqlalchemy").text("CREATE SCHEMA IF NOT EXISTS airlock"))
        conn.commit()
    Base.metadata.create_all(engine, tables=[AirlockSubmissionDB.__table__])

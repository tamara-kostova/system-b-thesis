import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, Date, DateTime, JSON
from sqlalchemy import event
from sqlalchemy.orm import Session

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
from shared.db import Base, engine


class PermitDB(Base):
    __tablename__ = "permit"
    __table_args__ = {"schema": "permits"}

    permit_id             = Column(String,   primary_key=True, default=lambda: str(uuid.uuid4()))
    type                  = Column(String(10),  nullable=False)
    holder                = Column(String(255), nullable=False)
    named_users           = Column(JSON,        nullable=False, default=list)
    purpose               = Column(String(50),  nullable=False)
    data_scope            = Column(JSON,        nullable=False)
    format                = Column(String(20),  nullable=False)
    pseudonymization_justification = Column(Text, nullable=True)
    valid_from            = Column(Date,        nullable=True)
    valid_until           = Column(Date,        nullable=True)
    state                 = Column(String(20),  nullable=False, default="draft")
    omop_snapshot         = Column(String(50),  nullable=False, default="synthea-omop-v1")
    vocab_version         = Column(String(50),  nullable=False, default="5.4")
    reviewer_comment      = Column(Text,        nullable=True)
    created_at            = Column(DateTime,    nullable=False, default=datetime.utcnow)
    updated_at            = Column(DateTime,    nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


def create_tables():
    with engine.begin() as conn:
        conn.execute(__import__("sqlalchemy").text("CREATE SCHEMA IF NOT EXISTS permits"))
    Base.metadata.create_all(engine)

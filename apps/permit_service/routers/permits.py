from datetime import date
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))
from shared.db import get_db
from shared.audit import log_event
from apps.permit_service.models import PermitDB
from apps.permit_service.state_machine import PermitStateMachine, IllegalTransitionError

router = APIRouter(prefix="/permits", tags=["permits"])


# --- Schemas ---

class DataScopeIn(BaseModel):
    domains: list[str]
    concept_ids: list[int]
    time_window_from: date
    time_window_until: date


class PermitCreate(BaseModel):
    type: Literal["request", "permit"]
    holder: str
    named_users: list[str] = []
    purpose: Literal["public_health", "policy", "statistics", "education", "research", "innovation"]
    data_scope: DataScopeIn
    format: Literal["anonymized", "pseudonymized"]
    pseudonymization_justification: str | None = None


class PermitOut(BaseModel):
    permit_id: str
    type: str
    holder: str
    named_users: list[str]
    purpose: str
    data_scope: dict
    format: str
    pseudonymization_justification: str | None
    valid_from: date | None
    valid_until: date | None
    state: str
    omop_snapshot: str
    vocab_version: str
    reviewer_comment: str | None
    created_at: str
    updated_at: str

    @classmethod
    def from_db(cls, p: PermitDB) -> "PermitOut":
        return cls(
            permit_id=p.permit_id,
            type=p.type,
            holder=p.holder,
            named_users=p.named_users or [],
            purpose=p.purpose,
            data_scope=p.data_scope,
            format=p.format,
            pseudonymization_justification=p.pseudonymization_justification,
            valid_from=p.valid_from,
            valid_until=p.valid_until,
            state=p.state,
            omop_snapshot=p.omop_snapshot,
            vocab_version=p.vocab_version,
            reviewer_comment=p.reviewer_comment,
            created_at=str(p.created_at),
            updated_at=str(p.updated_at),
        )


class TransitionRequest(BaseModel):
    actor: str
    comment: str | None = None
    valid_from: date | None = None
    valid_until: date | None = None


# --- Endpoints ---

@router.post("", response_model=PermitOut, status_code=201)
def create_permit(body: PermitCreate, db: Session = Depends(get_db)):
    permit = PermitDB(
        type=body.type,
        holder=body.holder,
        named_users=body.named_users,
        purpose=body.purpose,
        data_scope=body.data_scope.model_dump(),
        format=body.format,
        pseudonymization_justification=body.pseudonymization_justification,
    )
    db.add(permit)
    db.flush()
    log_event(
        event_type="permit.draft",
        actor=body.holder,
        resource_id=permit.permit_id,
        details={"type": body.type, "purpose": body.purpose},
        db=db,
    )
    db.commit()
    db.refresh(permit)
    return PermitOut.from_db(permit)


@router.get("", response_model=list[PermitOut])
def list_permits(state: str | None = None, holder: str | None = None, db: Session = Depends(get_db)):
    q = db.query(PermitDB)
    if state:
        q = q.filter(PermitDB.state == state)
    if holder:
        q = q.filter(PermitDB.holder == holder)
    return [PermitOut.from_db(p) for p in q.order_by(PermitDB.created_at.desc())]


@router.get("/register", response_model=list[PermitOut])
def public_register(db: Session = Depends(get_db)):
    """Public list of granted permits — no personal data, metadata only."""
    permits = db.query(PermitDB).filter(PermitDB.state == "granted").all()
    return [PermitOut.from_db(p) for p in permits]


@router.get("/{permit_id}", response_model=PermitOut)
def get_permit(permit_id: str, db: Session = Depends(get_db)):
    p = db.get(PermitDB, permit_id)
    if not p:
        raise HTTPException(404, "Permit not found")
    return PermitOut.from_db(p)


def _get_or_404(permit_id: str, db: Session) -> PermitDB:
    p = db.get(PermitDB, permit_id)
    if not p:
        raise HTTPException(404, "Permit not found")
    return p


@router.post("/{permit_id}/submit", response_model=PermitOut)
def submit(permit_id: str, body: TransitionRequest, db: Session = Depends(get_db)):
    p = _get_or_404(permit_id, db)
    try:
        PermitStateMachine(p, db).submit(body.actor)
    except IllegalTransitionError as e:
        raise HTTPException(400, str(e))
    return PermitOut.from_db(p)


@router.post("/{permit_id}/review", response_model=PermitOut)
def start_review(permit_id: str, body: TransitionRequest, db: Session = Depends(get_db)):
    p = _get_or_404(permit_id, db)
    try:
        PermitStateMachine(p, db).start_review(body.actor)
    except IllegalTransitionError as e:
        raise HTTPException(400, str(e))
    return PermitOut.from_db(p)


@router.post("/{permit_id}/grant", response_model=PermitOut)
def grant(permit_id: str, body: TransitionRequest, db: Session = Depends(get_db)):
    if not body.valid_from or not body.valid_until:
        raise HTTPException(400, "valid_from and valid_until are required to grant a permit")
    p = _get_or_404(permit_id, db)
    try:
        PermitStateMachine(p, db).grant(body.actor, body.valid_from, body.valid_until)
    except IllegalTransitionError as e:
        raise HTTPException(400, str(e))
    return PermitOut.from_db(p)


@router.post("/{permit_id}/refuse", response_model=PermitOut)
def refuse(permit_id: str, body: TransitionRequest, db: Session = Depends(get_db)):
    p = _get_or_404(permit_id, db)
    try:
        PermitStateMachine(p, db).refuse(body.actor, body.comment or "")
    except IllegalTransitionError as e:
        raise HTTPException(400, str(e))
    return PermitOut.from_db(p)

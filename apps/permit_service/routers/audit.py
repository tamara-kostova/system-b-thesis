from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc

from shared.audit import AuditEvent
from shared.db import SessionLocal

router = APIRouter(prefix="/audit", tags=["audit"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/events")
def list_events(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    event_type: str | None = Query(None),
    actor: str | None = Query(None),
    resource_id: str | None = Query(None),
    db: Session = Depends(get_db),
):
    q = db.query(AuditEvent)
    if event_type:
        q = q.filter(AuditEvent.event_type == event_type)
    if actor:
        q = q.filter(AuditEvent.actor.ilike(f"%{actor}%"))
    if resource_id:
        q = q.filter(AuditEvent.resource_id.ilike(f"%{resource_id}%"))
    total = q.count()
    events = q.order_by(desc(AuditEvent.ts)).offset(offset).limit(limit).all()
    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "events": [
            {
                "id": e.id,
                "ts": e.ts.isoformat(),
                "event_type": e.event_type,
                "actor": e.actor,
                "resource_id": e.resource_id,
                "details": e.details,
            }
            for e in events
        ],
    }

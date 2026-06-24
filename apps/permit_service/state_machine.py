"""
Permit state machine — EHDS Articles 67-68.

Every state transition is a method that:
  1. Checks the transition is legal
  2. Updates the state
  3. Writes an audit event

No state change happens outside this class.
"""

from datetime import date, datetime, timezone

from sqlalchemy.orm import Session

from apps.permit_service.models import PermitDB
from shared.audit import log_event
from shared.models import PERMIT_TRANSITIONS as TRANSITIONS


class IllegalTransitionError(ValueError):
    pass


class PermitStateMachine:
    def __init__(self, permit: PermitDB, db: Session):
        self.permit = permit
        self.db = db

    def _transition(self, new_state: str, actor: str, details: dict | None = None):
        allowed = TRANSITIONS.get(self.permit.state, [])
        if new_state not in allowed:
            raise IllegalTransitionError(
                f"Cannot transition from '{self.permit.state}' to '{new_state}'"
            )
        old_state = self.permit.state
        self.permit.state = new_state
        self.permit.updated_at = datetime.now(timezone.utc)
        log_event(
            event_type=f"permit.{new_state}",
            actor=actor,
            resource_id=self.permit.permit_id,
            details={"from": old_state, "to": new_state, **(details or {})},
            db=self.db,
        )
        self.db.commit()

    def submit(self, actor: str):
        self._transition("submitted", actor)

    def start_review(self, actor: str):
        self._transition("under_review", actor)

    def grant(self, actor: str, valid_from: date, valid_until: date):
        if valid_until <= valid_from:
            raise IllegalTransitionError(
                f"valid_until ({valid_until}) must be after valid_from ({valid_from})"
            )
        self.permit.valid_from = valid_from
        self.permit.valid_until = valid_until
        self._transition(
            "granted", actor, {"valid_from": str(valid_from), "valid_until": str(valid_until)}
        )

    def refuse(self, actor: str, comment: str):
        self.permit.reviewer_comment = comment
        self._transition("refused", actor, {"comment": comment})

    def expire(self, actor: str):
        self._transition("expired", actor)

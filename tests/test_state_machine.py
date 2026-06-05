import pytest
from datetime import date
from unittest.mock import MagicMock

from apps.permit_service.state_machine import PermitStateMachine, IllegalTransitionError, TRANSITIONS
from apps.permit_service.models import PermitDB


def make_permit(state: str) -> PermitDB:
    p = PermitDB()
    p.permit_id = "test-permit-id"
    p.state = state
    return p


def make_sm(state: str) -> PermitStateMachine:
    db = MagicMock()
    db.commit = MagicMock()
    return PermitStateMachine(make_permit(state), db)


# Legal transitions

def test_draft_can_submit():
    sm = make_sm("draft")
    sm.submit("applicant")
    assert sm.permit.state == "submitted"


def test_submitted_can_start_review():
    sm = make_sm("submitted")
    sm.start_review("reviewer")
    assert sm.permit.state == "under_review"


def test_submitted_can_be_refused():
    sm = make_sm("submitted")
    sm.refuse("reviewer", "Incomplete justification")
    assert sm.permit.state == "refused"


def test_under_review_can_be_granted():
    sm = make_sm("under_review")
    sm.grant("reviewer", date(2026, 1, 1), date(2026, 12, 31))
    assert sm.permit.state == "granted"
    assert sm.permit.valid_from == date(2026, 1, 1)
    assert sm.permit.valid_until == date(2026, 12, 31)


def test_under_review_can_be_refused():
    sm = make_sm("under_review")
    sm.refuse("reviewer", "Does not meet Article 53 criteria")
    assert sm.permit.state == "refused"
    assert sm.permit.reviewer_comment == "Does not meet Article 53 criteria"


def test_granted_can_expire():
    sm = make_sm("granted")
    sm.expire("system")
    assert sm.permit.state == "expired"


# Illegal transitions

def test_draft_cannot_be_granted_directly():
    with pytest.raises(IllegalTransitionError):
        make_sm("draft").grant("reviewer", date.today(), date.today())


def test_refused_is_terminal():
    for action in ["submit", "start_review", "expire"]:
        with pytest.raises(IllegalTransitionError):
            sm = make_sm("refused")
            getattr(sm, action)("actor")


def test_expired_is_terminal():
    with pytest.raises(IllegalTransitionError):
        make_sm("expired").grant("reviewer", date.today(), date.today())


def test_granted_cannot_be_submitted():
    with pytest.raises(IllegalTransitionError):
        make_sm("granted").submit("actor")


# Verify all defined transitions are tested
def test_transitions_table_complete():
    assert set(TRANSITIONS.keys()) == {"draft", "submitted", "under_review", "granted", "refused", "expired"}

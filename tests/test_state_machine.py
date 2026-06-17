import pytest
from datetime import date
from unittest.mock import MagicMock, patch

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


# Audit event assertions — a refactor that drops log_event should fail these

def test_submit_writes_audit_event():
    with patch("apps.permit_service.state_machine.log_event") as mock_log:
        sm = make_sm("draft")
        sm.submit("applicant@example.com")
        mock_log.assert_called_once()
        call_kwargs = mock_log.call_args.kwargs
        assert call_kwargs["event_type"] == "permit.submitted"
        assert call_kwargs["actor"] == "applicant@example.com"
        assert call_kwargs["resource_id"] == "test-permit-id"
        assert call_kwargs["details"]["from"] == "draft"
        assert call_kwargs["details"]["to"] == "submitted"
        assert call_kwargs["db"] is sm.db


def test_grant_writes_audit_event():
    with patch("apps.permit_service.state_machine.log_event") as mock_log:
        sm = make_sm("under_review")
        sm.grant("reviewer", date(2026, 1, 1), date(2026, 12, 31))
        mock_log.assert_called_once()
        call_kwargs = mock_log.call_args.kwargs
        assert call_kwargs["event_type"] == "permit.granted"
        assert call_kwargs["actor"] == "reviewer"


def test_refuse_writes_audit_event():
    with patch("apps.permit_service.state_machine.log_event") as mock_log:
        sm = make_sm("under_review")
        sm.refuse("reviewer", "Does not meet Article 53 criteria")
        mock_log.assert_called_once()
        call_kwargs = mock_log.call_args.kwargs
        assert call_kwargs["event_type"] == "permit.refused"
        assert call_kwargs["details"]["comment"] == "Does not meet Article 53 criteria"


def test_illegal_transition_does_not_write_audit():
    with patch("apps.permit_service.state_machine.log_event") as mock_log:
        with pytest.raises(IllegalTransitionError):
            make_sm("draft").grant("reviewer", date.today(), date.today())
        mock_log.assert_not_called()


def test_grant_valid_until_before_valid_from_is_rejected():
    """Issuing an already-expired permit (valid_until ≤ valid_from) must be refused."""
    with patch("apps.permit_service.state_machine.log_event"):
        with pytest.raises(IllegalTransitionError):
            make_sm("under_review").grant("reviewer", date(2026, 12, 31), date(2026, 1, 1))


def test_grant_same_day_valid_from_and_until_is_rejected():
    with patch("apps.permit_service.state_machine.log_event"):
        with pytest.raises(IllegalTransitionError):
            make_sm("under_review").grant("reviewer", date(2026, 6, 1), date(2026, 6, 1))

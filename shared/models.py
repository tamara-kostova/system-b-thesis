from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

PERMIT_TRANSITIONS: dict[str, list[str]] = {
    "draft": ["submitted"],
    "submitted": ["under_review", "refused"],
    "under_review": ["granted", "refused"],
    "granted": ["expired"],
    "refused": [],
    "expired": [],
}


class DataScope(BaseModel):
    domains: list[str]
    concept_ids: list[int]
    time_window_from: date
    time_window_until: date


class Permit(BaseModel):
    permit_id: str
    type: Literal["request", "permit"]
    holder: str
    named_users: list[str] = Field(default_factory=list)
    purpose: Literal["public_health", "policy", "statistics", "education", "research", "innovation"]
    data_scope: DataScope
    format: Literal["anonymized", "pseudonymized"]
    pseudonymization_justification: str | None = None
    valid_from: date
    valid_until: date
    state: Literal["draft", "submitted", "under_review", "granted", "refused", "expired"] = "draft"
    omop_snapshot: str
    vocab_version: str

    _TRANSITIONS = PERMIT_TRANSITIONS

    def can_transition_to(self, new_state: str) -> bool:
        return new_state in PERMIT_TRANSITIONS.get(self.state, [])

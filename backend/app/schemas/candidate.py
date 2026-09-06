from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.models.candidate import CandidateStatus


class CandidateCreate(BaseModel):
    full_name: str = Field(min_length=1, max_length=255)
    email: str | None = None
    phone: str | None = None
    position_id: int
    interviewer_id: int


class CandidateUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    email: str | None = None
    phone: str | None = None


class HoldRequest(BaseModel):
    reason: str = Field(min_length=1)
    review_by: date | None = None
    # Required only when the candidate's open round has a scheduled (non-cancelled)
    # interview — the hold endpoint rejects the request with no default in that
    # case rather than silently choosing keep or cancel for the admin.
    interview_action: Literal["keep", "cancel"] | None = None


class CandidateOut(BaseModel):
    id: int
    full_name: str
    email: str | None
    phone: str | None
    position_id: int
    owner_id: int | None
    open_round_id: int | None
    status: CandidateStatus
    hold_reason: str | None
    hold_review_by: date | None
    created_by: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class InterviewerOut(BaseModel):
    id: int
    full_name: str
    email: str
    timezone: str | None

    model_config = {"from_attributes": True}

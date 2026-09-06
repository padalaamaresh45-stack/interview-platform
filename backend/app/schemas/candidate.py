from datetime import date, datetime

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

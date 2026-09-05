from datetime import datetime

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
    interviewer_id: int | None = None


class CandidateOut(BaseModel):
    id: int
    full_name: str
    email: str | None
    phone: str | None
    position_id: int
    interviewer_id: int
    status: CandidateStatus
    created_by: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class InterviewerOut(BaseModel):
    id: int
    full_name: str
    email: str

    model_config = {"from_attributes": True}

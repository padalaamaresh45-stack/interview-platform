from datetime import datetime

from pydantic import BaseModel, Field

from app.models.interview import InterviewStatus


class InterviewCreate(BaseModel):
    round_id: int
    scheduled_at: datetime
    duration_minutes: int = Field(default=60, ge=15, le=480)
    notes: str | None = None


class InterviewOut(BaseModel):
    id: int
    candidate_id: int
    candidate_name: str
    position_title: str
    round_id: int
    interviewer_id: int
    interviewer_name: str
    status: InterviewStatus
    scheduled_at: datetime
    duration_minutes: int
    notes: str | None
    created_at: datetime

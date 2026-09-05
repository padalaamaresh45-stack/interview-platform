from datetime import datetime

from pydantic import BaseModel, Field


class InterviewCreate(BaseModel):
    candidate_id: int
    interviewer_id: int
    scheduled_at: datetime
    duration_minutes: int = Field(default=60, ge=15, le=480)
    notes: str | None = None


class InterviewOut(BaseModel):
    id: int
    candidate_id: int
    candidate_name: str
    position_title: str
    interviewer_id: int
    interviewer_name: str
    scheduled_at: datetime
    duration_minutes: int
    notes: str | None
    created_at: datetime

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.round import RoundStatus


class RoundAssignRequest(BaseModel):
    """Assign a candidate to a new Round, optionally scheduling its Interview
    in the same atomic write. Leaving the scheduling fields blank creates the
    Round only — "assigned but unscheduled" (ticket #28)."""

    stage_id: int
    assignee_id: int
    assignment_due_at: datetime | None = None
    brief: str | None = None
    scheduled_at: datetime | None = None
    duration_minutes: int = Field(default=60, ge=15, le=480)
    notes: str | None = None


class ReassignRequest(BaseModel):
    """Reassign the candidate's open round to a different interviewer, same
    stage. See `close_and_open_round`'s `prior_round_closed_status="reassigned"`
    call in the reassign endpoint (ticket #30)."""

    assignee_id: int


class RoundOut(BaseModel):
    id: int
    candidate_id: int
    stage_id: int
    assignee_id: int
    status: RoundStatus
    assignment_due_at: datetime | None
    brief: str | None
    reassigned_from_round_id: int | None
    created_at: datetime
    closed_at: datetime | None
    interview_id: int | None

    model_config = {"from_attributes": True}

from datetime import datetime

from pydantic import BaseModel

from app.models.candidate import CandidateStatus
from app.schemas.interview_score import InterviewScoreOut


class StageOut(BaseModel):
    id: int
    position_id: int
    name: str
    sequence_order: int
    day_limit: int | None
    is_terminal: bool
    advance_threshold: int | None
    reject_threshold: int | None
    feedback_grace_hours: int | None

    model_config = {"from_attributes": True}


class ScoreSummaryOut(BaseModel):
    submitted_count: int
    total_count: int
    average: float | None


class BoardCandidateOut(BaseModel):
    id: int
    full_name: str
    position_id: int
    position_title: str
    owner_id: int | None
    status: CandidateStatus
    current_stage_id: int
    days_in_stage: int
    health: str | None
    next_action: str
    score: ScoreSummaryOut


class BoardColumnOut(BaseModel):
    stage: StageOut
    candidates: list[BoardCandidateOut]


class BoardOut(BaseModel):
    columns: list[BoardColumnOut]


class MoveCandidateRequest(BaseModel):
    to_stage_id: int
    # Moving a candidate OUT of a terminal stage (Hired/Rejected) is blocked
    # unless the admin explicitly confirms — force=true is that confirmation.
    force: bool = False


class StageTransitionOut(BaseModel):
    id: int
    from_stage_id: int | None
    from_stage_name: str | None
    to_stage_id: int
    to_stage_name: str
    actor_id: int
    actor_name: str
    created_at: datetime


class CandidateHistoryOut(BaseModel):
    id: int
    full_name: str
    position_id: int
    position_title: str
    status: CandidateStatus
    current_stage_id: int
    current_stage_name: str
    days_in_stage: int
    health: str | None
    next_action: str
    score: ScoreSummaryOut
    stage_history: list[StageTransitionOut]
    scores: list[InterviewScoreOut]

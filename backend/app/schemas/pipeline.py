from datetime import datetime

from pydantic import BaseModel

from app.models.candidate import CandidateStatus
from app.models.round import RoundStatus
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
    gap_state: str | None
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


class RoundConsolidationOut(BaseModel):
    id: int
    stage_id: int
    stage_name: str
    assignee_id: int
    assignee_name: str
    status: RoundStatus
    created_at: datetime
    closed_at: datetime | None
    average_score: float | None
    scores: list[InterviewScoreOut]


class ConsolidationOut(BaseModel):
    """Every Round for a candidate, in chronological order, plus the
    cross-round average/variance — the input to #27's "split decision" badge,
    computed once (compute_score_variance/is_split_decision in derive.py) and
    reused here rather than reimplemented. `reassigned` and `closed_unscored`
    rounds are listed but contribute no score to the average/variance unless
    they later received a late scorecard and transitioned to `scored`."""

    candidate_id: int
    rounds: list[RoundConsolidationOut]
    average_score: float | None
    variance: float | None
    split_decision: bool


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

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.models.candidate import CandidateStatus
from app.schemas.candidate import CandidateOut
from app.schemas.question import QuestionOut


class ScoreSubmission(BaseModel):
    question_id: int
    # Deliberately not `Field(ge=1, le=5)`: an out-of-range score must surface as a
    # 400 from submit_scores' own validation (per spec), not a 422 from pydantic.
    score: int
    comment: str | None = None


class ScoreSubmitRequest(BaseModel):
    scores: list[ScoreSubmission]


class InterviewScoreOut(BaseModel):
    id: int
    candidate_id: int
    question_id: int
    score: int
    comment: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class InterviewerCandidateDetail(BaseModel):
    id: int
    full_name: str
    email: str | None
    phone: str | None
    position_id: int
    status: CandidateStatus
    round_id: int | None
    questions: list[QuestionOut]
    scores: list[InterviewScoreOut]


class InterviewerQueueRow(BaseModel):
    """One row of the `/my-candidates` portal (ticket #33) — round-scoped, not
    candidate-scoped: the query is submission authorization's shape
    (assignee_id = me, status in {open, closed_unscored}), matching #26
    exactly. `scheduled_at` and `scorecard_due_at` are both rendered by the
    frontend in the interviewer's own User.timezone, not browser-local — see
    ticket #29."""

    round_id: int
    candidate_id: int
    candidate_full_name: str
    stage_name: str
    scheduled_at: datetime | None
    brief: str | None
    scorecard_due_at: datetime | None
    state: Literal["needs_scheduling", "scheduled", "overdue"]
    is_closed_unscored: bool
    # Only set when is_closed_unscored: the stage the candidate has since
    # moved to, for row copy that names the move rather than using generic
    # overdue language. None if the candidate's next round hasn't been
    # created yet, or terminal-stage lookup found nothing.
    next_stage_name: str | None

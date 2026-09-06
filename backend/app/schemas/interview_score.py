from datetime import datetime

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


class MyCandidateOut(CandidateOut):
    """CandidateOut plus the interviewer-portal-only scorecard_due_at, derived
    from the interviewer's own open round (not stored). Rendered by the
    frontend in the interviewer's own User.timezone, not browser-local —
    see ticket #29."""

    scorecard_due_at: datetime | None

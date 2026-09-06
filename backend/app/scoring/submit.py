from fastapi import HTTPException, status
from sqlalchemy.orm import Session as DBSession

from app.models.candidate import Candidate, CandidateStatus
from app.models.interview_score import InterviewScore
from app.models.question import Question
from app.models.round import Round, RoundStatus
from app.schemas.interview_score import ScoreSubmission

_SCOREABLE_ROUND_STATUSES = (RoundStatus.open, RoundStatus.closed_unscored)


def submit_scores(
    db: DBSession, round_id: int, interviewer_id: int, submissions: list[ScoreSubmission]
) -> Candidate:
    """Validate and atomically write every Score for a Round, transitioning that
    Round to `scored` in the same transaction. Raises HTTPException (404/409/400)
    and writes nothing on any failure. Locks the Round row to serialize concurrent
    submits against the same round.

    Submission authorization is scoped to this specific round_id, not to the
    candidate: does this round belong to this interviewer as assignee, and does
    it not already have a scorecard (status open or closed_unscored — a
    closed_unscored round with nothing submitted yet is exactly the
    round-1-late-submission case this must support, so it is not disqualifying).
    This is deliberately a third, independent query from both
    `compute_current_owner` and `interviewer_has_access` in app.pipeline.access
    — it does not call either of them.

    The ownership check and the status check both read off this single locked
    fetch — there is deliberately no earlier unlocked read of the same Round in
    this session first. An earlier `db.get()` would populate SQLAlchemy's
    identity map, and a subsequent `with_for_update()` query does not refresh
    already-loaded attributes by default, so a second, concurrent request could
    observe a stale `status` even after its row lock is granted and would
    silently emit a duplicate write / uncaught IntegrityError instead of the
    intended 409."""

    round_ = db.query(Round).filter(Round.id == round_id).populate_existing().with_for_update().first()
    if round_ is None or round_.assignee_id != interviewer_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Round not found.")

    if round_.status not in _SCOREABLE_ROUND_STATUSES:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This round has already been scored.")

    existing_score = db.query(InterviewScore.id).filter(InterviewScore.round_id == round_.id).first()
    if existing_score is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This round has already been scored.")

    candidate = db.get(Candidate, round_.candidate_id)
    if candidate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Round not found.")

    expected_question_ids = {
        question_id
        for (question_id,) in db.query(Question.id).filter(Question.position_id == candidate.position_id).all()
    }

    submitted_ids = [s.question_id for s in submissions]
    submitted_id_set = set(submitted_ids)

    if len(submitted_ids) != len(submitted_id_set):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Duplicate question_id in submission.")

    missing = expected_question_ids - submitted_id_set
    extra = submitted_id_set - expected_question_ids
    if missing or extra:
        parts = []
        if missing:
            parts.append(f"missing question_id(s) {sorted(missing)}")
        if extra:
            parts.append(f"unknown question_id(s) {sorted(extra)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Submitted questions do not match the position's question set: {', '.join(parts)}.",
        )

    for submission in submissions:
        if not (1 <= submission.score <= 5):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"score {submission.score} for question_id {submission.question_id} is out of range 1-5.",
            )

    for submission in submissions:
        db.add(
            InterviewScore(
                candidate_id=candidate.id,
                round_id=round_.id,
                question_id=submission.question_id,
                score=submission.score,
                comment=submission.comment,
            )
        )
    round_.status = RoundStatus.scored
    candidate.status = CandidateStatus.completed
    db.commit()
    db.refresh(candidate)
    return candidate

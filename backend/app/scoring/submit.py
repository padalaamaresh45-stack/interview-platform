from fastapi import HTTPException, status
from sqlalchemy.orm import Session as DBSession

from app.models.candidate import Candidate, CandidateStatus
from app.models.interview_score import InterviewScore
from app.models.question import Question
from app.schemas.interview_score import ScoreSubmission


def submit_scores(
    db: DBSession, candidate_id: int, interviewer_id: int, submissions: list[ScoreSubmission]
) -> Candidate:
    """Validate and atomically write every Score for a Candidate, flipping status to
    completed in the same transaction. Raises HTTPException (404/409/400) and writes
    nothing on any failure. Locks the Candidate row to serialize concurrent submits
    against the same candidate.

    The ownership check and the status check both read off this single locked fetch
    — there is deliberately no earlier unlocked read of the same Candidate in this
    session first. An earlier `db.get()` would populate SQLAlchemy's identity map,
    and a subsequent `with_for_update()` query does not refresh already-loaded
    attributes by default, so a second, concurrent request could observe a stale
    `status` even after its row lock is granted and would silently emit a duplicate
    write / uncaught IntegrityError instead of the intended 409."""

    candidate = (
        db.query(Candidate).filter(Candidate.id == candidate_id).populate_existing().with_for_update().first()
    )
    if candidate is None or candidate.interviewer_id != interviewer_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found.")

    if candidate.status == CandidateStatus.completed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="This candidate has already been submitted."
        )

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
                question_id=submission.question_id,
                score=submission.score,
                comment=submission.comment,
            )
        )
    candidate.status = CandidateStatus.completed
    db.commit()
    db.refresh(candidate)
    return candidate

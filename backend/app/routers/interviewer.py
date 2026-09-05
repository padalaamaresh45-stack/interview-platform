from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session as DBSession

from app.auth.dependencies import require_interviewer
from app.database import get_db
from app.models.candidate import Candidate, CandidateStatus
from app.models.interview_score import InterviewScore
from app.models.question import Question
from app.models.user import User
from app.schemas.candidate import CandidateOut
from app.schemas.interview_score import InterviewerCandidateDetail, ScoreSubmitRequest
from app.scoring.submit import submit_scores

router = APIRouter(prefix="/api/interviewer/candidates", tags=["interviewer"])


def _get_own_candidate_or_404(db: DBSession, candidate_id: int, interviewer: User) -> Candidate:
    candidate = db.get(Candidate, candidate_id)
    if candidate is None or candidate.interviewer_id != interviewer.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found.")
    return candidate


@router.get("", response_model=list[CandidateOut])
def list_my_candidates(
    db: DBSession = Depends(get_db),
    interviewer: User = Depends(require_interviewer),
):
    return (
        db.query(Candidate)
        .filter(Candidate.interviewer_id == interviewer.id, Candidate.status == CandidateStatus.not_started)
        .order_by(Candidate.id)
        .all()
    )


@router.get("/{candidate_id}", response_model=InterviewerCandidateDetail)
def get_my_candidate(
    candidate_id: int,
    db: DBSession = Depends(get_db),
    interviewer: User = Depends(require_interviewer),
):
    candidate = _get_own_candidate_or_404(db, candidate_id, interviewer)
    questions = (
        db.query(Question)
        .filter(Question.position_id == candidate.position_id)
        .order_by(Question.sequence_order)
        .all()
    )
    scores = db.query(InterviewScore).filter(InterviewScore.candidate_id == candidate.id).all()
    return InterviewerCandidateDetail(
        id=candidate.id,
        full_name=candidate.full_name,
        email=candidate.email,
        phone=candidate.phone,
        position_id=candidate.position_id,
        status=candidate.status,
        questions=questions,
        scores=scores,
    )


@router.post("/{candidate_id}/scores", response_model=CandidateOut)
def submit_candidate_scores(
    candidate_id: int,
    payload: ScoreSubmitRequest,
    db: DBSession = Depends(get_db),
    interviewer: User = Depends(require_interviewer),
):
    # Ownership and the completed-status check both happen inside submit_scores'
    # single locked fetch of the Candidate — no separate unlocked read of the same
    # row happens first in this session/request. See submit_scores' docstring for
    # why an earlier read here would be a correctness bug, not just redundant.
    return submit_scores(db, candidate_id, interviewer.id, payload.scores)

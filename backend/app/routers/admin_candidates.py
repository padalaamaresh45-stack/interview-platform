from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session as DBSession

from app.auth.dependencies import require_admin
from app.database import get_db
from app.models.candidate import Candidate, CandidateStatus
from app.models.position import Position
from app.models.question import Question
from app.models.user import User, UserRole
from app.schemas.candidate import CandidateCreate, CandidateOut, CandidateUpdate, InterviewerOut

router = APIRouter(prefix="/api/admin/candidates", tags=["admin-candidates"])

interviewers_router = APIRouter(prefix="/api/admin/interviewers", tags=["admin-candidates"])


def _get_candidate_or_404(db: DBSession, candidate_id: int) -> Candidate:
    candidate = db.get(Candidate, candidate_id)
    if candidate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found.")
    return candidate


@router.post("", response_model=CandidateOut, status_code=status.HTTP_201_CREATED)
def create_candidate(
    payload: CandidateCreate,
    db: DBSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    position = db.get(Position, payload.position_id)
    if position is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Position not found.")

    question_count = db.query(func.count(Question.id)).filter(Question.position_id == position.id).scalar()
    if question_count == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot create a candidate against a position with zero questions.",
        )

    interviewer = db.get(User, payload.interviewer_id)
    if interviewer is None or interviewer.role != UserRole.interviewer:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="interviewer_id must reference an interviewer.")

    candidate = Candidate(
        full_name=payload.full_name,
        email=payload.email,
        phone=payload.phone,
        position_id=payload.position_id,
        interviewer_id=payload.interviewer_id,
        created_by=admin.id,
    )
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    return candidate


@router.get("", response_model=list[CandidateOut])
def list_candidates(
    db: DBSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    return db.query(Candidate).order_by(Candidate.id).all()


@router.get("/{candidate_id}", response_model=CandidateOut)
def get_candidate(
    candidate_id: int,
    db: DBSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    return _get_candidate_or_404(db, candidate_id)


@router.patch("/{candidate_id}", response_model=CandidateOut)
def update_candidate(
    candidate_id: int,
    payload: CandidateUpdate,
    db: DBSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    candidate = _get_candidate_or_404(db, candidate_id)
    updates = payload.model_dump(exclude_unset=True)

    if "interviewer_id" in updates:
        if candidate.status != CandidateStatus.not_started:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot reassign the interviewer once the candidate is completed.",
            )
        interviewer = db.get(User, updates["interviewer_id"])
        if interviewer is None or interviewer.role != UserRole.interviewer:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="interviewer_id must reference an interviewer."
            )
        candidate.interviewer_id = updates["interviewer_id"]

    if "full_name" in updates:
        candidate.full_name = updates["full_name"]
    if "email" in updates:
        candidate.email = updates["email"]
    if "phone" in updates:
        candidate.phone = updates["phone"]

    db.commit()
    db.refresh(candidate)
    return candidate


@router.delete("/{candidate_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_candidate(
    candidate_id: int,
    db: DBSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    candidate = _get_candidate_or_404(db, candidate_id)
    if candidate.status != CandidateStatus.not_started:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete a candidate once they are completed.",
        )
    db.delete(candidate)
    db.commit()
    return None


@interviewers_router.get("", response_model=list[InterviewerOut])
def list_active_interviewers(
    db: DBSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    return (
        db.query(User)
        .filter(User.role == UserRole.interviewer, User.is_active.is_(True))
        .order_by(User.full_name)
        .all()
    )

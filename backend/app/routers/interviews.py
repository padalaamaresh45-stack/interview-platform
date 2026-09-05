from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session as DBSession

from app.auth.dependencies import require_admin, require_interviewer
from app.database import get_db
from app.models.candidate import Candidate
from app.models.interview import Interview
from app.models.position import Position
from app.models.user import User, UserRole
from app.schemas.interview import InterviewCreate, InterviewOut

router = APIRouter(tags=["interviews"])


def _to_out(db: DBSession, interview: Interview) -> InterviewOut:
    candidate = db.get(Candidate, interview.candidate_id)
    interviewer = db.get(User, interview.interviewer_id)
    position = db.get(Position, candidate.position_id) if candidate else None
    return InterviewOut(
        id=interview.id,
        candidate_id=interview.candidate_id,
        candidate_name=candidate.full_name if candidate else f"#{interview.candidate_id}",
        position_title=position.title if position else "—",
        interviewer_id=interview.interviewer_id,
        interviewer_name=interviewer.full_name if interviewer else f"#{interview.interviewer_id}",
        scheduled_at=interview.scheduled_at,
        duration_minutes=interview.duration_minutes,
        notes=interview.notes,
        created_at=interview.created_at,
    )


@router.post("/api/admin/interviews", response_model=InterviewOut, status_code=status.HTTP_201_CREATED)
def schedule_interview(
    payload: InterviewCreate,
    db: DBSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    candidate = db.get(Candidate, payload.candidate_id)
    if candidate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found.")

    interviewer = db.get(User, payload.interviewer_id)
    if interviewer is None or interviewer.role != UserRole.interviewer:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="interviewer_id must reference an interviewer."
        )

    interview = Interview(
        candidate_id=payload.candidate_id,
        interviewer_id=payload.interviewer_id,
        scheduled_at=payload.scheduled_at,
        duration_minutes=payload.duration_minutes,
        notes=payload.notes,
        created_by=admin.id,
    )
    db.add(interview)
    db.commit()
    db.refresh(interview)
    return _to_out(db, interview)


@router.get("/api/admin/interviews", response_model=list[InterviewOut])
def list_all_interviews(
    db: DBSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    # Admin sees the whole calendar — every scheduled interview across every
    # interviewer and candidate. This is the "admin controls the whole thing"
    # half of the split; list_my_interviews below is the other half.
    interviews = db.query(Interview).order_by(Interview.scheduled_at).all()
    return [_to_out(db, i) for i in interviews]


@router.delete("/api/admin/interviews/{interview_id}", status_code=status.HTTP_204_NO_CONTENT)
def cancel_interview(
    interview_id: int,
    db: DBSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    interview = db.get(Interview, interview_id)
    if interview is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interview not found.")
    db.delete(interview)
    db.commit()
    return None


@router.get("/api/interviewer/interviews", response_model=list[InterviewOut])
def list_my_interviews(
    db: DBSession = Depends(get_db),
    interviewer: User = Depends(require_interviewer),
):
    # Scoped to this interviewer only — they can never see another
    # interviewer's schedule or another interviewer's candidates here.
    interviews = (
        db.query(Interview)
        .filter(Interview.interviewer_id == interviewer.id)
        .order_by(Interview.scheduled_at)
        .all()
    )
    return [_to_out(db, i) for i in interviews]

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as DBSession

from app.auth.dependencies import require_interviewer
from app.database import get_db
from app.models.candidate import Candidate, CandidateStatus
from app.models.user import User
from app.schemas.candidate import CandidateOut

router = APIRouter(prefix="/api/interviewer/candidates", tags=["interviewer"])


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

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session as DBSession

from app.auth.dependencies import require_admin
from app.database import get_db
from app.models.candidate import Candidate
from app.models.interview import Interview
from app.models.stage import Stage
from app.models.user import User, UserRole
from app.pipeline.rounds import close_and_open_round
from app.schemas.round import RoundAssignRequest, RoundOut

router = APIRouter(prefix="/api/admin", tags=["rounds"])


@router.post("/candidates/{candidate_id}/rounds", response_model=RoundOut, status_code=status.HTTP_201_CREATED)
def assign_round(
    candidate_id: int,
    payload: RoundAssignRequest,
    db: DBSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Assign a candidate's next Round and, if scheduling fields were
    supplied, its Interview — one atomic write (ticket #28). Closing any
    still-open prior round is #27's shared helper; this endpoint only adds
    the optional Interview on top, inside the same transaction."""
    candidate = db.get(Candidate, candidate_id)
    if candidate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found.")

    stage = db.get(Stage, payload.stage_id)
    if stage is None or stage.position_id != candidate.position_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="stage_id must reference a stage belonging to the candidate's position.",
        )

    assignee = db.get(User, payload.assignee_id)
    if assignee is None or assignee.role != UserRole.interviewer:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="assignee_id must reference an interviewer.",
        )

    new_round = close_and_open_round(
        db,
        candidate_id=candidate.id,
        new_stage_id=stage.id,
        new_assignee_id=assignee.id,
        assignment_due_at=payload.assignment_due_at,
        brief=payload.brief,
    )

    interview = None
    if payload.scheduled_at is not None:
        interview = Interview(
            candidate_id=candidate.id,
            round_id=new_round.id,
            scheduled_at=payload.scheduled_at,
            duration_minutes=payload.duration_minutes,
            notes=payload.notes,
            created_by=admin.id,
        )
        db.add(interview)
        db.flush()

    db.commit()
    db.refresh(new_round)

    return RoundOut(
        id=new_round.id,
        candidate_id=new_round.candidate_id,
        stage_id=new_round.stage_id,
        assignee_id=new_round.assignee_id,
        status=new_round.status,
        assignment_due_at=new_round.assignment_due_at,
        brief=new_round.brief,
        reassigned_from_round_id=new_round.reassigned_from_round_id,
        created_at=new_round.created_at,
        closed_at=new_round.closed_at,
        interview_id=interview.id if interview is not None else None,
    )

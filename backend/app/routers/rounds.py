from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session as DBSession

from app.auth.dependencies import require_admin
from app.database import get_db
from app.models.candidate import Candidate
from app.models.interview import Interview
from app.models.round import Round, RoundStatus
from app.models.stage import Stage
from app.models.user import User, UserRole
from app.pipeline.access import get_open_round
from app.pipeline.rounds import close_and_open_round
from app.pipeline.stage_transitions import record_stage_transition
from app.schemas.round import ReassignRequest, RoundAssignRequest, RoundOut

router = APIRouter(prefix="/api/admin", tags=["rounds"])


def _round_to_out(round_: Round, interview_id: int | None) -> RoundOut:
    return RoundOut(
        id=round_.id,
        candidate_id=round_.candidate_id,
        stage_id=round_.stage_id,
        assignee_id=round_.assignee_id,
        status=round_.status,
        assignment_due_at=round_.assignment_due_at,
        brief=round_.brief,
        reassigned_from_round_id=round_.reassigned_from_round_id,
        created_at=round_.created_at,
        closed_at=round_.closed_at,
        interview_id=interview_id,
    )


def _get_interviewer_or_400(db: DBSession, assignee_id: int) -> User:
    assignee = db.get(User, assignee_id)
    if assignee is None or assignee.role != UserRole.interviewer:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="assignee_id must reference an interviewer.",
        )
    return assignee


@router.post("/candidates/{candidate_id}/rounds", response_model=RoundOut, status_code=status.HTTP_201_CREATED)
def assign_round(
    candidate_id: int,
    payload: RoundAssignRequest,
    db: DBSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Assign a candidate's next Round and, if scheduling fields were
    supplied, its Interview — one atomic write (ticket #28). Closing any
    still-open prior round is #27's shared helper; this endpoint also records
    the matching CandidateStageTransition in the same transaction, so the
    pipeline board's stage column and the round's actual stage can't drift
    apart the way they could before (the board is #16's machinery, the round
    is #27's — record_stage_transition is the one shared write between them,
    same convention as close_and_open_round). The optional Interview is added
    on top, still inside the same transaction."""
    candidate = db.get(Candidate, candidate_id)
    if candidate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found.")

    stage = db.get(Stage, payload.stage_id)
    if stage is None or stage.position_id != candidate.position_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="stage_id must reference a stage belonging to the candidate's position.",
        )

    assignee = _get_interviewer_or_400(db, payload.assignee_id)

    new_round = close_and_open_round(
        db,
        candidate_id=candidate.id,
        new_stage_id=stage.id,
        new_assignee_id=assignee.id,
        assignment_due_at=payload.assignment_due_at,
        brief=payload.brief,
    )
    record_stage_transition(db, candidate, stage, admin.id)

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

    return _round_to_out(new_round, interview.id if interview is not None else None)


@router.post("/candidates/{candidate_id}/rounds/reassign", response_model=RoundOut, status_code=status.HTTP_201_CREATED)
def reassign_round(
    candidate_id: int,
    payload: ReassignRequest,
    db: DBSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """Reassign the candidate's currently open round to a new interviewer.
    Never mutates the open Round's assignee_id — closes it as `reassigned`
    and opens a new Round for the same stage via #27's shared helper (ticket
    #30). Any scheduled Interview on the closed round is left untouched;
    cancelling it is a separate admin action."""
    candidate = db.get(Candidate, candidate_id)
    if candidate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found.")

    open_round = get_open_round(db, candidate_id)
    if open_round is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Candidate has no open round to reassign.",
        )

    assignee = _get_interviewer_or_400(db, payload.assignee_id)

    new_round = close_and_open_round(
        db,
        candidate_id=candidate.id,
        new_stage_id=open_round.stage_id,
        new_assignee_id=assignee.id,
        assignment_due_at=open_round.assignment_due_at,
        brief=open_round.brief,
        prior_round_closed_status=RoundStatus.reassigned,
        reassigned_from_round_id=open_round.id,
    )
    db.commit()
    db.refresh(new_round)

    return _round_to_out(new_round, None)

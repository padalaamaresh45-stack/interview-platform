from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session as DBSession

from app.auth.dependencies import require_interviewer
from app.database import get_db
from app.models.candidate import Candidate
from app.models.interview import Interview, InterviewStatus
from app.models.interview_score import InterviewScore
from app.models.question import Question
from app.models.round import Round, RoundStatus
from app.models.stage import Stage
from app.models.stage_transition import CandidateStageTransition
from app.models.user import User
from app.pipeline.access import candidate_to_out, interviewer_has_access
from app.pipeline.derive import compute_queue_state, compute_scorecard_due_at
from app.schemas.candidate import CandidateOut
from app.schemas.interview_score import InterviewerCandidateDetail, InterviewerQueueRow, ScoreSubmitRequest
from app.scoring.submit import submit_scores

router = APIRouter(prefix="/api/interviewer/candidates", tags=["interviewer"])
rounds_router = APIRouter(prefix="/api/interviewer/rounds", tags=["interviewer"])


def _get_own_candidate_or_404(db: DBSession, candidate_id: int, interviewer: User) -> Candidate:
    candidate = db.get(Candidate, candidate_id)
    if candidate is None or not interviewer_has_access(db, candidate_id, interviewer.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found.")
    return candidate


@router.get("", response_model=list[InterviewerQueueRow])
def list_my_candidates(
    db: DBSession = Depends(get_db),
    interviewer: User = Depends(require_interviewer),
):
    # Submission-authorization's exact shape (see app.scoring.submit's
    # _SCOREABLE_ROUND_STATUSES), not the ownership query and not a filter on
    # Candidate.status: a candidate can already be `completed` (advanced past
    # this stage) while this round is still `closed_unscored` and this
    # interviewer still owes a scorecard for it — that combination must not be
    # filtered out here.
    rows = (
        db.query(Round, Candidate)
        .join(Candidate, Candidate.id == Round.candidate_id)
        .filter(
            Round.assignee_id == interviewer.id,
            Round.status.in_((RoundStatus.open, RoundStatus.closed_unscored)),
        )
        .all()
    )
    now = datetime.now(timezone.utc)
    results = []
    for round_, candidate in rows:
        stage = db.get(Stage, round_.stage_id)
        interview = (
            db.query(Interview)
            .filter(Interview.round_id == round_.id, Interview.status == InterviewStatus.scheduled)
            .first()
        )
        scheduled_at = None
        scorecard_due_at = None
        if interview is not None:
            scheduled_at = interview.scheduled_at
            interview_end_at = interview.scheduled_at + timedelta(minutes=interview.duration_minutes)
            scorecard_due_at = compute_scorecard_due_at(interview_end_at, stage.feedback_grace_hours)

        state = compute_queue_state(
            round_status=round_.status,
            has_active_interview=interview is not None,
            scorecard_due_at=scorecard_due_at,
            now=now,
        )

        next_stage_name = None
        if round_.status == RoundStatus.closed_unscored:
            # The stage this specific round's closure moved the candidate
            # into — the earliest transition *away from this round's own
            # stage*, not the candidate's current stage. A candidate can have
            # advanced more than once since, or been rejected, since this
            # round closed; using "most recent transition" would then name
            # the wrong (or a terminal) stage instead of what this round's
            # own advancement actually led to.
            departing_transition = (
                db.query(CandidateStageTransition)
                .filter(
                    CandidateStageTransition.candidate_id == candidate.id,
                    CandidateStageTransition.from_stage_id == round_.stage_id,
                )
                .order_by(CandidateStageTransition.created_at.asc(), CandidateStageTransition.id.asc())
                .first()
            )
            if departing_transition is not None:
                next_stage = db.get(Stage, departing_transition.to_stage_id)
                next_stage_name = next_stage.name if next_stage else None

        results.append(
            InterviewerQueueRow(
                round_id=round_.id,
                candidate_id=candidate.id,
                candidate_full_name=candidate.full_name,
                stage_name=stage.name if stage is not None else "",
                scheduled_at=scheduled_at,
                brief=round_.brief,
                scorecard_due_at=scorecard_due_at,
                state=state,
                is_closed_unscored=round_.status == RoundStatus.closed_unscored,
                next_stage_name=next_stage_name,
            )
        )

    # Soonest due date first; rows with no due date at all have nothing to
    # sort on and trail the list — but within that trailing group, an overdue
    # row (a closed_unscored round whose Interview record is gone, so no due
    # date could be computed) still outranks a merely unscheduled one, since
    # it already represents owed feedback rather than a not-yet-started task.
    results.sort(key=lambda r: (r.scorecard_due_at is None, r.scorecard_due_at, r.state != "overdue", r.round_id))
    return results


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
    # This interviewer's own round for this candidate — prefer their open one
    # (the one they're meant to be scoring right now); otherwise their most
    # recent one. A candidate can have more than one round across stages
    # (re-interviewed), and scores are per-round now, so this must not fall
    # back to every score ever recorded for the candidate across every
    # interviewer's rounds.
    my_round = (
        db.query(Round)
        .filter(Round.candidate_id == candidate.id, Round.assignee_id == interviewer.id)
        .order_by((Round.status == RoundStatus.open).desc(), Round.created_at.desc())
        .first()
    )
    scores = (
        db.query(InterviewScore).filter(InterviewScore.round_id == my_round.id).all() if my_round is not None else []
    )
    return InterviewerCandidateDetail(
        id=candidate.id,
        full_name=candidate.full_name,
        email=candidate.email,
        phone=candidate.phone,
        position_id=candidate.position_id,
        status=candidate.status,
        round_id=(
            my_round.id
            if my_round is not None and my_round.status in (RoundStatus.open, RoundStatus.closed_unscored)
            else None
        ),
        questions=questions,
        scores=scores,
    )


@rounds_router.post("/{round_id}/scores", response_model=CandidateOut)
def submit_round_scores(
    round_id: int,
    payload: ScoreSubmitRequest,
    db: DBSession = Depends(get_db),
    interviewer: User = Depends(require_interviewer),
):
    # Ownership and the already-scored check both happen inside submit_scores'
    # single locked fetch of the Round — no separate unlocked read of the same
    # row happens first in this session/request. See submit_scores' docstring
    # for why an earlier read here would be a correctness bug, not just
    # redundant.
    candidate = submit_scores(db, round_id, interviewer.id, payload.scores)
    return candidate_to_out(db, candidate)

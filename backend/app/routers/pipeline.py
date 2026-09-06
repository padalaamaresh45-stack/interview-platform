from sqlalchemy import func
from sqlalchemy.orm import Session as DBSession
from fastapi import APIRouter, Depends, HTTPException, status

from app.auth.dependencies import require_admin
from app.database import get_db
from app.models.candidate import Candidate
from app.models.interview import Interview, InterviewStatus
from app.models.interview_score import InterviewScore
from app.models.position import Position
from app.models.question import Question
from app.models.round import Round, RoundStatus
from app.models.stage import Stage
from app.models.stage_transition import CandidateStageTransition
from app.models.user import User
from app.pipeline.access import get_open_rounds
from app.pipeline.derive import (
    compute_current_owner,
    compute_gap_state,
    compute_score_variance,
    derive_candidate_fields,
    is_split_decision,
)
from app.pipeline.stage_transitions import latest_transitions_by_candidate, record_stage_transition
from app.schemas.pipeline import (
    BoardCandidateOut,
    BoardColumnOut,
    BoardOut,
    CandidateHistoryOut,
    ConsolidationOut,
    MoveCandidateRequest,
    RoundConsolidationOut,
    ScoreSummaryOut,
    StageOut,
    StageTransitionOut,
)

router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])


def _get_candidate_or_404(db: DBSession, candidate_id: int) -> Candidate:
    candidate = db.get(Candidate, candidate_id)
    if candidate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found.")
    return candidate


def _question_counts_by_position(db: DBSession, position_ids: list[int]) -> dict[int, int]:
    if not position_ids:
        return {}
    rows = (
        db.query(Question.position_id, func.count(Question.id))
        .filter(Question.position_id.in_(position_ids))
        .group_by(Question.position_id)
        .all()
    )
    return dict(rows)


def _scores_by_candidate(db: DBSession, candidate_ids: list[int]) -> dict[int, list[InterviewScore]]:
    if not candidate_ids:
        return {}
    rows = db.query(InterviewScore).filter(InterviewScore.candidate_id.in_(candidate_ids)).all()
    by_candidate: dict[int, list[InterviewScore]] = {}
    for row in rows:
        by_candidate.setdefault(row.candidate_id, []).append(row)
    return by_candidate


def _round_ids_with_active_interview(db: DBSession, round_ids: list[int]) -> set[int]:
    if not round_ids:
        return set()
    rows = (
        db.query(Interview.round_id)
        .filter(Interview.round_id.in_(round_ids), Interview.status != InterviewStatus.cancelled)
        .all()
    )
    return {row[0] for row in rows}


def _latest_closed_round_by_candidate(db: DBSession, candidate_ids: list[int]) -> dict[int, Round]:
    """The most recently closed Round per candidate (any non-open status) —
    feeds compute_gap_state's "did the last round score, or fall away
    unscored/reassigned" branch. Ordered by closed_at then id so two rounds
    closed in the same instant still resolve deterministically."""
    if not candidate_ids:
        return {}
    rows = (
        db.query(Round)
        .filter(Round.candidate_id.in_(candidate_ids), Round.status != RoundStatus.open)
        .order_by(Round.candidate_id, Round.closed_at.desc(), Round.id.desc())
        .all()
    )
    latest: dict[int, Round] = {}
    for row in rows:
        latest.setdefault(row.candidate_id, row)
    return latest


def _average_score_by_round(db: DBSession, round_ids: list[int]) -> dict[int, float]:
    if not round_ids:
        return {}
    rows = (
        db.query(InterviewScore.round_id, func.avg(InterviewScore.score))
        .filter(InterviewScore.round_id.in_(round_ids))
        .group_by(InterviewScore.round_id)
        .all()
    )
    return {round_id: float(avg) for round_id, avg in rows}


@router.get("/stages", response_model=list[StageOut])
def list_stages(
    position_id: int,
    db: DBSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    return (
        db.query(Stage)
        .filter(Stage.position_id == position_id)
        .order_by(Stage.sequence_order)
        .all()
    )


@router.get("/board", response_model=BoardOut)
def get_board(
    position_id: int | None = None,
    db: DBSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    stage_query = db.query(Stage)
    if position_id is not None:
        stage_query = stage_query.filter(Stage.position_id == position_id)
    stages = stage_query.order_by(Stage.position_id, Stage.sequence_order).all()

    candidate_query = db.query(Candidate)
    if position_id is not None:
        candidate_query = candidate_query.filter(Candidate.position_id == position_id)
    candidates = candidate_query.all()

    positions = {p.id: p for p in db.query(Position).all()}
    latest_transitions = latest_transitions_by_candidate(db, [c.id for c in candidates])
    question_counts = _question_counts_by_position(db, list(positions.keys()))
    scores_by_candidate = _scores_by_candidate(db, [c.id for c in candidates])
    open_rounds = get_open_rounds(db, [c.id for c in candidates])
    active_interview_round_ids = _round_ids_with_active_interview(
        db, [r.id for r in open_rounds.values()]
    )
    latest_closed_round_by_candidate = _latest_closed_round_by_candidate(db, [c.id for c in candidates])
    average_score_by_round = _average_score_by_round(
        db, [r.id for r in latest_closed_round_by_candidate.values()]
    )

    columns: dict[int, list[BoardCandidateOut]] = {stage.id: [] for stage in stages}
    for candidate in candidates:
        transition = latest_transitions.get(candidate.id)
        if transition is None:
            # A candidate with no transition row has never entered the pipeline
            # (a data gap, not a valid state) — exclude rather than guess a stage.
            continue
        stage = next((s for s in stages if s.id == transition.to_stage_id), None)
        if stage is None:
            continue
        derived = derive_candidate_fields(
            candidate_status=candidate.status,
            current_stage_id=stage.id,
            current_stage_name=stage.name,
            stage_day_limit=stage.day_limit,
            is_terminal=stage.is_terminal,
            entered_stage_at=transition.created_at,
            scores=scores_by_candidate.get(candidate.id, []),
            total_questions=question_counts.get(candidate.position_id, 0),
            hold_reason=candidate.hold_reason,
        )
        position = positions.get(candidate.position_id)
        open_round = open_rounds.get(candidate.id)
        latest_closed_round = latest_closed_round_by_candidate.get(candidate.id)
        gap_state = compute_gap_state(
            is_terminal=stage.is_terminal,
            hold_reason=candidate.hold_reason,
            has_open_round=open_round is not None,
            open_round_has_active_interview=(
                open_round is not None and open_round.id in active_interview_round_ids
            ),
            latest_closed_round_status=latest_closed_round.status if latest_closed_round else None,
            latest_round_average_score=(
                average_score_by_round.get(latest_closed_round.id) if latest_closed_round else None
            ),
            advance_threshold=stage.advance_threshold,
        )
        columns.setdefault(stage.id, []).append(
            BoardCandidateOut(
                id=candidate.id,
                full_name=candidate.full_name,
                position_id=candidate.position_id,
                position_title=position.title if position else f"#{candidate.position_id}",
                owner_id=compute_current_owner(open_rounds.get(candidate.id)),
                status=candidate.status,
                current_stage_id=stage.id,
                days_in_stage=derived.days_in_stage,
                health=derived.health,
                next_action=derived.next_action,
                gap_state=gap_state,
                score=ScoreSummaryOut(
                    submitted_count=derived.score.submitted_count,
                    total_count=derived.score.total_count,
                    average=derived.score.average,
                ),
            )
        )

    return BoardOut(
        columns=[
            BoardColumnOut(stage=StageOut.model_validate(stage), candidates=columns.get(stage.id, []))
            for stage in stages
        ]
    )


def _build_candidate_history(db: DBSession, candidate: Candidate) -> CandidateHistoryOut:
    position = db.get(Position, candidate.position_id)
    transitions = (
        db.query(CandidateStageTransition)
        .filter(CandidateStageTransition.candidate_id == candidate.id)
        .order_by(CandidateStageTransition.created_at.desc(), CandidateStageTransition.id.desc())
        .all()
    )
    if not transitions:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Candidate has no pipeline history."
        )

    stage_ids = {t.to_stage_id for t in transitions} | {t.from_stage_id for t in transitions if t.from_stage_id}
    stages = {s.id: s for s in db.query(Stage).filter(Stage.id.in_(stage_ids)).all()}
    actor_ids = {t.actor_id for t in transitions}
    actors = {u.id: u for u in db.query(User).filter(User.id.in_(actor_ids)).all()}

    current_stage = stages[transitions[0].to_stage_id]
    question_count = db.query(func.count(Question.id)).filter(Question.position_id == candidate.position_id).scalar()
    scores = db.query(InterviewScore).filter(InterviewScore.candidate_id == candidate.id).order_by(InterviewScore.id).all()

    derived = derive_candidate_fields(
        candidate_status=candidate.status,
        current_stage_id=current_stage.id,
        current_stage_name=current_stage.name,
        stage_day_limit=current_stage.day_limit,
        is_terminal=current_stage.is_terminal,
        entered_stage_at=transitions[0].created_at,
        scores=scores,
        total_questions=question_count,
        hold_reason=candidate.hold_reason,
    )

    stage_history = [
        StageTransitionOut(
            id=t.id,
            from_stage_id=t.from_stage_id,
            from_stage_name=stages[t.from_stage_id].name if t.from_stage_id else None,
            to_stage_id=t.to_stage_id,
            to_stage_name=stages[t.to_stage_id].name,
            actor_id=t.actor_id,
            actor_name=actors[t.actor_id].full_name if t.actor_id in actors else f"#{t.actor_id}",
            created_at=t.created_at,
        )
        for t in transitions
    ]

    return CandidateHistoryOut(
        id=candidate.id,
        full_name=candidate.full_name,
        position_id=candidate.position_id,
        position_title=position.title if position else f"#{candidate.position_id}",
        status=candidate.status,
        current_stage_id=current_stage.id,
        current_stage_name=current_stage.name,
        days_in_stage=derived.days_in_stage,
        health=derived.health,
        next_action=derived.next_action,
        score=ScoreSummaryOut(
            submitted_count=derived.score.submitted_count,
            total_count=derived.score.total_count,
            average=derived.score.average,
        ),
        stage_history=stage_history,
        scores=scores,
    )


@router.get("/candidates/{candidate_id}", response_model=CandidateHistoryOut)
def get_candidate_history(
    candidate_id: int,
    db: DBSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    candidate = _get_candidate_or_404(db, candidate_id)
    return _build_candidate_history(db, candidate)


@router.get("/candidates/{candidate_id}/consolidation", response_model=ConsolidationOut)
def get_candidate_consolidation(
    candidate_id: int,
    db: DBSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """Every Round for a candidate, in chronological order, with the shared
    variance/split-decision calculation from #27 — admin-only, by construction
    (this whole router requires require_admin), so it never leaks another
    round's score to the interviewer who owns it. That blind-review guarantee
    for interviewer-facing endpoints lives separately, scoped to each
    interviewer's own Round, in app.routers.interviewer."""
    candidate = _get_candidate_or_404(db, candidate_id)

    rounds = (
        db.query(Round)
        .filter(Round.candidate_id == candidate.id)
        .order_by(Round.created_at, Round.id)
        .all()
    )
    if not rounds:
        return ConsolidationOut(
            candidate_id=candidate.id, rounds=[], average_score=None, variance=None, split_decision=False
        )

    round_ids = [r.id for r in rounds]
    stages = {s.id: s for s in db.query(Stage).filter(Stage.id.in_({r.stage_id for r in rounds})).all()}
    assignees = {u.id: u for u in db.query(User).filter(User.id.in_({r.assignee_id for r in rounds})).all()}
    average_by_round = _average_score_by_round(db, round_ids)
    scores_rows = db.query(InterviewScore).filter(InterviewScore.round_id.in_(round_ids)).order_by(InterviewScore.id).all()
    scores_by_round: dict[int, list[InterviewScore]] = {}
    for s in scores_rows:
        scores_by_round.setdefault(s.round_id, []).append(s)

    round_outs = []
    scored_averages = []
    for r in rounds:
        stage = stages.get(r.stage_id)
        assignee = assignees.get(r.assignee_id)
        avg = average_by_round.get(r.id)
        if r.status == RoundStatus.scored and avg is not None:
            scored_averages.append(avg)
        round_outs.append(
            RoundConsolidationOut(
                id=r.id,
                stage_id=r.stage_id,
                stage_name=stage.name if stage else f"#{r.stage_id}",
                assignee_id=r.assignee_id,
                assignee_name=assignee.full_name if assignee else f"#{r.assignee_id}",
                status=r.status,
                created_at=r.created_at,
                closed_at=r.closed_at,
                average_score=avg if r.status == RoundStatus.scored else None,
                scores=scores_by_round.get(r.id, []),
            )
        )

    average_score = round(sum(scored_averages) / len(scored_averages), 2) if scored_averages else None
    return ConsolidationOut(
        candidate_id=candidate.id,
        rounds=round_outs,
        average_score=average_score,
        variance=compute_score_variance(scored_averages),
        split_decision=is_split_decision(scored_averages),
    )


@router.post("/candidates/{candidate_id}/move", response_model=CandidateHistoryOut)
def move_candidate(
    candidate_id: int,
    payload: MoveCandidateRequest,
    db: DBSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    candidate = _get_candidate_or_404(db, candidate_id)

    to_stage = db.get(Stage, payload.to_stage_id)
    if to_stage is None or to_stage.position_id != candidate.position_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="to_stage_id must reference a stage belonging to the candidate's position.",
        )

    latest = latest_transitions_by_candidate(db, [candidate.id]).get(candidate.id)
    from_stage_id = latest.to_stage_id if latest else None

    if from_stage_id == to_stage.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Candidate is already in that stage.")

    if from_stage_id is not None and not payload.force:
        from_stage = db.get(Stage, from_stage_id)
        if from_stage is not None:
            if from_stage.is_terminal:
                # Leaving a terminal stage always requires force, even to move
                # to another terminal stage (e.g. Hired -> Rejected).
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        f"Candidate is already {from_stage.name}, which is a terminal stage. "
                        "Confirm to move them anyway."
                    ),
                )
            elif to_stage.is_terminal:
                # Moving into a terminal stage from a non-terminal one is always
                # allowed, regardless of sequence_order.
                pass
            elif to_stage.sequence_order < from_stage.sequence_order:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        f"Moving from {from_stage.name} back to {to_stage.name} is a backward move. "
                        "Confirm to move them anyway."
                    ),
                )

    record_stage_transition(db, candidate, to_stage, admin.id)
    db.commit()
    db.refresh(candidate)
    return _build_candidate_history(db, candidate)

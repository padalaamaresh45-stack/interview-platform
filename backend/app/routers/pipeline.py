from sqlalchemy import func
from sqlalchemy.orm import Session as DBSession
from fastapi import APIRouter, Depends, HTTPException, status

from app.auth.dependencies import require_admin
from app.database import get_db
from app.models.candidate import Candidate
from app.models.interview_score import InterviewScore
from app.models.position import Position
from app.models.question import Question
from app.models.stage import Stage
from app.models.stage_transition import CandidateStageTransition
from app.models.user import User
from app.pipeline.derive import derive_candidate_fields
from app.pipeline.stages import TERMINAL_STAGE_NAMES
from app.schemas.pipeline import (
    BoardCandidateOut,
    BoardColumnOut,
    BoardOut,
    CandidateHistoryOut,
    MoveCandidateRequest,
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


def _latest_transitions_by_candidate(
    db: DBSession, candidate_ids: list[int]
) -> dict[int, CandidateStageTransition]:
    """The single query every caller uses to find each candidate's current stage.
    A candidate's current stage is the to_stage of its most recent transition —
    never a stored current_stage column."""
    if not candidate_ids:
        return {}
    rows = (
        db.query(CandidateStageTransition)
        .filter(CandidateStageTransition.candidate_id.in_(candidate_ids))
        .order_by(CandidateStageTransition.candidate_id, CandidateStageTransition.created_at.desc(), CandidateStageTransition.id.desc())
        .all()
    )
    latest: dict[int, CandidateStageTransition] = {}
    for row in rows:
        latest.setdefault(row.candidate_id, row)
    return latest


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
    latest_transitions = _latest_transitions_by_candidate(db, [c.id for c in candidates])
    question_counts = _question_counts_by_position(db, list(positions.keys()))
    scores_by_candidate = _scores_by_candidate(db, [c.id for c in candidates])

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
            entered_stage_at=transition.created_at,
            scores=scores_by_candidate.get(candidate.id, []),
            total_questions=question_counts.get(candidate.position_id, 0),
        )
        position = positions.get(candidate.position_id)
        columns.setdefault(stage.id, []).append(
            BoardCandidateOut(
                id=candidate.id,
                full_name=candidate.full_name,
                position_id=candidate.position_id,
                position_title=position.title if position else f"#{candidate.position_id}",
                interviewer_id=candidate.interviewer_id,
                status=candidate.status,
                current_stage_id=stage.id,
                days_in_stage=derived.days_in_stage,
                health=derived.health,
                next_action=derived.next_action,
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
        entered_stage_at=transitions[0].created_at,
        scores=scores,
        total_questions=question_count,
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

    latest = _latest_transitions_by_candidate(db, [candidate.id]).get(candidate.id)
    from_stage_id = latest.to_stage_id if latest else None

    if from_stage_id == to_stage.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Candidate is already in that stage.")

    if from_stage_id is not None and not payload.force:
        from_stage = db.get(Stage, from_stage_id)
        if from_stage is not None and from_stage.name in TERMINAL_STAGE_NAMES:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Candidate is already {from_stage.name}, which is a terminal stage. "
                    "Confirm to move them anyway."
                ),
            )

    db.add(
        CandidateStageTransition(
            candidate_id=candidate.id,
            from_stage_id=from_stage_id,
            to_stage_id=to_stage.id,
            actor_id=admin.id,
        )
    )
    db.commit()
    db.refresh(candidate)
    return _build_candidate_history(db, candidate)

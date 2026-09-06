"""Single source of truth for writing a CandidateStageTransition row — shared
by `move_candidate` (ticket #16) and the round-advance endpoint
(`assign_round`, ticket #27/#28), so a candidate's stage and their round can
never drift the way `compute_health` and `compute_next_action` once did (see
derive.py's module docstring) — this is the same risk, one call site short of
repeating it."""

from sqlalchemy.orm import Session as DBSession

from app.models.candidate import Candidate
from app.models.stage import Stage
from app.models.stage_transition import CandidateStageTransition


def latest_transitions_by_candidate(
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
        .order_by(
            CandidateStageTransition.candidate_id,
            CandidateStageTransition.created_at.desc(),
            CandidateStageTransition.id.desc(),
        )
        .all()
    )
    latest: dict[int, CandidateStageTransition] = {}
    for row in rows:
        latest.setdefault(row.candidate_id, row)
    return latest


def record_stage_transition(
    db: DBSession, candidate: Candidate, to_stage: Stage, actor_id: int
) -> CandidateStageTransition:
    """Write one CandidateStageTransition row: `from_stage_id` is whatever the
    candidate's latest transition says (`None` if this is their first ever).
    Flushes but does not commit — the caller controls the transaction
    boundary, same convention as `close_and_open_round`, so this can be
    combined atomically with a Round write."""
    latest = latest_transitions_by_candidate(db, [candidate.id]).get(candidate.id)
    from_stage_id = latest.to_stage_id if latest else None
    transition = CandidateStageTransition(
        candidate_id=candidate.id,
        from_stage_id=from_stage_id,
        to_stage_id=to_stage.id,
        actor_id=actor_id,
    )
    db.add(transition)
    db.flush()
    return transition

"""The close-then-open transaction shared by two call sites: ticket #27's
"admin assigns next round" step of the round loop, and ticket #30's
reassignment flow. Same shape both times — close the candidate's current
open Round (if any), then open a new one — differing only in the resulting
status of the closed round (`closed_unscored` vs `reassigned`). Implemented
once here so the two call sites can't independently drift the way
compute_health and compute_next_action once did (see derive.py's module
docstring)."""

from datetime import datetime, timezone

from sqlalchemy.orm import Session as DBSession

from app.models.candidate import Candidate
from app.models.round import Round, RoundStatus


def close_and_open_round(
    db: DBSession,
    *,
    candidate_id: int,
    new_stage_id: int,
    new_assignee_id: int,
    assignment_due_at: datetime | None = None,
    brief: str | None = None,
    prior_round_closed_status: RoundStatus = RoundStatus.closed_unscored,
    reassigned_from_round_id: int | None = None,
    now: datetime | None = None,
) -> Round:
    """Close the candidate's currently open Round (if any) as
    `prior_round_closed_status`, then open a new Round for `new_stage_id` /
    `new_assignee_id`. Only closes a round when one is genuinely open — the
    normal path (prior round already `scored`) has nothing to close.

    Flushes but does not commit: the caller controls the transaction boundary
    so it can add more writes (e.g. ticket #28's optional Interview) to the
    same atomic commit. Callers that want this as a standalone unit of work
    must call db.commit() themselves.

    Locks the Candidate row for the duration, not the Round row: two
    concurrent calls for a candidate with NO open round yet (first assignment
    race) still have to serialize, and there is no Round row to lock in that
    case. Locking the Candidate covers both that race and the close-then-open
    race uniformly, the same way submit_scores locks the Round it's scoped to
    — see that function's docstring for why an earlier unlocked read of the
    same row first would be a correctness bug, not just redundant.
    """
    now = now or datetime.now(timezone.utc)

    db.query(Candidate).filter(Candidate.id == candidate_id).with_for_update().first()

    prior_open = (
        db.query(Round)
        .filter(Round.candidate_id == candidate_id, Round.status == RoundStatus.open)
        .with_for_update()
        .first()
    )
    if prior_open is not None:
        prior_open.status = prior_round_closed_status
        prior_open.closed_at = now

    new_round = Round(
        candidate_id=candidate_id,
        stage_id=new_stage_id,
        assignee_id=new_assignee_id,
        status=RoundStatus.open,
        assignment_due_at=assignment_due_at,
        brief=brief,
        reassigned_from_round_id=reassigned_from_round_id,
    )
    db.add(new_round)
    db.flush()
    return new_round

"""Ownership and access queries for Candidates, scoped through Round — the
only source of truth since Candidate.interviewer_id was dropped. Three
independent queries, deliberately not derived from one another:

- get_open_round: backs `compute_current_owner` (display).
- interviewer_has_access: has this interviewer EVER been assigned any Round
  (any status) for this candidate — read authorization. A closed/reassigned
  Round still grants access; this is what keeps an interviewer from losing
  access to a candidate the instant they submit their scorecard.
- (submission authorization is round_id-scoped and lives in app.scoring.submit,
  since it is not about a candidate at all — it is about one specific Round.)
"""

from sqlalchemy.orm import Session as DBSession

from app.models.candidate import Candidate
from app.models.round import Round, RoundStatus
from app.pipeline.derive import compute_current_owner


def get_open_round(db: DBSession, candidate_id: int) -> Round | None:
    return (
        db.query(Round)
        .filter(Round.candidate_id == candidate_id, Round.status == RoundStatus.open)
        .first()
    )


def get_open_rounds(db: DBSession, candidate_ids: list[int]) -> dict[int, Round]:
    if not candidate_ids:
        return {}
    rows = (
        db.query(Round)
        .filter(Round.candidate_id.in_(candidate_ids), Round.status == RoundStatus.open)
        .all()
    )
    return {row.candidate_id: row for row in rows}


def candidate_to_out(db: DBSession, candidate: Candidate):
    from app.schemas.candidate import CandidateOut

    open_round = get_open_round(db, candidate.id)
    return CandidateOut(
        id=candidate.id,
        full_name=candidate.full_name,
        email=candidate.email,
        phone=candidate.phone,
        position_id=candidate.position_id,
        owner_id=compute_current_owner(open_round),
        open_round_id=open_round.id if open_round is not None else None,
        status=candidate.status,
        hold_reason=candidate.hold_reason,
        hold_review_by=candidate.hold_review_by,
        created_by=candidate.created_by,
        created_at=candidate.created_at,
        updated_at=candidate.updated_at,
    )


def interviewer_has_access(db: DBSession, candidate_id: int, interviewer_id: int) -> bool:
    return (
        db.query(Round.id)
        .filter(Round.candidate_id == candidate_id, Round.assignee_id == interviewer_id)
        .first()
        is not None
    )

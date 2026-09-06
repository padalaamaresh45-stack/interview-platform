"""One-off data cleanup, not a migration: closes any open Round belonging to a
candidate whose current stage is already terminal (Hired/Rejected).

Why a script and not a migration: this fixes bad *data* that accumulated
because `move_candidate` never closed a candidate's open round when moving
them to a terminal stage (the "Move to stage" / rounds-engine disconnect found
in the 2026-09-06 manual E2E pass). It is not a schema change, and the bug that
produced these rows is explicitly NOT being fixed here (`move_candidate` is
untouched, per scope) — so this script is a point-in-time cleanup, safe to
re-run (idempotent: a second run finds nothing to close), not something
alembic's forward/rollback model is the right fit for. If `move_candidate`
starts closing rounds on terminal moves in a future change, this script
becomes permanently a no-op rather than something that needs deleting.

Sets the affected rounds to `closed_unscored`, per the epic doc's two-writers
rule for that status (rejection, and advancing past a still-open round — this
is a delayed instance of the same "closing without a scorecard" case, just
triggered by cleanup instead of by the advance transaction itself).

Run with: python -m app.scripts.close_terminal_phantom_rounds [--dry-run]
"""

import argparse
from datetime import datetime, timezone

from app.database import SessionLocal
from app.models.round import Round, RoundStatus
from app.models.stage import Stage
from app.models.stage_transition import CandidateStageTransition


def find_phantom_open_rounds(db) -> list[Round]:
    """Every open Round whose candidate's current stage (latest
    CandidateStageTransition.to_stage_id) is_terminal."""
    open_rounds = db.query(Round).filter(Round.status == RoundStatus.open).all()
    if not open_rounds:
        return []

    candidate_ids = [r.candidate_id for r in open_rounds]
    latest_by_candidate: dict[int, CandidateStageTransition] = {}
    transitions = (
        db.query(CandidateStageTransition)
        .filter(CandidateStageTransition.candidate_id.in_(candidate_ids))
        .order_by(
            CandidateStageTransition.candidate_id,
            CandidateStageTransition.created_at.desc(),
            CandidateStageTransition.id.desc(),
        )
        .all()
    )
    for row in transitions:
        latest_by_candidate.setdefault(row.candidate_id, row)

    stage_ids = {t.to_stage_id for t in latest_by_candidate.values()}
    terminal_stage_ids = {
        s.id for s in db.query(Stage).filter(Stage.id.in_(stage_ids), Stage.is_terminal.is_(True)).all()
    }

    phantoms = []
    for round_ in open_rounds:
        latest = latest_by_candidate.get(round_.candidate_id)
        if latest is not None and latest.to_stage_id in terminal_stage_ids:
            phantoms.append(round_)
    return phantoms


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Report what would change without writing.")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        phantoms = find_phantom_open_rounds(db)
        if not phantoms:
            print("No open rounds found on candidates at a terminal stage. Nothing to do.")
            return

        for round_ in phantoms:
            print(
                f"Round {round_.id} (candidate_id={round_.candidate_id}, stage_id={round_.stage_id}) "
                f"is open on a candidate now at a terminal stage."
            )

        if args.dry_run:
            print(f"\n--dry-run: would close {len(phantoms)} round(s) as closed_unscored. No changes made.")
            return

        now = datetime.now(timezone.utc)
        for round_ in phantoms:
            round_.status = RoundStatus.closed_unscored
            round_.closed_at = now
        db.commit()
        print(f"\nClosed {len(phantoms)} round(s) as closed_unscored.")
    finally:
        db.close()


if __name__ == "__main__":
    main()

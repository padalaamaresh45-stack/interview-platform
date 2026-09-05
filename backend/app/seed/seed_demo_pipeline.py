"""Populate the board with example candidates in every stage, for local/demo use.

Run once against a dev database:

    python -m app.seed.seed_demo_pipeline

Idempotent: does nothing if the demo position already exists. Every row it
creates is a normal Candidate/Position/User — nothing here is board-only fake
data, so it can be edited, moved, and deleted through the app like anything
else.
"""
from datetime import datetime, timedelta, timezone

from app.auth.hashing import hash_password
from app.database import SessionLocal
from app.models.candidate import Candidate, CandidateStatus
from app.models.interview_score import InterviewScore
from app.models.position import Position
from app.models.question import Question
from app.models.stage import Stage
from app.models.stage_transition import CandidateStageTransition
from app.models.user import User, UserRole

DEMO_POSITION_TITLE = "Product Engineer (Demo)"


def _get_or_create_admin(db) -> User:
    admin = db.query(User).filter(User.role == UserRole.admin).first()
    if admin is not None:
        return admin
    admin = User(
        email="demo-admin@example.com",
        password_hash=hash_password("demo-password-123"),
        full_name="Demo Admin",
        role=UserRole.admin,
    )
    db.add(admin)
    db.flush()
    return admin


def _get_or_create_interviewer(db, email: str, full_name: str) -> User:
    interviewer = db.query(User).filter(User.email == email).first()
    if interviewer is not None:
        return interviewer
    interviewer = User(email=email, password_hash=hash_password("demo-password-123"), full_name=full_name, role=UserRole.interviewer)
    db.add(interviewer)
    db.flush()
    return interviewer


def main() -> None:
    db = SessionLocal()
    try:
        if db.query(Position).filter(Position.title == DEMO_POSITION_TITLE).first() is not None:
            print(f"{DEMO_POSITION_TITLE!r} already exists — nothing to do.")
            return

        admin = _get_or_create_admin(db)
        interviewer_a = _get_or_create_interviewer(db, "demo-priya@example.com", "Priya Raghavan")
        interviewer_b = _get_or_create_interviewer(db, "demo-marcus@example.com", "Marcus Bell")

        position = Position(title=DEMO_POSITION_TITLE, created_by=admin.id)
        db.add(position)
        db.flush()  # after_insert event seeds this position's Stage rows

        db.add(Question(position_id=position.id, question_text="Walk me through a system you designed.", sequence_order=1))
        db.flush()
        question = db.query(Question).filter(Question.position_id == position.id).first()

        stages = {
            s.name: s for s in db.query(Stage).filter(Stage.position_id == position.id).order_by(Stage.sequence_order)
        }

        now = datetime.now(timezone.utc)

        # (name, interviewer, final stage, days ago they entered that stage, score or None)
        demo_candidates = [
            ("Dana Whitfield", interviewer_a, "Applied", 1, None),
            ("Amara Okonkwo", interviewer_b, "Applied", 5, None),  # over Applied's 3-day limit -> stalled
            ("Wei Zhang", interviewer_a, "Screening", 2, None),
            ("Julian Reyes", interviewer_b, "Screening", 7, None),  # over Screening's 5-day limit -> stalled
            ("Sofia Mendes", interviewer_a, "Under review", 3, 4),
            ("Ravi Anand", interviewer_b, "Offer", 1, 5),
            ("Noah Brennan", interviewer_a, "Hired", 10, 5),
            ("Elena Petrova", interviewer_b, "Rejected", 2, 2),
        ]

        for full_name, interviewer, stage_name, days_ago, score in demo_candidates:
            stage = stages[stage_name]
            candidate = Candidate(
                full_name=full_name,
                position_id=position.id,
                interviewer_id=interviewer.id,
                created_by=admin.id,
                status=CandidateStatus.completed if score is not None else CandidateStatus.not_started,
            )
            db.add(candidate)
            db.flush()  # after_insert event writes the "Applied" transition

            entered_at = now - timedelta(days=days_ago)
            if stage_name != "Applied":
                # The "latest" transition is whichever has the greatest created_at
                # (see _latest_transitions_by_candidate), so the Applied transition
                # must be backdated to *before* entered_at too, not left at its
                # real (and therefore more recent) insert-time default.
                db.query(CandidateStageTransition).filter(
                    CandidateStageTransition.candidate_id == candidate.id
                ).update({"created_at": entered_at - timedelta(days=1)})
                db.add(
                    CandidateStageTransition(
                        candidate_id=candidate.id,
                        from_stage_id=stages["Applied"].id,
                        to_stage_id=stage.id,
                        actor_id=admin.id,
                        created_at=entered_at,
                    )
                )
            else:
                db.query(CandidateStageTransition).filter(
                    CandidateStageTransition.candidate_id == candidate.id
                ).update({"created_at": entered_at})

            if score is not None:
                db.add(InterviewScore(candidate_id=candidate.id, question_id=question.id, score=score))

        db.commit()
        print(f"Seeded {len(demo_candidates)} demo candidates under {DEMO_POSITION_TITLE!r}.")
    finally:
        db.close()


if __name__ == "__main__":
    main()

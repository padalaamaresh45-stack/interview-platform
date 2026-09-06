"""One-off cleanup: earlier QA sessions left behind test positions with
QA-artifact titles ("Manual Test Position", "QA Curl Position Renamed", ...)
and a couple of placeholder candidates ("Renamed Candidate", "AMARESH PADALA").
Rather than deleting them, rename everything to realistic-looking data and
top up each position with candidates spread across stages, so the homepage
board never lands on an empty or obviously-fake position.

Idempotent by position id — safe to re-run, it always overwrites titles and
adds candidates by name so re-running just adds duplicates of the "extra"
candidates (not something this needs to guard against for a one-time cleanup).

Run once:

    python -m app.seed.backfill_realistic_positions
"""
from datetime import datetime, timedelta, timezone

from app.database import SessionLocal
from app.models.candidate import Candidate, CandidateStatus
from app.models.interview_score import InterviewScore
from app.models.position import Position
from app.models.question import Question
from app.models.round import Round, RoundStatus
from app.models.stage import Stage
from app.models.stage_transition import CandidateStageTransition
from app.models.user import User, UserRole

POSITION_RENAMES = {
    "Manual Test Position": "Senior Backend Engineer",
    "QA Curl Position Renamed": "Product Designer",
    "Flow Test Engineer": "Data Analyst",
    "Smoke Test Engineer": "Customer Success Manager",
}

QUESTION_RENAMES = {
    "First": "Describe a project where you had to push back on a deadline.",
    "Second": "How do you approach a design critique with conflicting feedback?",
}

CANDIDATE_RENAMES = {
    "AMARESH PADALA": "Farah Nasser",
    "Renamed Candidate": "Tomás Ibarra",
}

EXTRA_CANDIDATES = {
    "Senior Backend Engineer": [
        ("Grace Kimathi", "Applied", 1, None),
        ("Owen Fitzgerald", "Screening", 3, None),
        ("Mei Lin Tan", "Under review", 4, 4),
        ("Callum Ashworth", "Hired", 12, 5),
    ],
    "Product Designer": [
        ("Isabela Duarte", "Screening", 2, None),
        ("Nikhil Bhatt", "Offer", 1, 5),
    ],
    "Data Analyst": [
        ("Freya Solberg", "Applied", 6, None),  # over limit -> stalled
        ("Jonas Achebe", "Under review", 2, 3),
    ],
    "Customer Success Manager": [
        ("Lucia Moreno", "Applied", 1, None),
        ("Sami Al-Farsi", "Screening", 5, None),
        ("Beatrix Novak", "Rejected", 3, 2),
    ],
}


def main() -> None:
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.role == UserRole.admin, User.is_active.is_(True)).first()
        interviewers = db.query(User).filter(User.role == UserRole.interviewer, User.is_active.is_(True)).all()
        if admin is None or not interviewers:
            print("Need at least one active admin and one active interviewer — aborting.")
            return

        # Rename positions
        renamed_positions: dict[str, Position] = {}
        for position in db.query(Position).all():
            new_title = POSITION_RENAMES.get(position.title)
            if new_title:
                position.title = new_title
            renamed_positions[position.title] = position
        db.flush()

        # Rename generic questions
        for question in db.query(Question).all():
            new_text = QUESTION_RENAMES.get(question.question_text)
            if new_text:
                question.question_text = new_text
        db.flush()

        # Rename placeholder candidates and move them off any deactivated interviewer
        for candidate in db.query(Candidate).all():
            new_name = CANDIDATE_RENAMES.get(candidate.full_name)
            if new_name:
                candidate.full_name = new_name
            open_round = (
                db.query(Round)
                .filter(Round.candidate_id == candidate.id, Round.status == RoundStatus.open)
                .first()
            )
            if open_round is not None:
                interviewer = db.get(User, open_round.assignee_id)
                if interviewer is not None and not interviewer.is_active:
                    open_round.assignee_id = interviewers[0].id
        db.flush()

        now = datetime.now(timezone.utc)
        added = 0
        for title, roster in EXTRA_CANDIDATES.items():
            position = renamed_positions.get(title)
            if position is None:
                continue

            stages = {
                s.name: s
                for s in db.query(Stage).filter(Stage.position_id == position.id).order_by(Stage.sequence_order)
            }
            question = db.query(Question).filter(Question.position_id == position.id).first()
            if question is None:
                question = Question(
                    position_id=position.id,
                    question_text="Walk me through a recent piece of work you're proud of.",
                    sequence_order=1,
                )
                db.add(question)
                db.flush()

            for idx, (full_name, stage_name, days_ago, score) in enumerate(roster):
                if db.query(Candidate).filter(Candidate.full_name == full_name).first() is not None:
                    continue  # already added by a previous run

                stage = stages[stage_name]
                interviewer = interviewers[idx % len(interviewers)]
                candidate = Candidate(
                    full_name=full_name,
                    position_id=position.id,
                    created_by=admin.id,
                    status=CandidateStatus.completed if score is not None else CandidateStatus.not_started,
                )
                db.add(candidate)
                db.flush()  # after_insert event writes the "Applied" transition
                round_status = RoundStatus.scored if score is not None else RoundStatus.open
                round_ = Round(
                    candidate_id=candidate.id, stage_id=stage.id, assignee_id=interviewer.id, status=round_status
                )
                db.add(round_)
                db.flush()

                entered_at = now - timedelta(days=days_ago)
                if stage_name != "Applied":
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

                if score is not None and question is not None:
                    db.add(
                        InterviewScore(
                            candidate_id=candidate.id, round_id=round_.id, question_id=question.id, score=score
                        )
                    )

                added += 1

        db.commit()
        print(f"Renamed {len(POSITION_RENAMES)} positions, added {added} candidates.")
    finally:
        db.close()


if __name__ == "__main__":
    main()

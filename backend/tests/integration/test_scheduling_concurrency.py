"""Ticket #28 AC5: two simultaneous schedule attempts against the same round —
the DB's partial unique index (`interviews(round_id) WHERE status != 'cancelled'`,
landed in #26) must be what rejects the second one, not an app-level check
racing ahead of it."""

import threading

from app.auth.hashing import hash_password
from app.auth.session import SESSION_COOKIE_NAME, create_session
from app.models.candidate import Candidate
from app.models.interview import Interview, InterviewStatus
from app.models.position import Position
from app.models.round import Round, RoundStatus
from app.models.stage import Stage
from app.models.user import User, UserRole


def _make_admin(db_session):
    admin = User(
        email="admin@example.com",
        password_hash=hash_password("correct horse battery staple"),
        full_name="Admin",
        role=UserRole.admin,
    )
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)
    return admin


def _make_interviewer(db_session):
    user = User(email="iv@example.com", password_hash=hash_password("pw"), full_name="Ivy", role=UserRole.interviewer)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _make_round(db_session, admin, interviewer):
    position = Position(title="Backend Engineer", created_by=admin.id)
    db_session.add(position)
    db_session.commit()
    db_session.refresh(position)

    stage_id = (
        db_session.query(Stage.id)
        .filter(Stage.position_id == position.id)
        .order_by(Stage.sequence_order)
        .limit(1)
        .scalar()
    )

    candidate = Candidate(full_name="Cara Candidate", position_id=position.id, created_by=admin.id)
    db_session.add(candidate)
    db_session.flush()

    round_ = Round(candidate_id=candidate.id, stage_id=stage_id, assignee_id=interviewer.id, status=RoundStatus.open)
    db_session.add(round_)
    db_session.commit()
    db_session.refresh(round_)
    return round_


def test_concurrent_schedule_on_same_round_only_one_active_interview_survives(client, db_session):
    admin = _make_admin(db_session)
    interviewer = _make_interviewer(db_session)
    round_ = _make_round(db_session, admin, interviewer)

    session = create_session(db_session, admin.id)
    client.cookies.set(SESSION_COOKIE_NAME, session.id)

    from datetime import datetime, timedelta, timezone

    payload_a = {
        "round_id": round_.id,
        "scheduled_at": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
    }
    payload_b = {
        "round_id": round_.id,
        "scheduled_at": (datetime.now(timezone.utc) + timedelta(days=2)).isoformat(),
    }

    results = []

    def _schedule(payload):
        try:
            resp = client.post("/api/admin/interviews", json=payload)
            results.append(resp.status_code)
        except Exception:
            # The endpoint has no app-level pre-check and no try/except around
            # the commit (see app/routers/interviews.py::schedule_interview),
            # so the loser of the race surfaces as an uncaught IntegrityError
            # from the DB's partial unique index rather than a handled HTTP
            # error. That's the exact thing this test exists to prove — the
            # index, not app logic, is what stops the second write.
            results.append("raised")

    threads = [
        threading.Thread(target=_schedule, args=(payload_a,)),
        threading.Thread(target=_schedule, args=(payload_b,)),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Exactly one write succeeds; the other fails at the DB constraint level
    # (surfaced here as an uncaught IntegrityError, since the endpoint has no
    # app-level pre-check to race ahead of it — see comment above).
    assert results.count(201) == 1
    assert results.count("raised") == 1

    active_interviews = (
        db_session.query(Interview)
        .filter(Interview.round_id == round_.id, Interview.status != InterviewStatus.cancelled)
        .all()
    )
    assert len(active_interviews) == 1

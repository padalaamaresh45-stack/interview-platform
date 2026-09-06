"""Ticket #28 AC5: two simultaneous schedule attempts against the same round —
the DB's partial unique index (`interviews(round_id) WHERE status != 'cancelled'`,
landed in #26) must be what rejects the second one, not an app-level check
racing ahead of it."""

import threading
from datetime import datetime, timedelta, timezone

from sqlalchemy.exc import IntegrityError

from app.auth.session import SESSION_COOKIE_NAME, create_session
from app.models.candidate import Candidate
from app.models.interview import Interview, InterviewStatus
from app.models.round import Round, RoundStatus
from tests.integration.test_interviews import (
    _admin_client,
    _first_stage_id,
    _interviewer_client,
    _make_position,
)


def test_concurrent_schedule_on_same_round_only_one_active_interview_survives(client, db_session):
    admin = _admin_client(client, db_session)
    interviewer = _interviewer_client(client, db_session, email="iv@example.com")
    position = _make_position(db_session, admin)
    stage_id = _first_stage_id(db_session, position)

    candidate = Candidate(full_name="Cara Candidate", position_id=position.id, created_by=admin.id)
    db_session.add(candidate)
    db_session.flush()
    round_ = Round(candidate_id=candidate.id, stage_id=stage_id, assignee_id=interviewer.id, status=RoundStatus.open)
    db_session.add(round_)
    db_session.commit()
    db_session.refresh(round_)

    # Log back in as admin — scheduling is an admin-only action, and creating
    # the interviewer client above overwrote the session cookie.
    admin_session = create_session(db_session, admin.id)
    client.cookies.set(SESSION_COOKIE_NAME, admin_session.id)

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
        except IntegrityError as exc:
            # The endpoint has no app-level pre-check and no try/except around
            # the commit (see app/routers/interviews.py::schedule_interview),
            # so the loser of the race surfaces as an uncaught IntegrityError
            # from the DB's partial unique index rather than a handled HTTP
            # error. Scoped to IntegrityError (not a bare Exception) and to
            # this specific constraint by name, so an unrelated failure (e.g.
            # connection-pool exhaustion under threads) is NOT swallowed here
            # and instead fails the test loudly, as it should.
            assert "uq_interviews_round_active" in str(exc)
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

from datetime import datetime, timedelta, timezone

import pytest

from app.auth.hashing import hash_password
from app.auth.session import SESSION_COOKIE_NAME, create_session
from app.models.candidate import Candidate
from app.models.interview import Interview, InterviewStatus
from app.models.position import Position
from app.models.round import Round, RoundStatus
from app.models.stage import Stage
from app.models.user import User, UserRole

ADMIN_EMAIL = "admin@example.com"
ADMIN_PASSWORD = "correct horse battery staple"


def _admin_client(client, db_session, *, email=ADMIN_EMAIL, password=ADMIN_PASSWORD):
    admin = User(email=email, password_hash=hash_password(password), full_name="Admin", role=UserRole.admin)
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)
    session = create_session(db_session, admin.id)
    client.cookies.set(SESSION_COOKIE_NAME, session.id)
    return admin


def _make_interviewer(db_session, email="iv@example.com"):
    user = User(email=email, password_hash=hash_password("pw"), full_name="Ivy", role=UserRole.interviewer)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _make_position(db_session, admin):
    position = Position(title="Backend Engineer", created_by=admin.id)
    db_session.add(position)
    db_session.commit()
    db_session.refresh(position)
    return position


def _stage_ids(db_session, position):
    return [
        row
        for (row,) in db_session.query(Stage.id)
        .filter(Stage.position_id == position.id)
        .order_by(Stage.sequence_order)
        .all()
    ]


def _make_candidate(db_session, admin, position):
    candidate = Candidate(full_name="Cara Candidate", position_id=position.id, created_by=admin.id)
    db_session.add(candidate)
    db_session.commit()
    db_session.refresh(candidate)
    return candidate


def test_assign_and_schedule_in_one_call_creates_round_and_interview(client, db_session):
    admin = _admin_client(client, db_session)
    position = _make_position(db_session, admin)
    interviewer = _make_interviewer(db_session)
    candidate = _make_candidate(db_session, admin, position)
    stage_id = _stage_ids(db_session, position)[0]
    scheduled_at = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()

    resp = client.post(
        f"/api/admin/candidates/{candidate.id}/rounds",
        json={
            "stage_id": stage_id,
            "assignee_id": interviewer.id,
            "scheduled_at": scheduled_at,
            "duration_minutes": 45,
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "open"
    assert body["interview_id"] is not None

    rounds = db_session.query(Round).filter(Round.candidate_id == candidate.id).all()
    assert len(rounds) == 1
    interviews = db_session.query(Interview).filter(Interview.round_id == rounds[0].id).all()
    assert len(interviews) == 1


def test_assign_with_no_schedule_creates_round_only_assigned_but_unscheduled(client, db_session):
    admin = _admin_client(client, db_session)
    position = _make_position(db_session, admin)
    interviewer = _make_interviewer(db_session)
    candidate = _make_candidate(db_session, admin, position)
    stage_id = _stage_ids(db_session, position)[0]

    resp = client.post(
        f"/api/admin/candidates/{candidate.id}/rounds",
        json={"stage_id": stage_id, "assignee_id": interviewer.id},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["interview_id"] is None

    board = client.get("/api/pipeline/board", params={"position_id": position.id})
    assert board.status_code == 200
    candidates = [c for col in board.json()["columns"] for c in col["candidates"]]
    matched = next(c for c in candidates if c["id"] == candidate.id)
    assert matched["gap_state"] == "assigned_but_unscheduled"


def test_assign_and_schedule_atomic_on_forced_interview_failure(client, db_session, monkeypatch):
    admin = _admin_client(client, db_session)
    position = _make_position(db_session, admin)
    interviewer = _make_interviewer(db_session)
    candidate = _make_candidate(db_session, admin, position)
    stage_id = _stage_ids(db_session, position)[0]

    def _boom(*args, **kwargs):
        raise RuntimeError("forced failure")

    monkeypatch.setattr("app.routers.rounds.Interview", _boom)

    with pytest.raises(RuntimeError):
        client.post(
            f"/api/admin/candidates/{candidate.id}/rounds",
            json={
                "stage_id": stage_id,
                "assignee_id": interviewer.id,
                "scheduled_at": datetime.now(timezone.utc).isoformat(),
            },
        )

    rounds = db_session.query(Round).filter(Round.candidate_id == candidate.id).all()
    assert rounds == []


def test_cancel_returns_round_to_assigned_but_unscheduled_not_closed(client, db_session):
    admin = _admin_client(client, db_session)
    position = _make_position(db_session, admin)
    interviewer = _make_interviewer(db_session)
    candidate = _make_candidate(db_session, admin, position)
    stage_id = _stage_ids(db_session, position)[0]

    assign_resp = client.post(
        f"/api/admin/candidates/{candidate.id}/rounds",
        json={
            "stage_id": stage_id,
            "assignee_id": interviewer.id,
            "scheduled_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    round_id = assign_resp.json()["id"]
    interview_id = assign_resp.json()["interview_id"]

    cancel_resp = client.delete(f"/api/admin/interviews/{interview_id}")
    assert cancel_resp.status_code == 204

    round_ = db_session.get(Round, round_id)
    db_session.refresh(round_)
    assert round_.status == RoundStatus.open

    interview = db_session.get(Interview, interview_id)
    assert interview.status == InterviewStatus.cancelled

    board = client.get("/api/pipeline/board", params={"position_id": position.id})
    candidates = [c for col in board.json()["columns"] for c in col["candidates"]]
    matched = next(c for c in candidates if c["id"] == candidate.id)
    assert matched["gap_state"] == "assigned_but_unscheduled"


def test_reassign_closes_old_round_and_opens_new_via_shared_helper(client, db_session, monkeypatch):
    admin = _admin_client(client, db_session)
    position = _make_position(db_session, admin)
    interviewer = _make_interviewer(db_session)
    other_interviewer = _make_interviewer(db_session, email="other@example.com")
    candidate = _make_candidate(db_session, admin, position)
    stage_id = _stage_ids(db_session, position)[0]

    assign_resp = client.post(
        f"/api/admin/candidates/{candidate.id}/rounds",
        json={"stage_id": stage_id, "assignee_id": interviewer.id},
    )
    old_round_id = assign_resp.json()["id"]

    calls = []
    import app.routers.rounds as rounds_module

    original = rounds_module.close_and_open_round

    def _spy(*args, **kwargs):
        calls.append(kwargs)
        return original(*args, **kwargs)

    monkeypatch.setattr(rounds_module, "close_and_open_round", _spy)

    resp = client.post(
        f"/api/admin/candidates/{candidate.id}/rounds/reassign",
        json={"assignee_id": other_interviewer.id},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["assignee_id"] == other_interviewer.id
    assert body["stage_id"] == stage_id
    assert body["reassigned_from_round_id"] == old_round_id

    assert len(calls) == 1
    assert calls[0]["prior_round_closed_status"] == RoundStatus.reassigned

    old_round = db_session.get(Round, old_round_id)
    db_session.refresh(old_round)
    assert old_round.status == RoundStatus.reassigned
    assert old_round.closed_at is not None


def test_reassign_does_not_touch_scheduled_interview(client, db_session):
    admin = _admin_client(client, db_session)
    position = _make_position(db_session, admin)
    interviewer = _make_interviewer(db_session)
    other_interviewer = _make_interviewer(db_session, email="other@example.com")
    candidate = _make_candidate(db_session, admin, position)
    stage_id = _stage_ids(db_session, position)[0]

    assign_resp = client.post(
        f"/api/admin/candidates/{candidate.id}/rounds",
        json={
            "stage_id": stage_id,
            "assignee_id": interviewer.id,
            "scheduled_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    interview_id = assign_resp.json()["interview_id"]

    resp = client.post(
        f"/api/admin/candidates/{candidate.id}/rounds/reassign",
        json={"assignee_id": other_interviewer.id},
    )
    assert resp.status_code == 201

    interview = db_session.get(Interview, interview_id)
    db_session.refresh(interview)
    assert interview.status == InterviewStatus.scheduled
    assert interview.scheduled_at is not None


def test_reassign_updates_ownership_immediately(client, db_session):
    admin = _admin_client(client, db_session)
    position = _make_position(db_session, admin)
    interviewer = _make_interviewer(db_session)
    other_interviewer = _make_interviewer(db_session, email="other@example.com")
    candidate = _make_candidate(db_session, admin, position)
    stage_id = _stage_ids(db_session, position)[0]

    client.post(
        f"/api/admin/candidates/{candidate.id}/rounds",
        json={"stage_id": stage_id, "assignee_id": interviewer.id},
    )
    client.post(
        f"/api/admin/candidates/{candidate.id}/rounds/reassign",
        json={"assignee_id": other_interviewer.id},
    )

    resp = client.get(f"/api/admin/candidates/{candidate.id}")
    assert resp.status_code == 200
    assert resp.json()["owner_id"] == other_interviewer.id


def test_reschedule_after_cancel_succeeds(client, db_session):
    admin = _admin_client(client, db_session)
    position = _make_position(db_session, admin)
    interviewer = _make_interviewer(db_session)
    candidate = _make_candidate(db_session, admin, position)
    stage_id = _stage_ids(db_session, position)[0]

    assign_resp = client.post(
        f"/api/admin/candidates/{candidate.id}/rounds",
        json={
            "stage_id": stage_id,
            "assignee_id": interviewer.id,
            "scheduled_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    round_id = assign_resp.json()["id"]
    interview_id = assign_resp.json()["interview_id"]

    client.delete(f"/api/admin/interviews/{interview_id}")

    replacement = client.post(
        "/api/admin/interviews",
        json={
            "round_id": round_id,
            "scheduled_at": (datetime.now(timezone.utc) + timedelta(days=2)).isoformat(),
        },
    )
    assert replacement.status_code == 201

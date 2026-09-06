from datetime import datetime, timedelta, timezone

from app.auth.hashing import hash_password
from app.auth.session import SESSION_COOKIE_NAME, create_session
from app.models.candidate import Candidate
from app.models.interview import Interview
from app.models.position import Position
from app.models.round import Round
from app.models.stage import Stage
from app.models.user import User, UserRole

ADMIN_EMAIL = "admin@example.com"
ADMIN_PASSWORD = "correct horse battery staple"


def _make_user(db_session, *, email=ADMIN_EMAIL, password=ADMIN_PASSWORD, role=UserRole.admin):
    user = User(email=email, password_hash=hash_password(password), full_name="Test User", role=role)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _admin_client(client, db_session, *, email=ADMIN_EMAIL, password=ADMIN_PASSWORD):
    admin = _make_user(db_session, email=email, password=password)
    session = create_session(db_session, admin.id)
    client.cookies.set(SESSION_COOKIE_NAME, session.id)
    return admin


def _interviewer_client(client, db_session, *, email, full_name="Ivy Interviewer"):
    interviewer = User(
        email=email, password_hash=hash_password("pw"), full_name=full_name, role=UserRole.interviewer
    )
    db_session.add(interviewer)
    db_session.commit()
    db_session.refresh(interviewer)
    session = create_session(db_session, interviewer.id)
    client.cookies.set(SESSION_COOKIE_NAME, session.id)
    return interviewer


def _make_position(db_session, admin):
    position = Position(title="Backend Engineer", created_by=admin.id)
    db_session.add(position)
    db_session.commit()
    db_session.refresh(position)
    return position


def _first_stage_id(db_session, position):
    return (
        db_session.query(Stage.id)
        .filter(Stage.position_id == position.id)
        .order_by(Stage.sequence_order)
        .limit(1)
        .scalar()
    )


def _make_candidate_with_round(db_session, admin, position, interviewer, *, full_name="Cara Candidate"):
    candidate = Candidate(full_name=full_name, position_id=position.id, created_by=admin.id)
    db_session.add(candidate)
    db_session.flush()
    round_ = Round(
        candidate_id=candidate.id, stage_id=_first_stage_id(db_session, position), assignee_id=interviewer.id
    )
    db_session.add(round_)
    db_session.commit()
    db_session.refresh(candidate)
    db_session.refresh(round_)
    return candidate, round_


def test_admin_can_schedule_and_list_interviews(client, db_session):
    admin = _admin_client(client, db_session)
    position = _make_position(db_session, admin)
    interviewer = User(
        email="iv@example.com", password_hash=hash_password("pw"), full_name="Ivy", role=UserRole.interviewer
    )
    db_session.add(interviewer)
    db_session.commit()
    db_session.refresh(interviewer)
    candidate, round_ = _make_candidate_with_round(db_session, admin, position, interviewer)

    scheduled_at = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    resp = client.post(
        "/api/admin/interviews",
        json={
            "round_id": round_.id,
            "scheduled_at": scheduled_at,
            "duration_minutes": 45,
            "notes": "Focus on system design.",
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["candidate_name"] == "Cara Candidate"
    assert body["interviewer_name"] == "Ivy"
    assert body["position_title"] == "Backend Engineer"
    assert body["duration_minutes"] == 45
    assert body["status"] == "scheduled"

    listed = client.get("/api/admin/interviews")
    assert listed.status_code == 200
    assert len(listed.json()) == 1


def test_interviewer_only_sees_their_own_interviews(client, db_session):
    admin = _admin_client(client, db_session)
    position = _make_position(db_session, admin)

    iv_a = User(email="a@example.com", password_hash=hash_password("pw"), full_name="A", role=UserRole.interviewer)
    iv_b = User(email="b@example.com", password_hash=hash_password("pw"), full_name="B", role=UserRole.interviewer)
    db_session.add_all([iv_a, iv_b])
    db_session.commit()
    db_session.refresh(iv_a)
    db_session.refresh(iv_b)

    candidate_a, round_a = _make_candidate_with_round(db_session, admin, position, iv_a)
    candidate_b, round_b = _make_candidate_with_round(
        db_session, admin, position, iv_b, full_name="Bob Candidate"
    )

    now = datetime.now(timezone.utc)
    db_session.add(Interview(candidate_id=candidate_a.id, round_id=round_a.id, scheduled_at=now, created_by=admin.id))
    db_session.add(Interview(candidate_id=candidate_b.id, round_id=round_b.id, scheduled_at=now, created_by=admin.id))
    db_session.commit()

    session = create_session(db_session, iv_a.id)
    client.cookies.set(SESSION_COOKIE_NAME, session.id)

    resp = client.get("/api/interviewer/interviews")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["candidate_name"] == "Cara Candidate"


def test_admin_can_cancel_an_interview(client, db_session):
    admin = _admin_client(client, db_session)
    position = _make_position(db_session, admin)
    interviewer = User(
        email="iv2@example.com", password_hash=hash_password("pw"), full_name="Ivy", role=UserRole.interviewer
    )
    db_session.add(interviewer)
    db_session.commit()
    db_session.refresh(interviewer)
    candidate, round_ = _make_candidate_with_round(db_session, admin, position, interviewer)

    create_resp = client.post(
        "/api/admin/interviews",
        json={"round_id": round_.id, "scheduled_at": datetime.now(timezone.utc).isoformat()},
    )
    interview_id = create_resp.json()["id"]

    delete_resp = client.delete(f"/api/admin/interviews/{interview_id}")
    assert delete_resp.status_code == 204

    listed = client.get("/api/admin/interviews")
    assert listed.json() == []

    stored = db_session.get(Interview, interview_id)
    assert stored is not None
    assert stored.status.value == "cancelled"


def test_cancelled_interview_does_not_reappear_in_interviewer_list(client, db_session):
    admin = _admin_client(client, db_session)
    position = _make_position(db_session, admin)
    interviewer = User(
        email="iv4@example.com", password_hash=hash_password("pw"), full_name="Ivy", role=UserRole.interviewer
    )
    db_session.add(interviewer)
    db_session.commit()
    db_session.refresh(interviewer)
    candidate, round_ = _make_candidate_with_round(db_session, admin, position, interviewer)

    create_resp = client.post(
        "/api/admin/interviews",
        json={"round_id": round_.id, "scheduled_at": datetime.now(timezone.utc).isoformat()},
    )
    interview_id = create_resp.json()["id"]
    client.delete(f"/api/admin/interviews/{interview_id}")

    session = create_session(db_session, interviewer.id)
    client.cookies.set(SESSION_COOKIE_NAME, session.id)
    resp = client.get("/api/interviewer/interviews")
    assert resp.json() == []


def test_second_active_interview_for_same_round_rejected_at_db_level(client, db_session):
    import pytest
    from sqlalchemy.exc import IntegrityError

    admin = _admin_client(client, db_session)
    position = _make_position(db_session, admin)
    interviewer = User(
        email="iv5@example.com", password_hash=hash_password("pw"), full_name="Ivy", role=UserRole.interviewer
    )
    db_session.add(interviewer)
    db_session.commit()
    db_session.refresh(interviewer)
    candidate, round_ = _make_candidate_with_round(db_session, admin, position, interviewer)

    db_session.add(
        Interview(candidate_id=candidate.id, round_id=round_.id, scheduled_at=datetime.now(timezone.utc), created_by=admin.id)
    )
    db_session.commit()

    db_session.add(
        Interview(candidate_id=candidate.id, round_id=round_.id, scheduled_at=datetime.now(timezone.utc), created_by=admin.id)
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_interviewer_cannot_schedule_interviews(client, db_session):
    _admin_client(client, db_session)
    _interviewer_client(client, db_session, email="iv3@example.com")

    resp = client.post(
        "/api/admin/interviews",
        json={"round_id": 1, "scheduled_at": datetime.now(timezone.utc).isoformat()},
    )
    assert resp.status_code == 403

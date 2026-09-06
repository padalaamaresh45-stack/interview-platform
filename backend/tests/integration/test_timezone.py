from datetime import datetime, timedelta, timezone

from app.auth.hashing import hash_password
from app.auth.session import SESSION_COOKIE_NAME, create_session
from app.models.candidate import Candidate, CandidateStatus
from app.models.interview import Interview
from app.models.position import Position
from app.models.question import Question
from app.models.round import Round
from app.models.stage import Stage
from app.models.user import User, UserRole

EMAIL = "iv@example.com"
PASSWORD = "correct horse battery staple"


def _make_user(db_session, *, email=EMAIL, password=PASSWORD, role=UserRole.interviewer, tz=None):
    user = User(
        email=email,
        password_hash=hash_password(password),
        full_name="Ivy Interviewer",
        role=role,
        timezone=tz,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_first_login_sets_timezone_from_browser_inference(client, db_session):
    _make_user(db_session, tz=None)

    resp = client.post(
        "/api/auth/login",
        json={"email": EMAIL, "password": PASSWORD, "browser_timezone": "America/New_York"},
    )
    assert resp.status_code == 200
    assert resp.json()["timezone"] == "America/New_York"

    stored = db_session.query(User).filter(User.email == EMAIL).first()
    assert stored.timezone == "America/New_York"


def test_second_login_does_not_overwrite_a_manually_changed_timezone(client, db_session):
    user = _make_user(db_session, tz=None)

    client.post(
        "/api/auth/login",
        json={"email": EMAIL, "password": PASSWORD, "browser_timezone": "America/New_York"},
    )
    client.post("/api/auth/logout")

    # user manually corrects it via the profile setting
    db_session.query(User).filter(User.id == user.id).update({"timezone": "Asia/Kolkata"})
    db_session.commit()

    # a second login, from a browser in yet another zone (e.g. traveling),
    # must not silently reassign the profile timezone
    resp = client.post(
        "/api/auth/login",
        json={"email": EMAIL, "password": PASSWORD, "browser_timezone": "Europe/London"},
    )
    assert resp.status_code == 200
    assert resp.json()["timezone"] == "Asia/Kolkata"


def test_user_can_view_and_change_own_timezone(client, db_session):
    _make_user(db_session, tz="America/New_York")
    client.post("/api/auth/login", json={"email": EMAIL, "password": PASSWORD})

    me = client.get("/api/auth/me")
    assert me.json()["timezone"] == "America/New_York"

    updated = client.patch("/api/auth/me/timezone", json={"timezone": "Asia/Kolkata"})
    assert updated.status_code == 200
    assert updated.json()["timezone"] == "Asia/Kolkata"

    me_again = client.get("/api/auth/me")
    assert me_again.json()["timezone"] == "Asia/Kolkata"


def test_update_timezone_requires_authentication(client, db_session):
    resp = client.patch("/api/auth/me/timezone", json={"timezone": "Asia/Kolkata"})
    assert resp.status_code == 401


def _make_position_with_stage(db_session, admin, *, feedback_grace_hours=48):
    position = Position(title="Backend Engineer", created_by=admin.id)
    db_session.add(position)
    db_session.commit()
    db_session.refresh(position)

    question = Question(position_id=position.id, question_text="Q", sequence_order=1)
    db_session.add(question)

    db_session.query(Stage).filter(Stage.position_id == position.id).delete()
    stage = Stage(position_id=position.id, name="Screen", sequence_order=1, feedback_grace_hours=feedback_grace_hours)
    db_session.add(stage)
    db_session.commit()
    db_session.refresh(stage)
    return position, stage


def test_scorecard_due_at_is_derived_from_interview_end_plus_grace_period(client, db_session):
    admin = _make_user(db_session, email="admin@example.com", role=UserRole.admin)
    interviewer = _make_user(db_session, tz="America/New_York")
    position, stage = _make_position_with_stage(db_session, admin, feedback_grace_hours=48)

    candidate = Candidate(full_name="Cara Candidate", position_id=position.id, created_by=admin.id)
    db_session.add(candidate)
    db_session.flush()
    round_ = Round(candidate_id=candidate.id, stage_id=stage.id, assignee_id=interviewer.id)
    db_session.add(round_)
    db_session.commit()
    db_session.refresh(round_)

    scheduled_at = datetime(2026, 1, 15, 20, 0, tzinfo=timezone.utc)
    interview = Interview(
        candidate_id=candidate.id,
        round_id=round_.id,
        scheduled_at=scheduled_at,
        duration_minutes=60,
        created_by=admin.id,
    )
    db_session.add(interview)
    db_session.commit()

    interviewer_session = create_session(db_session, interviewer.id)
    client.cookies.set(SESSION_COOKIE_NAME, interviewer_session.id)

    resp = client.get("/api/interviewer/candidates")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    expected_due_at = scheduled_at + timedelta(hours=48 + 1)  # +1h interview duration
    assert body[0]["scorecard_due_at"] == expected_due_at.isoformat().replace("+00:00", "Z")

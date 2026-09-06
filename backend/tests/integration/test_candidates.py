from app.auth.hashing import hash_password
from app.auth.session import SESSION_COOKIE_NAME, create_session
from app.models.candidate import Candidate, CandidateStatus
from app.models.position import Position
from app.models.question import Question
from app.models.round import Round, RoundStatus
from app.models.stage import Stage
from app.models.user import User, UserRole

ADMIN_EMAIL = "admin@example.com"
ADMIN_PASSWORD = "correct horse battery staple"


def _make_user(db_session, *, email=ADMIN_EMAIL, password=ADMIN_PASSWORD, role=UserRole.admin, is_active=True):
    user = User(
        email=email,
        password_hash=hash_password(password),
        full_name="Test User",
        role=role,
        is_active=is_active,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _admin_client(client, db_session, *, email=ADMIN_EMAIL, password=ADMIN_PASSWORD):
    admin = _make_user(db_session, email=email, password=password)
    session = create_session(db_session, admin.id)
    client.cookies.set(SESSION_COOKIE_NAME, session.id)
    return admin


def _make_position(db_session, admin, *, title="Backend Engineer"):
    position = Position(title=title, created_by=admin.id)
    db_session.add(position)
    db_session.commit()
    db_session.refresh(position)
    return position


def _make_question(db_session, position, *, text="Tell me about yourself.", sequence_order=1):
    question = Question(position_id=position.id, question_text=text, sequence_order=sequence_order)
    db_session.add(question)
    db_session.commit()
    db_session.refresh(question)
    return question


def _make_candidate(db_session, admin, position, interviewer, *, status=CandidateStatus.not_started):
    candidate = Candidate(
        full_name="Cara Candidate",
        position_id=position.id,
        created_by=admin.id,
        status=status,
    )
    db_session.add(candidate)
    db_session.flush()
    first_stage_id = (
        db_session.query(Stage.id)
        .filter(Stage.position_id == position.id)
        .order_by(Stage.sequence_order)
        .limit(1)
        .scalar()
    )
    round_status = RoundStatus.scored if status == CandidateStatus.completed else RoundStatus.open
    db_session.add(
        Round(candidate_id=candidate.id, stage_id=first_stage_id, assignee_id=interviewer.id, status=round_status)
    )
    db_session.commit()
    db_session.refresh(candidate)
    return candidate


def test_create_against_zero_question_position_returns_400(client, db_session):
    admin = _admin_client(client, db_session)
    position = _make_position(db_session, admin)
    interviewer = _make_user(db_session, email="iv@example.com", role=UserRole.interviewer)

    resp = client.post(
        "/api/admin/candidates",
        json={"full_name": "No Questions Yet", "position_id": position.id, "interviewer_id": interviewer.id},
    )
    assert resp.status_code == 400


def test_create_against_valid_position_returns_201_not_started(client, db_session):
    admin = _admin_client(client, db_session)
    position = _make_position(db_session, admin)
    _make_question(db_session, position)
    interviewer = _make_user(db_session, email="iv@example.com", role=UserRole.interviewer)

    resp = client.post(
        "/api/admin/candidates",
        json={"full_name": "Cara Candidate", "position_id": position.id, "interviewer_id": interviewer.id},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "not_started"
    assert body["owner_id"] == interviewer.id


def test_edit_contact_fields_regardless_of_status(client, db_session):
    admin = _admin_client(client, db_session)
    position = _make_position(db_session, admin)
    _make_question(db_session, position)
    interviewer = _make_user(db_session, email="iv@example.com", role=UserRole.interviewer)

    not_started = _make_candidate(db_session, admin, position, interviewer)
    completed = _make_candidate(db_session, admin, position, interviewer, status=CandidateStatus.completed)

    for candidate in (not_started, completed):
        resp = client.patch(
            f"/api/admin/candidates/{candidate.id}",
            json={"full_name": "Updated Name", "email": "new@example.com", "phone": "555-0000"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["full_name"] == "Updated Name"
        assert body["email"] == "new@example.com"
        assert body["phone"] == "555-0000"


def test_delete_allowed_only_when_not_started(client, db_session):
    admin = _admin_client(client, db_session)
    position = _make_position(db_session, admin)
    _make_question(db_session, position)
    interviewer = _make_user(db_session, email="iv@example.com", role=UserRole.interviewer)

    not_started = _make_candidate(db_session, admin, position, interviewer)
    ok_resp = client.delete(f"/api/admin/candidates/{not_started.id}")
    assert ok_resp.status_code == 204

    completed = _make_candidate(db_session, admin, position, interviewer, status=CandidateStatus.completed)
    blocked_resp = client.delete(f"/api/admin/candidates/{completed.id}")
    assert blocked_resp.status_code == 400
    assert db_session.get(Candidate, completed.id) is not None


def test_deactivated_interviewer_excluded_from_picker_but_existing_assignment_unchanged(client, db_session):
    admin = _admin_client(client, db_session)
    position = _make_position(db_session, admin)
    _make_question(db_session, position)
    interviewer = _make_user(db_session, email="iv@example.com", role=UserRole.interviewer)
    candidate = _make_candidate(db_session, admin, position, interviewer)

    interviewer.is_active = False
    db_session.commit()

    picker_resp = client.get("/api/admin/interviewers")
    assert picker_resp.status_code == 200
    assert all(row["id"] != interviewer.id for row in picker_resp.json())

    detail_resp = client.get(f"/api/admin/candidates/{candidate.id}")
    assert detail_resp.status_code == 200
    assert detail_resp.json()["owner_id"] == interviewer.id

    interviewer_session = create_session(db_session, interviewer.id)
    client.cookies.set(SESSION_COOKIE_NAME, interviewer_session.id)
    queue_resp = client.get("/api/interviewer/candidates")
    assert queue_resp.status_code == 200
    assert any(row["id"] == candidate.id for row in queue_resp.json())


def test_interviewer_a_cannot_see_interviewer_b_candidate_in_queue(client, db_session):
    admin = _admin_client(client, db_session)
    position = _make_position(db_session, admin)
    _make_question(db_session, position)
    interviewer_a = _make_user(db_session, email="a@example.com", role=UserRole.interviewer)
    interviewer_b = _make_user(db_session, email="b@example.com", password="another password", role=UserRole.interviewer)
    candidate_b = _make_candidate(db_session, admin, position, interviewer_b)

    session_a = create_session(db_session, interviewer_a.id)
    client.cookies.set(SESSION_COOKIE_NAME, session_a.id)
    queue_resp = client.get("/api/interviewer/candidates")
    assert queue_resp.status_code == 200
    assert all(row["id"] != candidate_b.id for row in queue_resp.json())


def test_updated_at_bumps_on_edit(client, db_session):
    admin = _admin_client(client, db_session)
    position = _make_position(db_session, admin)
    _make_question(db_session, position)
    interviewer = _make_user(db_session, email="iv@example.com", role=UserRole.interviewer)
    candidate = _make_candidate(db_session, admin, position, interviewer)
    original_updated_at = candidate.updated_at.isoformat()

    resp = client.patch(f"/api/admin/candidates/{candidate.id}", json={"full_name": "Changed"})
    assert resp.status_code == 200
    assert resp.json()["updated_at"] != original_updated_at


def test_non_admin_gets_403_on_every_admin_route_in_this_module(client, db_session):
    admin = _admin_client(client, db_session)
    position = _make_position(db_session, admin)
    _make_question(db_session, position)
    interviewer = _make_user(db_session, email="iv@example.com", role=UserRole.interviewer)
    candidate = _make_candidate(db_session, admin, position, interviewer)

    other_interviewer = _make_user(
        db_session, email="other@example.com", password="another password", role=UserRole.interviewer
    )
    session = create_session(db_session, other_interviewer.id)
    client.cookies.set(SESSION_COOKIE_NAME, session.id)

    assert (
        client.post(
            "/api/admin/candidates",
            json={"full_name": "X", "position_id": position.id, "interviewer_id": interviewer.id},
        ).status_code
        == 403
    )
    assert client.get("/api/admin/candidates").status_code == 403
    assert client.get(f"/api/admin/candidates/{candidate.id}").status_code == 403
    assert client.patch(f"/api/admin/candidates/{candidate.id}", json={"full_name": "X"}).status_code == 403
    assert client.delete(f"/api/admin/candidates/{candidate.id}").status_code == 403
    assert client.get("/api/admin/interviewers").status_code == 403

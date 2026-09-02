from app.auth.hashing import hash_password
from app.auth.session import SESSION_COOKIE_NAME, create_session
from app.models.candidate import Candidate
from app.models.interview_score import InterviewScore
from app.models.position import Position
from app.models.question import Question
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


def test_create_and_edit_position_bumps_updated_at(client, db_session):
    admin = _admin_client(client, db_session)

    create_resp = client.post("/api/admin/positions", json={"title": "Backend Engineer"})
    assert create_resp.status_code == 201
    body = create_resp.json()
    assert body["title"] == "Backend Engineer"
    assert body["question_count"] == 0
    original_updated_at = body["updated_at"]

    edit_resp = client.patch(f"/api/admin/positions/{body['id']}", json={"title": "Senior Backend Engineer"})
    assert edit_resp.status_code == 200
    edited = edit_resp.json()
    assert edited["title"] == "Senior Backend Engineer"
    assert edited["updated_at"] != original_updated_at


def test_no_delete_route_exists_for_position(client, db_session):
    admin = _admin_client(client, db_session)
    position = _make_position(db_session, admin)

    resp = client.delete(f"/api/admin/positions/{position.id}")
    assert resp.status_code in (404, 405)


def test_questions_are_returned_in_sequence_order(client, db_session):
    admin = _admin_client(client, db_session)
    position = _make_position(db_session, admin)

    client.post(f"/api/admin/positions/{position.id}/questions", json={"question_text": "Second", "sequence_order": 2})
    client.post(f"/api/admin/positions/{position.id}/questions", json={"question_text": "First", "sequence_order": 1})

    resp = client.get(f"/api/admin/positions/{position.id}/questions")
    assert resp.status_code == 200
    texts = [q["question_text"] for q in resp.json()]
    assert texts == ["First", "Second"]


def test_sequence_order_collision_returns_clean_400(client, db_session):
    admin = _admin_client(client, db_session)
    position = _make_position(db_session, admin)

    first = client.post(
        f"/api/admin/positions/{position.id}/questions", json={"question_text": "Q1", "sequence_order": 1}
    )
    assert first.status_code == 201

    collision = client.post(
        f"/api/admin/positions/{position.id}/questions", json={"question_text": "Q2", "sequence_order": 1}
    )
    assert collision.status_code == 400


def _make_candidate(db_session, admin, position, interviewer):
    candidate = Candidate(
        full_name="Cara Candidate", position_id=position.id, interviewer_id=interviewer.id, created_by=admin.id
    )
    db_session.add(candidate)
    db_session.commit()
    db_session.refresh(candidate)
    return candidate


def test_edit_question_text_with_existing_scores_succeeds_and_leaves_scores_untouched(client, db_session):
    admin = _admin_client(client, db_session)
    position = _make_position(db_session, admin)
    question = _make_question(db_session, position)
    interviewer = _make_user(db_session, email="iv@example.com", role=UserRole.interviewer)
    candidate = _make_candidate(db_session, admin, position, interviewer)

    score = InterviewScore(question_id=question.id, candidate_id=candidate.id, score=4, comment="Solid answer.")
    db_session.add(score)
    db_session.commit()
    db_session.refresh(score)

    resp = client.patch(f"/api/admin/questions/{question.id}", json={"question_text": "Updated wording."})
    assert resp.status_code == 200
    assert resp.json()["question_text"] == "Updated wording."

    db_session.refresh(score)
    assert score.score == 4
    assert score.comment == "Solid answer."


def test_delete_question_with_zero_scores_succeeds(client, db_session):
    admin = _admin_client(client, db_session)
    position = _make_position(db_session, admin)
    question = _make_question(db_session, position)

    resp = client.delete(f"/api/admin/questions/{question.id}")
    assert resp.status_code == 204

    follow_up = client.get(f"/api/admin/positions/{position.id}/questions")
    assert follow_up.json() == []


def test_delete_question_with_scores_returns_400_naming_count(client, db_session):
    admin = _admin_client(client, db_session)
    position = _make_position(db_session, admin)
    question = _make_question(db_session, position)
    interviewer = _make_user(db_session, email="iv@example.com", role=UserRole.interviewer)

    for i in range(3):
        candidate = _make_candidate(db_session, admin, position, interviewer)
        db_session.add(InterviewScore(question_id=question.id, candidate_id=candidate.id, score=3))
    db_session.commit()

    resp = client.delete(f"/api/admin/questions/{question.id}")
    assert resp.status_code == 400
    assert "3" in resp.json()["detail"]


def test_position_list_includes_accurate_question_count_including_zero(client, db_session):
    admin = _admin_client(client, db_session)
    empty_position = _make_position(db_session, admin, title="Empty Role")
    staffed_position = _make_position(db_session, admin, title="Staffed Role")
    _make_question(db_session, staffed_position, text="Q1", sequence_order=1)
    _make_question(db_session, staffed_position, text="Q2", sequence_order=2)

    resp = client.get("/api/admin/positions")
    assert resp.status_code == 200
    by_id = {row["id"]: row["question_count"] for row in resp.json()}
    assert by_id[empty_position.id] == 0
    assert by_id[staffed_position.id] == 2


def test_non_admin_gets_403_on_every_route_in_this_module(client, db_session):
    admin = _admin_client(client, db_session)
    position = _make_position(db_session, admin)
    question = _make_question(db_session, position)

    interviewer = _make_user(
        db_session, email="interviewer@example.com", password="another password", role=UserRole.interviewer
    )
    interviewer_session = create_session(db_session, interviewer.id)
    client.cookies.set(SESSION_COOKIE_NAME, interviewer_session.id)

    assert client.post("/api/admin/positions", json={"title": "X"}).status_code == 403
    assert client.get("/api/admin/positions").status_code == 403
    assert client.patch(f"/api/admin/positions/{position.id}", json={"title": "X"}).status_code == 403
    assert (
        client.post(
            f"/api/admin/positions/{position.id}/questions", json={"question_text": "X", "sequence_order": 99}
        ).status_code
        == 403
    )
    assert client.get(f"/api/admin/positions/{position.id}/questions").status_code == 403
    assert client.patch(f"/api/admin/questions/{question.id}", json={"question_text": "X"}).status_code == 403
    assert client.delete(f"/api/admin/questions/{question.id}").status_code == 403

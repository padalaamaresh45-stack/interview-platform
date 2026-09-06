from app.auth.hashing import hash_password
from app.auth.session import SESSION_COOKIE_NAME, create_session
from app.models.candidate import Candidate
from app.models.position import Position
from app.models.question import Question
from app.models.round import Round
from app.models.stage import Stage
from app.models.user import User, UserRole

ADMIN_EMAIL = "admin@example.com"
ADMIN_PASSWORD = "correct horse battery staple"


def _make_user(db_session, *, email=ADMIN_EMAIL, password=ADMIN_PASSWORD, role=UserRole.admin, is_active=True):
    user = User(email=email, password_hash=hash_password(password), full_name="Test User", role=role, is_active=is_active)
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


def _make_candidate(db_session, admin, position, interviewer):
    candidate = Candidate(
        full_name="Cara Candidate",
        position_id=position.id,
        created_by=admin.id,
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
    db_session.add(Round(candidate_id=candidate.id, stage_id=first_stage_id, assignee_id=interviewer.id))
    db_session.commit()
    db_session.refresh(candidate)
    return candidate


def test_position_creation_seeds_default_stages(db_session):
    admin = _make_user(db_session)
    position = _make_position(db_session, admin)
    stages = db_session.query(Stage).filter(Stage.position_id == position.id).order_by(Stage.sequence_order).all()
    assert [s.name for s in stages] == ["Applied", "Screening", "Under review", "Offer", "Hired", "Rejected"]


def test_candidate_creation_enters_first_stage(db_session):
    admin = _make_user(db_session)
    position = _make_position(db_session, admin)
    interviewer = _make_user(db_session, email="iv@example.com", role=UserRole.interviewer)
    candidate = _make_candidate(db_session, admin, position, interviewer)

    first_stage = (
        db_session.query(Stage).filter(Stage.position_id == position.id).order_by(Stage.sequence_order).first()
    )
    assert first_stage.name == "Applied"

    from app.models.stage_transition import CandidateStageTransition

    transitions = (
        db_session.query(CandidateStageTransition)
        .filter(CandidateStageTransition.candidate_id == candidate.id)
        .all()
    )
    assert len(transitions) == 1
    assert transitions[0].to_stage_id == first_stage.id
    assert transitions[0].from_stage_id is None


def test_board_groups_candidates_by_current_stage(client, db_session):
    admin = _admin_client(client, db_session)
    position = _make_position(db_session, admin)
    _make_question(db_session, position)
    interviewer = _make_user(db_session, email="iv@example.com", role=UserRole.interviewer)
    candidate = _make_candidate(db_session, admin, position, interviewer)

    resp = client.get("/api/pipeline/board")
    assert resp.status_code == 200
    columns = resp.json()["columns"]
    applied_column = next(c for c in columns if c["stage"]["name"] == "Applied")
    assert [c["id"] for c in applied_column["candidates"]] == [candidate.id]
    assert applied_column["candidates"][0]["next_action"] == "Submit interview scores"
    assert applied_column["candidates"][0]["health"] == "on_track"


def test_move_candidate_writes_a_transition_and_moves_it_on_the_board(client, db_session):
    admin = _admin_client(client, db_session)
    position = _make_position(db_session, admin)
    _make_question(db_session, position)
    interviewer = _make_user(db_session, email="iv@example.com", role=UserRole.interviewer)
    candidate = _make_candidate(db_session, admin, position, interviewer)

    stages = db_session.query(Stage).filter(Stage.position_id == position.id).order_by(Stage.sequence_order).all()
    screening = stages[1]

    resp = client.post(f"/api/pipeline/candidates/{candidate.id}/move", json={"to_stage_id": screening.id})
    assert resp.status_code == 200
    body = resp.json()
    assert body["current_stage_id"] == screening.id
    assert len(body["stage_history"]) == 2
    assert body["stage_history"][0]["to_stage_name"] == "Screening"
    assert body["stage_history"][0]["from_stage_name"] == "Applied"

    board = client.get("/api/pipeline/board").json()
    screening_column = next(c for c in board["columns"] if c["stage"]["name"] == "Screening")
    assert [c["id"] for c in screening_column["candidates"]] == [candidate.id]
    applied_column = next(c for c in board["columns"] if c["stage"]["name"] == "Applied")
    assert applied_column["candidates"] == []


def test_move_to_stage_outside_position_is_rejected(client, db_session):
    admin = _admin_client(client, db_session)
    position_a = _make_position(db_session, admin, title="Backend Engineer")
    position_b = _make_position(db_session, admin, title="Designer")
    _make_question(db_session, position_a)
    interviewer = _make_user(db_session, email="iv@example.com", role=UserRole.interviewer)
    candidate = _make_candidate(db_session, admin, position_a, interviewer)

    other_stage = (
        db_session.query(Stage).filter(Stage.position_id == position_b.id).order_by(Stage.sequence_order).first()
    )

    resp = client.post(f"/api/pipeline/candidates/{candidate.id}/move", json={"to_stage_id": other_stage.id})
    assert resp.status_code == 400


def test_backward_move_between_non_terminal_stages_is_blocked_without_force(client, db_session):
    admin = _admin_client(client, db_session)
    position = _make_position(db_session, admin)
    _make_question(db_session, position)
    interviewer = _make_user(db_session, email="iv@example.com", role=UserRole.interviewer)
    candidate = _make_candidate(db_session, admin, position, interviewer)

    stages = {
        s.name: s for s in db_session.query(Stage).filter(Stage.position_id == position.id)
    }
    # Applied -> Under review (forward, no force needed)
    forward_resp = client.post(
        f"/api/pipeline/candidates/{candidate.id}/move", json={"to_stage_id": stages["Under review"].id}
    )
    assert forward_resp.status_code == 200

    # Under review -> Screening (backward, blocked without force)
    blocked_resp = client.post(
        f"/api/pipeline/candidates/{candidate.id}/move", json={"to_stage_id": stages["Screening"].id}
    )
    assert blocked_resp.status_code == 409

    forced_resp = client.post(
        f"/api/pipeline/candidates/{candidate.id}/move",
        json={"to_stage_id": stages["Screening"].id, "force": True},
    )
    assert forced_resp.status_code == 200
    assert forced_resp.json()["current_stage_id"] == stages["Screening"].id


def test_forward_move_between_non_terminal_stages_needs_no_force(client, db_session):
    admin = _admin_client(client, db_session)
    position = _make_position(db_session, admin)
    _make_question(db_session, position)
    interviewer = _make_user(db_session, email="iv@example.com", role=UserRole.interviewer)
    candidate = _make_candidate(db_session, admin, position, interviewer)

    stages = {
        s.name: s for s in db_session.query(Stage).filter(Stage.position_id == position.id)
    }
    resp = client.post(f"/api/pipeline/candidates/{candidate.id}/move", json={"to_stage_id": stages["Offer"].id})
    assert resp.status_code == 200
    assert resp.json()["current_stage_id"] == stages["Offer"].id


def test_moving_into_terminal_stage_needs_no_force_from_any_stage(client, db_session):
    admin = _admin_client(client, db_session)
    position = _make_position(db_session, admin)
    _make_question(db_session, position)
    interviewer = _make_user(db_session, email="iv@example.com", role=UserRole.interviewer)
    candidate = _make_candidate(db_session, admin, position, interviewer)

    stages = {
        s.name: s for s in db_session.query(Stage).filter(Stage.position_id == position.id)
    }
    # Candidate starts at Applied (sequence_order 1) — moving straight to
    # Rejected (sequence_order 6, terminal) skips every stage in between but
    # must still not require force, since the destination is terminal.
    resp = client.post(f"/api/pipeline/candidates/{candidate.id}/move", json={"to_stage_id": stages["Rejected"].id})
    assert resp.status_code == 200
    assert resp.json()["current_stage_id"] == stages["Rejected"].id


def test_list_stages_returns_terminal_stages_unfiltered(client, db_session):
    admin = _admin_client(client, db_session)
    position = _make_position(db_session, admin)

    resp = client.get(f"/api/pipeline/stages?position_id={position.id}")
    assert resp.status_code == 200
    names = [s["name"] for s in resp.json()]
    assert names == ["Applied", "Screening", "Under review", "Offer", "Hired", "Rejected"]
    terminal_flags = {s["name"]: s["is_terminal"] for s in resp.json()}
    assert terminal_flags == {
        "Applied": False,
        "Screening": False,
        "Under review": False,
        "Offer": False,
        "Hired": True,
        "Rejected": True,
    }


def test_move_out_of_terminal_stage_is_blocked_without_force(client, db_session):
    admin = _admin_client(client, db_session)
    position = _make_position(db_session, admin)
    _make_question(db_session, position)
    interviewer = _make_user(db_session, email="iv@example.com", role=UserRole.interviewer)
    candidate = _make_candidate(db_session, admin, position, interviewer)

    stages = {
        s.name: s for s in db_session.query(Stage).filter(Stage.position_id == position.id)
    }
    move_resp = client.post(f"/api/pipeline/candidates/{candidate.id}/move", json={"to_stage_id": stages["Hired"].id})
    assert move_resp.status_code == 200

    blocked_resp = client.post(
        f"/api/pipeline/candidates/{candidate.id}/move", json={"to_stage_id": stages["Rejected"].id}
    )
    assert blocked_resp.status_code == 409

    forced_resp = client.post(
        f"/api/pipeline/candidates/{candidate.id}/move",
        json={"to_stage_id": stages["Rejected"].id, "force": True},
    )
    assert forced_resp.status_code == 200
    assert forced_resp.json()["current_stage_id"] == stages["Rejected"].id


def test_candidate_in_terminal_stage_has_null_health_not_on_track(client, db_session):
    admin = _admin_client(client, db_session)
    position = _make_position(db_session, admin)
    _make_question(db_session, position)
    interviewer = _make_user(db_session, email="iv@example.com", role=UserRole.interviewer)
    candidate = _make_candidate(db_session, admin, position, interviewer)

    stages = {
        s.name: s for s in db_session.query(Stage).filter(Stage.position_id == position.id)
    }
    client.post(f"/api/pipeline/candidates/{candidate.id}/move", json={"to_stage_id": stages["Rejected"].id})

    history_resp = client.get(f"/api/pipeline/candidates/{candidate.id}")
    assert history_resp.json()["health"] is None

    board = client.get(f"/api/pipeline/board?position_id={position.id}").json()
    rejected_column = next(c for c in board["columns"] if c["stage"]["name"] == "Rejected")
    assert rejected_column["candidates"][0]["health"] is None


def test_candidate_history_includes_scores(client, db_session):
    admin = _admin_client(client, db_session)
    position = _make_position(db_session, admin)
    question = _make_question(db_session, position)
    interviewer = _make_user(db_session, email="iv@example.com", role=UserRole.interviewer)
    candidate = _make_candidate(db_session, admin, position, interviewer)

    from app.models.interview_score import InterviewScore

    round_ = db_session.query(Round).filter(Round.candidate_id == candidate.id).first()
    db_session.add(InterviewScore(candidate_id=candidate.id, round_id=round_.id, question_id=question.id, score=4))
    db_session.commit()

    resp = client.get(f"/api/pipeline/candidates/{candidate.id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["score"]["submitted_count"] == 1
    assert body["score"]["total_count"] == 1
    assert body["score"]["average"] == 4
    assert len(body["scores"]) == 1


def test_deleting_a_candidate_deletes_its_stage_transitions(client, db_session):
    admin = _admin_client(client, db_session)
    position = _make_position(db_session, admin)
    interviewer = _make_user(db_session, email="iv@example.com", role=UserRole.interviewer)
    candidate = _make_candidate(db_session, admin, position, interviewer)

    resp = client.delete(f"/api/admin/candidates/{candidate.id}")
    assert resp.status_code == 204

from app.auth.hashing import hash_password
from app.auth.session import SESSION_COOKIE_NAME, create_session
from app.models.candidate import Candidate
from app.models.interview_score import InterviewScore
from app.models.position import Position
from app.models.question import Question
from app.models.round import Round, RoundStatus
from app.models.stage import Stage
from app.models.user import User, UserRole

ADMIN_EMAIL = "admin@example.com"
ADMIN_PASSWORD = "correct horse battery staple"


def _make_user(db_session, *, email=ADMIN_EMAIL, password=ADMIN_PASSWORD, role=UserRole.admin, full_name="Test User"):
    user = User(email=email, password_hash=hash_password(password), full_name=full_name, role=role)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _login_as(client, db_session, user):
    session = create_session(db_session, user.id)
    client.cookies.set(SESSION_COOKIE_NAME, session.id)


def _make_position(db_session, admin, *, title="Backend Engineer"):
    position = Position(title=title, created_by=admin.id)
    db_session.add(position)
    db_session.commit()
    db_session.refresh(position)
    return position


def _make_question(db_session, position, *, text="Q", sequence_order=1):
    question = Question(position_id=position.id, question_text=text, sequence_order=sequence_order)
    db_session.add(question)
    db_session.commit()
    db_session.refresh(question)
    return question


def _first_stage_id(db_session, position):
    return (
        db_session.query(Stage.id)
        .filter(Stage.position_id == position.id)
        .order_by(Stage.sequence_order)
        .limit(1)
        .scalar()
    )


def _make_candidate(db_session, admin, position):
    candidate = Candidate(full_name="Cara Candidate", position_id=position.id, created_by=admin.id)
    db_session.add(candidate)
    db_session.commit()
    db_session.refresh(candidate)
    return candidate


def _make_round(db_session, candidate, stage_id, assignee, *, status=RoundStatus.open, closed_at=None):
    round_ = Round(
        candidate_id=candidate.id,
        stage_id=stage_id,
        assignee_id=assignee.id,
        status=status,
        closed_at=closed_at,
    )
    db_session.add(round_)
    db_session.commit()
    db_session.refresh(round_)
    return round_


def _score(db_session, candidate, round_, question, value, *, comment=None):
    s = InterviewScore(candidate_id=candidate.id, round_id=round_.id, question_id=question.id, score=value, comment=comment)
    db_session.add(s)
    db_session.commit()


def test_consolidation_lists_every_round_in_chronological_order_including_gap_states(client, db_session):
    admin = _make_user(db_session)
    _login_as(client, db_session, admin)
    position = _make_position(db_session, admin)
    question = _make_question(db_session, position)
    stage_id = _first_stage_id(db_session, position)
    interviewer_a = _make_user(db_session, email="a@example.com", role=UserRole.interviewer, full_name="Ivy A")
    interviewer_b = _make_user(db_session, email="b@example.com", role=UserRole.interviewer, full_name="Ivy B")
    candidate = _make_candidate(db_session, admin, position)

    round1 = _make_round(db_session, candidate, stage_id, interviewer_a, status=RoundStatus.reassigned)
    round2 = _make_round(db_session, candidate, stage_id, interviewer_b, status=RoundStatus.closed_unscored)
    round3 = _make_round(db_session, candidate, stage_id, interviewer_a, status=RoundStatus.scored)
    _score(db_session, candidate, round3, question, 4)

    resp = client.get(f"/api/pipeline/candidates/{candidate.id}/consolidation")
    assert resp.status_code == 200
    body = resp.json()

    assert [r["id"] for r in body["rounds"]] == [round1.id, round2.id, round3.id]
    assert [r["status"] for r in body["rounds"]] == ["reassigned", "closed_unscored", "scored"]
    assert body["rounds"][0]["average_score"] is None
    assert body["rounds"][1]["average_score"] is None
    assert body["rounds"][2]["average_score"] == 4.0


def test_consolidation_average_and_variance_exclude_unscored_rounds(client, db_session):
    admin = _make_user(db_session)
    _login_as(client, db_session, admin)
    position = _make_position(db_session, admin)
    question = _make_question(db_session, position)
    stage_id = _first_stage_id(db_session, position)
    interviewer_a = _make_user(db_session, email="a@example.com", role=UserRole.interviewer, full_name="Ivy A")
    interviewer_b = _make_user(db_session, email="b@example.com", role=UserRole.interviewer, full_name="Ivy B")
    candidate = _make_candidate(db_session, admin, position)

    # An unscored, closed round that must appear in the list but not the average.
    _make_round(db_session, candidate, stage_id, interviewer_a, status=RoundStatus.closed_unscored)

    round2 = _make_round(db_session, candidate, stage_id, interviewer_b, status=RoundStatus.scored)
    _score(db_session, candidate, round2, question, 1)
    round3 = _make_round(db_session, candidate, stage_id, interviewer_a, status=RoundStatus.scored)
    _score(db_session, candidate, round3, question, 5)

    resp = client.get(f"/api/pipeline/candidates/{candidate.id}/consolidation")
    assert resp.status_code == 200
    body = resp.json()

    assert len(body["rounds"]) == 3
    assert body["average_score"] == 3.0
    assert body["variance"] == 4.0
    assert body["split_decision"] is True


def test_consolidation_requires_admin(client, db_session):
    admin = _make_user(db_session)
    position = _make_position(db_session, admin)
    candidate = _make_candidate(db_session, admin, position)
    interviewer = _make_user(db_session, email="iv@example.com", role=UserRole.interviewer)
    _login_as(client, db_session, interviewer)

    resp = client.get(f"/api/pipeline/candidates/{candidate.id}/consolidation")
    assert resp.status_code == 403


def test_interviewer_endpoint_does_not_leak_another_rounds_score_before_own_round_closes(client, db_session):
    admin = _make_user(db_session)
    position = _make_position(db_session, admin)
    question = _make_question(db_session, position)
    stage_id = _first_stage_id(db_session, position)
    interviewer_a = _make_user(db_session, email="a@example.com", role=UserRole.interviewer, full_name="Ivy A")
    interviewer_b = _make_user(db_session, email="b@example.com", role=UserRole.interviewer, full_name="Ivy B")
    candidate = _make_candidate(db_session, admin, position)

    # Interviewer A already scored a prior round for this candidate...
    round_a = _make_round(db_session, candidate, stage_id, interviewer_a, status=RoundStatus.scored)
    _score(db_session, candidate, round_a, question, 5, comment="Great candidate")

    # ...interviewer B now has their own open round for the same candidate,
    # not yet scored.
    _make_round(db_session, candidate, stage_id, interviewer_b, status=RoundStatus.open)

    _login_as(client, db_session, interviewer_b)
    resp = client.get(f"/api/interviewer/candidates/{candidate.id}")
    assert resp.status_code == 200
    body = resp.json()

    # B's own round has no scores yet — A's scorecard must not leak through.
    assert body["scores"] == []


def test_interviewer_list_view_does_not_expose_other_rounds_score(client, db_session):
    admin = _make_user(db_session)
    position = _make_position(db_session, admin)
    question = _make_question(db_session, position)
    stage_id = _first_stage_id(db_session, position)
    interviewer_a = _make_user(db_session, email="a@example.com", role=UserRole.interviewer, full_name="Ivy A")
    interviewer_b = _make_user(db_session, email="b@example.com", role=UserRole.interviewer, full_name="Ivy B")
    candidate = _make_candidate(db_session, admin, position)

    round_a = _make_round(db_session, candidate, stage_id, interviewer_a, status=RoundStatus.scored)
    _score(db_session, candidate, round_a, question, 2)
    _make_round(db_session, candidate, stage_id, interviewer_b, status=RoundStatus.open)

    _login_as(client, db_session, interviewer_b)
    resp = client.get("/api/interviewer/candidates")
    assert resp.status_code == 200
    body = resp.json()
    mine = next((c for c in body if c["id"] == candidate.id), None)
    assert mine is not None
    # No field on the interviewer-facing list carries another round's score.
    assert "score" not in mine or mine.get("score") is None

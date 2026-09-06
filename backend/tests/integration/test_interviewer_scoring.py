import threading

from app.auth.hashing import hash_password
from app.auth.session import SESSION_COOKIE_NAME, create_session
from app.models.candidate import Candidate, CandidateStatus
from app.models.interview_score import InterviewScore
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


def _make_candidate(db_session, admin, position, interviewer, *, status=CandidateStatus.not_started):
    candidate = Candidate(
        full_name="Cara Candidate",
        position_id=position.id,
        created_by=admin.id,
        status=status,
    )
    db_session.add(candidate)
    db_session.flush()
    round_status = RoundStatus.scored if status == CandidateStatus.completed else RoundStatus.open
    round_ = Round(
        candidate_id=candidate.id,
        stage_id=_first_stage_id(db_session, position),
        assignee_id=interviewer.id,
        status=round_status,
    )
    db_session.add(round_)
    db_session.commit()
    db_session.refresh(candidate)
    db_session.refresh(round_)
    return candidate, round_


def _login_as(client, db_session, user):
    session = create_session(db_session, user.id)
    client.cookies.set(SESSION_COOKIE_NAME, session.id)


def _setup_two_questions(db_session):
    admin = _make_user(db_session)
    position = _make_position(db_session, admin)
    q1 = _make_question(db_session, position, text="Q1", sequence_order=1)
    q2 = _make_question(db_session, position, text="Q2", sequence_order=2)
    interviewer = _make_user(db_session, email="iv@example.com", role=UserRole.interviewer)
    candidate, round_ = _make_candidate(db_session, admin, position, interviewer)
    return admin, position, q1, q2, interviewer, candidate, round_


def test_full_valid_submit_completes_and_leaves_queue(client, db_session):
    admin, position, q1, q2, interviewer, candidate, round_ = _setup_two_questions(db_session)
    _login_as(client, db_session, interviewer)

    resp = client.post(
        f"/api/interviewer/rounds/{round_.id}/scores",
        json={"scores": [{"question_id": q1.id, "score": 4, "comment": "Good"}, {"question_id": q2.id, "score": 5}]},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "completed"

    rows = db_session.query(InterviewScore).filter(InterviewScore.round_id == round_.id).all()
    assert len(rows) == 2

    db_session.refresh(round_)
    assert round_.status == RoundStatus.scored

    queue = client.get("/api/interviewer/candidates")
    assert all(row["id"] != candidate.id for row in queue.json())


def test_missing_question_returns_400_and_writes_nothing(client, db_session):
    admin, position, q1, q2, interviewer, candidate, round_ = _setup_two_questions(db_session)
    _login_as(client, db_session, interviewer)

    resp = client.post(
        f"/api/interviewer/rounds/{round_.id}/scores",
        json={"scores": [{"question_id": q1.id, "score": 4}]},
    )
    assert resp.status_code == 400
    assert db_session.query(InterviewScore).filter(InterviewScore.round_id == round_.id).count() == 0
    db_session.refresh(candidate)
    assert candidate.status == CandidateStatus.not_started


def test_extra_unknown_question_returns_400_and_writes_nothing(client, db_session):
    admin, position, q1, q2, interviewer, candidate, round_ = _setup_two_questions(db_session)
    _login_as(client, db_session, interviewer)

    resp = client.post(
        f"/api/interviewer/rounds/{round_.id}/scores",
        json={
            "scores": [
                {"question_id": q1.id, "score": 4},
                {"question_id": q2.id, "score": 5},
                {"question_id": 999999, "score": 3},
            ]
        },
    )
    assert resp.status_code == 400
    assert db_session.query(InterviewScore).filter(InterviewScore.round_id == round_.id).count() == 0


def test_out_of_range_score_returns_400_and_writes_nothing(client, db_session):
    admin, position, q1, q2, interviewer, candidate, round_ = _setup_two_questions(db_session)
    _login_as(client, db_session, interviewer)

    for bad_score in (0, 6):
        resp = client.post(
            f"/api/interviewer/rounds/{round_.id}/scores",
            json={"scores": [{"question_id": q1.id, "score": bad_score}, {"question_id": q2.id, "score": 3}]},
        )
        assert resp.status_code == 400
        assert db_session.query(InterviewScore).filter(InterviewScore.round_id == round_.id).count() == 0
        db_session.refresh(candidate)
        assert candidate.status == CandidateStatus.not_started


def test_resubmit_against_scored_round_returns_409_no_duplicates(client, db_session):
    admin, position, q1, q2, interviewer, candidate, round_ = _setup_two_questions(db_session)
    _login_as(client, db_session, interviewer)

    payload = {"scores": [{"question_id": q1.id, "score": 4}, {"question_id": q2.id, "score": 5}]}
    first = client.post(f"/api/interviewer/rounds/{round_.id}/scores", json=payload)
    assert first.status_code == 200

    second = client.post(f"/api/interviewer/rounds/{round_.id}/scores", json=payload)
    assert second.status_code == 409

    rows = db_session.query(InterviewScore).filter(InterviewScore.round_id == round_.id).all()
    assert len(rows) == 2
    assert {(r.question_id, r.score) for r in rows} == {(q1.id, 4), (q2.id, 5)}


def test_comment_optional(client, db_session):
    admin, position, q1, q2, interviewer, candidate, round_ = _setup_two_questions(db_session)
    _login_as(client, db_session, interviewer)

    resp = client.post(
        f"/api/interviewer/rounds/{round_.id}/scores",
        json={"scores": [{"question_id": q1.id, "score": 4}, {"question_id": q2.id, "score": 5}]},
    )
    assert resp.status_code == 200


def test_interviewer_a_cannot_open_or_submit_against_interviewer_b_candidate(client, db_session):
    admin = _make_user(db_session)
    position = _make_position(db_session, admin)
    q1 = _make_question(db_session, position)
    interviewer_a = _make_user(db_session, email="a@example.com", role=UserRole.interviewer)
    interviewer_b = _make_user(db_session, email="b@example.com", password="another password", role=UserRole.interviewer)
    candidate_b, round_b = _make_candidate(db_session, admin, position, interviewer_b)

    _login_as(client, db_session, interviewer_a)

    get_resp = client.get(f"/api/interviewer/candidates/{candidate_b.id}")
    assert get_resp.status_code in (403, 404)

    submit_resp = client.post(
        f"/api/interviewer/rounds/{round_b.id}/scores",
        json={"scores": [{"question_id": q1.id, "score": 3}]},
    )
    assert submit_resp.status_code in (403, 404)
    assert db_session.query(InterviewScore).filter(InterviewScore.round_id == round_b.id).count() == 0


def test_submit_against_nonexistent_round_returns_404(client, db_session):
    admin, position, q1, q2, interviewer, candidate, round_ = _setup_two_questions(db_session)
    _login_as(client, db_session, interviewer)

    resp = client.post(
        "/api/interviewer/rounds/999999/scores",
        json={"scores": [{"question_id": q1.id, "score": 3}, {"question_id": q2.id, "score": 3}]},
    )
    assert resp.status_code == 404


def test_submit_against_closed_unscored_round_with_no_scorecard_succeeds_and_scores_it(client, db_session):
    # The round-1-late-submission case: an admin advanced the candidate while
    # this round was still open, closing it as closed_unscored. The
    # interviewer's late submission must still succeed and score it.
    admin, position, q1, q2, interviewer, candidate, round_ = _setup_two_questions(db_session)
    round_.status = RoundStatus.closed_unscored
    db_session.commit()
    _login_as(client, db_session, interviewer)

    resp = client.post(
        f"/api/interviewer/rounds/{round_.id}/scores",
        json={"scores": [{"question_id": q1.id, "score": 4}, {"question_id": q2.id, "score": 5}]},
    )
    assert resp.status_code == 200
    db_session.refresh(round_)
    assert round_.status == RoundStatus.scored


def test_concurrent_double_submit_yields_exactly_one_completed_and_one_409(client, db_session):
    admin, position, q1, q2, interviewer, candidate, round_ = _setup_two_questions(db_session)
    _login_as(client, db_session, interviewer)

    payload = {"scores": [{"question_id": q1.id, "score": 4}, {"question_id": q2.id, "score": 5}]}
    results = []

    def submit():
        resp = client.post(f"/api/interviewer/rounds/{round_.id}/scores", json=payload)
        results.append(resp.status_code)

    threads = [threading.Thread(target=submit) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert sorted(results) == [200, 409]
    rows = db_session.query(InterviewScore).filter(InterviewScore.round_id == round_.id).all()
    assert len(rows) == 2
    db_session.refresh(candidate)
    assert candidate.status == CandidateStatus.completed

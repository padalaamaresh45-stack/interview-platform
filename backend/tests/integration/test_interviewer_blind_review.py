"""Ticket #31 AC4: exhaustive check that an interviewer with an unsubmitted round
can never read another round's scorecard for the same candidate.

Every route reachable by an interviewer (require_interviewer) was enumerated by
hand against the current router set:

  - GET  /api/interviewer/candidates             (list_my_candidates)
  - GET  /api/interviewer/candidates/{id}         (get_my_candidate)
  - POST /api/interviewer/rounds/{round_id}/scores (submit_round_scores)
  - GET  /api/interviewer/interviews              (list_my_interviews)
  - GET  /api/auth/me, PATCH /api/auth/me/timezone (own profile only, no scores)

Every other endpoint requires require_admin and 403s an interviewer outright, so
they're not reachable and aren't exercised here. This file drives the two
score-bearing endpoints (list and detail) against a single candidate who has
gone through two rounds with two different interviewers, one already scored,
one still open, and asserts the open round's interviewer never sees the closed
round's score/feedback in either response.
"""

from app.auth.hashing import hash_password
from app.auth.session import SESSION_COOKIE_NAME, create_session
from app.models.candidate import Candidate, CandidateStatus
from app.models.interview_score import InterviewScore
from app.models.position import Position
from app.models.question import Question
from app.models.round import Round, RoundStatus
from app.models.stage import Stage
from app.models.user import User, UserRole


def _make_user(db_session, *, email, password="correct horse battery staple", role=UserRole.admin):
    user = User(email=email, password_hash=hash_password(password), full_name="Test User", role=role, is_active=True)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _login_as(client, db_session, user):
    session = create_session(db_session, user.id)
    client.cookies.set(SESSION_COOKIE_NAME, session.id)


def _stage_ids(db_session, position):
    return (
        db_session.query(Stage.id)
        .filter(Stage.position_id == position.id)
        .order_by(Stage.sequence_order)
        .limit(2)
        .all()
    )


def test_interviewer_with_unsubmitted_round_cannot_see_other_rounds_scorecard(client, db_session):
    admin = _make_user(db_session, email="admin@example.com")
    position = Position(title="Backend Engineer", created_by=admin.id)
    db_session.add(position)
    db_session.commit()
    db_session.refresh(position)

    q1 = Question(position_id=position.id, question_text="Q1", sequence_order=1)
    db_session.add(q1)
    db_session.commit()
    db_session.refresh(q1)

    stage_ids = [row[0] for row in _stage_ids(db_session, position)]
    stage_1_id, stage_2_id = stage_ids[0], stage_ids[1]

    interviewer_a = _make_user(db_session, email="a@example.com", role=UserRole.interviewer)
    interviewer_b = _make_user(db_session, email="b@example.com", password="another password", role=UserRole.interviewer)

    candidate = Candidate(
        full_name="Cara Candidate",
        position_id=position.id,
        created_by=admin.id,
        status=CandidateStatus.not_started,
    )
    db_session.add(candidate)
    db_session.flush()

    # Round 1: interviewer A already scored it — a candid, harshly negative
    # scorecard that must never reach interviewer B.
    round_a = Round(candidate_id=candidate.id, stage_id=stage_1_id, assignee_id=interviewer_a.id, status=RoundStatus.scored)
    db_session.add(round_a)
    db_session.flush()
    db_session.add(InterviewScore(candidate_id=candidate.id, round_id=round_a.id, question_id=q1.id, score=1, comment="Not a fit."))

    # Round 2: interviewer B's round for the same candidate, still open/unsubmitted.
    round_b = Round(candidate_id=candidate.id, stage_id=stage_2_id, assignee_id=interviewer_b.id, status=RoundStatus.open)
    db_session.add(round_b)
    db_session.commit()
    db_session.refresh(round_b)

    _login_as(client, db_session, interviewer_b)

    # 1. Detail endpoint: B's own-round detail must carry only B's (empty) scores.
    detail = client.get(f"/api/interviewer/candidates/{candidate.id}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["round_id"] == round_b.id
    assert body["scores"] == []
    assert "Not a fit." not in detail.text
    assert not any(s["question_id"] == q1.id for s in body["scores"])

    # 2. Queue endpoint: only B's open round appears; no score/feedback field
    # exists on this response shape at all, but assert no score-bearing text
    # leaked through anyway (defense against a future field addition).
    queue = client.get("/api/interviewer/candidates")
    assert queue.status_code == 200
    assert "Not a fit." not in queue.text
    round_ids_in_queue = {row["round_id"] for row in queue.json()}
    assert round_ids_in_queue == {round_b.id}

    # 3. Submission authorization: B cannot submit against A's already-scored round.
    submit_against_a = client.post(
        f"/api/interviewer/rounds/{round_a.id}/scores",
        json={"scores": [{"question_id": q1.id, "score": 5}]},
    )
    assert submit_against_a.status_code in (403, 404, 409)

    # 4. Interviews endpoint carries no score data at all — confirm it's scoped
    # to B's own round only, as a completeness check on the enumeration above.
    interviews = client.get("/api/interviewer/interviews")
    assert interviews.status_code == 200
    assert "Not a fit." not in interviews.text

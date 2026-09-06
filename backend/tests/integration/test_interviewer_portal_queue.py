from datetime import datetime, timedelta, timezone

from app.auth.hashing import hash_password
from app.auth.session import SESSION_COOKIE_NAME, create_session
from app.models.candidate import Candidate, CandidateStatus
from app.models.interview import Interview
from app.models.interview_score import InterviewScore
from app.models.position import Position
from app.models.question import Question
from app.models.round import Round, RoundStatus
from app.models.stage import Stage
from app.models.stage_transition import CandidateStageTransition
from app.models.user import User, UserRole

ADMIN_EMAIL = "admin@example.com"
ADMIN_PASSWORD = "correct horse battery staple"


def _make_user(db_session, *, email=ADMIN_EMAIL, password=ADMIN_PASSWORD, role=UserRole.admin):
    user = User(email=email, password_hash=hash_password(password), full_name="Test User", role=role, is_active=True)
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


def _stages(db_session, position):
    return db_session.query(Stage).filter(Stage.position_id == position.id).order_by(Stage.sequence_order).all()


def _make_candidate(db_session, admin, position, *, status=CandidateStatus.not_started):
    candidate = Candidate(full_name="Cara Candidate", position_id=position.id, created_by=admin.id, status=status)
    db_session.add(candidate)
    db_session.commit()
    db_session.refresh(candidate)
    return candidate


def _make_round(db_session, candidate, stage, interviewer, *, status=RoundStatus.open, brief=None):
    round_ = Round(candidate_id=candidate.id, stage_id=stage.id, assignee_id=interviewer.id, status=status, brief=brief)
    db_session.add(round_)
    db_session.commit()
    db_session.refresh(round_)
    return round_


def _make_interview(db_session, candidate, round_, admin, *, scheduled_at, duration_minutes=60):
    interview = Interview(
        candidate_id=candidate.id,
        round_id=round_.id,
        scheduled_at=scheduled_at,
        duration_minutes=duration_minutes,
        created_by=admin.id,
    )
    db_session.add(interview)
    db_session.commit()
    db_session.refresh(interview)
    return interview


def _make_transition(db_session, candidate, admin, *, from_stage_id, to_stage_id):
    transition = CandidateStageTransition(
        candidate_id=candidate.id, from_stage_id=from_stage_id, to_stage_id=to_stage_id, actor_id=admin.id
    )
    db_session.add(transition)
    db_session.commit()
    return transition


def _login_as(client, db_session, user):
    session = create_session(db_session, user.id)
    client.cookies.set(SESSION_COOKIE_NAME, session.id)


def test_portal_includes_open_and_closed_unscored_excludes_scored_and_reassigned(client, db_session):
    admin = _make_user(db_session)
    position = _make_position(db_session, admin)
    stage1, stage2 = _stages(db_session, position)[:2]
    interviewer = _make_user(db_session, email="iv@example.com", role=UserRole.interviewer)

    c_open = _make_candidate(db_session, admin, position)
    _make_round(db_session, c_open, stage1, interviewer, status=RoundStatus.open)

    c_closed_unscored = _make_candidate(db_session, admin, position)
    _make_round(db_session, c_closed_unscored, stage1, interviewer, status=RoundStatus.closed_unscored)

    c_scored = _make_candidate(db_session, admin, position)
    _make_round(db_session, c_scored, stage1, interviewer, status=RoundStatus.scored)

    c_reassigned = _make_candidate(db_session, admin, position)
    _make_round(db_session, c_reassigned, stage1, interviewer, status=RoundStatus.reassigned)

    _login_as(client, db_session, interviewer)
    resp = client.get("/api/interviewer/candidates")
    assert resp.status_code == 200
    candidate_ids = {row["candidate_id"] for row in resp.json()}
    assert candidate_ids == {c_open.id, c_closed_unscored.id}


def test_portal_sorts_by_soonest_due_date_with_unscheduled_trailing(client, db_session):
    admin = _make_user(db_session)
    position = _make_position(db_session, admin)
    stage1 = _stages(db_session, position)[0]
    interviewer = _make_user(db_session, email="iv@example.com", role=UserRole.interviewer)
    now = datetime.now(timezone.utc)

    unscheduled = _make_candidate(db_session, admin, position)
    _make_round(db_session, unscheduled, stage1, interviewer, status=RoundStatus.open)

    due_later = _make_candidate(db_session, admin, position)
    round_later = _make_round(db_session, due_later, stage1, interviewer, status=RoundStatus.open)
    _make_interview(db_session, due_later, round_later, admin, scheduled_at=now + timedelta(days=2))

    due_sooner = _make_candidate(db_session, admin, position)
    round_sooner = _make_round(db_session, due_sooner, stage1, interviewer, status=RoundStatus.open)
    _make_interview(db_session, due_sooner, round_sooner, admin, scheduled_at=now + timedelta(hours=1))

    _login_as(client, db_session, interviewer)
    resp = client.get("/api/interviewer/candidates")
    assert resp.status_code == 200
    ordered_ids = [row["candidate_id"] for row in resp.json()]
    assert ordered_ids == [due_sooner.id, due_later.id, unscheduled.id]


def test_no_active_interview_yields_needs_scheduling_state(client, db_session):
    admin = _make_user(db_session)
    position = _make_position(db_session, admin)
    stage1 = _stages(db_session, position)[0]
    interviewer = _make_user(db_session, email="iv@example.com", role=UserRole.interviewer)
    candidate = _make_candidate(db_session, admin, position)
    _make_round(db_session, candidate, stage1, interviewer, status=RoundStatus.open)

    _login_as(client, db_session, interviewer)
    resp = client.get("/api/interviewer/candidates")
    row = resp.json()[0]
    assert row["state"] == "needs_scheduling"
    assert row["scheduled_at"] is None
    assert row["scorecard_due_at"] is None


def test_future_interview_yields_scheduled_state(client, db_session):
    admin = _make_user(db_session)
    position = _make_position(db_session, admin)
    stage1 = _stages(db_session, position)[0]
    interviewer = _make_user(db_session, email="iv@example.com", role=UserRole.interviewer)
    candidate = _make_candidate(db_session, admin, position)
    round_ = _make_round(db_session, candidate, stage1, interviewer, status=RoundStatus.open)
    _make_interview(
        db_session, candidate, round_, admin, scheduled_at=datetime.now(timezone.utc) + timedelta(days=1)
    )

    _login_as(client, db_session, interviewer)
    resp = client.get("/api/interviewer/candidates")
    row = resp.json()[0]
    assert row["state"] == "scheduled"
    assert row["scheduled_at"] is not None


def test_past_due_scorecard_yields_overdue_state(client, db_session):
    admin = _make_user(db_session)
    position = _make_position(db_session, admin)
    stage1 = _stages(db_session, position)[0]
    interviewer = _make_user(db_session, email="iv@example.com", role=UserRole.interviewer)
    candidate = _make_candidate(db_session, admin, position)
    round_ = _make_round(db_session, candidate, stage1, interviewer, status=RoundStatus.open)
    # Interview ended well over the default 48h grace period ago.
    _make_interview(
        db_session, candidate, round_, admin, scheduled_at=datetime.now(timezone.utc) - timedelta(days=5)
    )

    _login_as(client, db_session, interviewer)
    resp = client.get("/api/interviewer/candidates")
    row = resp.json()[0]
    assert row["state"] == "overdue"
    assert row["is_closed_unscored"] is False


def test_closed_unscored_round_renders_overdue_bucket_with_next_stage_copy_data(client, db_session):
    admin = _make_user(db_session)
    position = _make_position(db_session, admin)
    stage1, stage2 = _stages(db_session, position)[:2]
    interviewer = _make_user(db_session, email="iv@example.com", role=UserRole.interviewer)
    candidate = _make_candidate(db_session, admin, position, status=CandidateStatus.not_started)
    _make_round(db_session, candidate, stage1, interviewer, status=RoundStatus.closed_unscored)
    _make_transition(db_session, candidate, admin, from_stage_id=stage1.id, to_stage_id=stage2.id)

    _login_as(client, db_session, interviewer)
    resp = client.get("/api/interviewer/candidates")
    row = resp.json()[0]
    assert row["state"] == "overdue"
    assert row["is_closed_unscored"] is True
    assert row["next_stage_name"] == stage2.name


def test_closed_unscored_next_stage_name_is_this_rounds_own_move_not_candidates_current_stage(client, db_session):
    # Candidate advanced twice since this round closed (stage1 -> stage2 ->
    # stage3): the row must name stage2 (what THIS round's closure led to),
    # not stage3 (the candidate's current stage today).
    admin = _make_user(db_session)
    position = _make_position(db_session, admin)
    stages = _stages(db_session, position)
    assert len(stages) >= 3
    stage1, stage2, stage3 = stages[:3]
    interviewer = _make_user(db_session, email="iv@example.com", role=UserRole.interviewer)
    candidate = _make_candidate(db_session, admin, position)
    _make_round(db_session, candidate, stage1, interviewer, status=RoundStatus.closed_unscored)
    _make_transition(db_session, candidate, admin, from_stage_id=stage1.id, to_stage_id=stage2.id)
    _make_transition(db_session, candidate, admin, from_stage_id=stage2.id, to_stage_id=stage3.id)

    _login_as(client, db_session, interviewer)
    resp = client.get("/api/interviewer/candidates")
    row = resp.json()[0]
    assert row["next_stage_name"] == stage2.name


def test_overdue_row_with_no_due_date_sorts_ahead_of_unscheduled_row_in_null_group(client, db_session):
    # A closed_unscored round whose Interview record no longer exists has no
    # computable scorecard_due_at, but it still represents owed feedback and
    # must not be indistinguishable from (or rank behind) a plain
    # not-yet-scheduled round in the null-due-date tail of the sort.
    admin = _make_user(db_session)
    position = _make_position(db_session, admin)
    stage1 = _stages(db_session, position)[0]
    interviewer = _make_user(db_session, email="iv@example.com", role=UserRole.interviewer)

    unscheduled = _make_candidate(db_session, admin, position)
    _make_round(db_session, unscheduled, stage1, interviewer, status=RoundStatus.open)

    overdue_no_interview = _make_candidate(db_session, admin, position)
    _make_round(db_session, overdue_no_interview, stage1, interviewer, status=RoundStatus.closed_unscored)

    _login_as(client, db_session, interviewer)
    resp = client.get("/api/interviewer/candidates")
    ordered = resp.json()
    assert [row["candidate_id"] for row in ordered] == [overdue_no_interview.id, unscheduled.id]


def test_no_other_interviewers_score_data_present_in_portal_response(client, db_session):
    admin = _make_user(db_session)
    position = _make_position(db_session, admin)
    stage1 = _stages(db_session, position)[0]
    interviewer_a = _make_user(db_session, email="a@example.com", role=UserRole.interviewer)
    interviewer_b = _make_user(db_session, email="b@example.com", password="another password", role=UserRole.interviewer)

    question = Question(position_id=position.id, question_text="Q", sequence_order=1)
    db_session.add(question)
    db_session.commit()
    db_session.refresh(question)

    candidate = _make_candidate(db_session, admin, position)
    round_b = _make_round(db_session, candidate, stage1, interviewer_b, status=RoundStatus.scored)
    db_session.add(InterviewScore(candidate_id=candidate.id, round_id=round_b.id, question_id=question.id, score=5))
    db_session.commit()

    round_a = _make_round(db_session, candidate, stage1, interviewer_a, status=RoundStatus.open)

    _login_as(client, db_session, interviewer_a)
    resp = client.get("/api/interviewer/candidates")
    body = resp.json()
    assert all("score" not in row for row in body)
    assert [row["round_id"] for row in body] == [round_a.id]

import threading

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.auth.hashing import hash_password
from app.models.candidate import Candidate
from app.models.position import Position
from app.models.round import Round, RoundStatus
from app.models.stage import Stage
from app.models.user import User, UserRole
from app.pipeline.rounds import close_and_open_round
from tests.conftest import TEST_DATABASE_URL


def _make_admin(db_session):
    admin = User(email="admin@example.com", password_hash=hash_password("pw"), full_name="Admin", role=UserRole.admin)
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)
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


def test_assigning_next_round_while_prior_open_closes_it_as_closed_unscored(db_session):
    admin = _make_admin(db_session)
    position = _make_position(db_session, admin)
    interviewer = _make_interviewer(db_session)
    candidate = _make_candidate(db_session, admin, position)
    stage_1, stage_2 = _stage_ids(db_session, position)[:2]

    prior = Round(candidate_id=candidate.id, stage_id=stage_1, assignee_id=interviewer.id)
    db_session.add(prior)
    db_session.commit()
    db_session.refresh(prior)

    new_round = close_and_open_round(
        db_session,
        candidate_id=candidate.id,
        new_stage_id=stage_2,
        new_assignee_id=interviewer.id,
    )

    db_session.refresh(prior)
    assert prior.status == RoundStatus.closed_unscored
    assert prior.closed_at is not None
    assert new_round.status == RoundStatus.open
    assert new_round.stage_id == stage_2


def test_assigning_next_round_when_prior_already_scored_leaves_it_untouched(db_session):
    admin = _make_admin(db_session)
    position = _make_position(db_session, admin)
    interviewer = _make_interviewer(db_session)
    candidate = _make_candidate(db_session, admin, position)
    stage_1, stage_2 = _stage_ids(db_session, position)[:2]

    prior = Round(
        candidate_id=candidate.id,
        stage_id=stage_1,
        assignee_id=interviewer.id,
        status=RoundStatus.scored,
        closed_at=None,
    )
    db_session.add(prior)
    db_session.commit()
    db_session.refresh(prior)
    original_closed_at = prior.closed_at

    close_and_open_round(
        db_session,
        candidate_id=candidate.id,
        new_stage_id=stage_2,
        new_assignee_id=interviewer.id,
    )

    db_session.refresh(prior)
    assert prior.status == RoundStatus.scored
    assert prior.closed_at == original_closed_at


def test_reassignment_path_closes_prior_as_reassigned_via_same_helper(db_session):
    admin = _make_admin(db_session)
    position = _make_position(db_session, admin)
    interviewer = _make_interviewer(db_session)
    other_interviewer = _make_interviewer(db_session, email="other@example.com")
    candidate = _make_candidate(db_session, admin, position)
    stage_1 = _stage_ids(db_session, position)[0]

    prior = Round(candidate_id=candidate.id, stage_id=stage_1, assignee_id=interviewer.id)
    db_session.add(prior)
    db_session.commit()
    db_session.refresh(prior)

    new_round = close_and_open_round(
        db_session,
        candidate_id=candidate.id,
        new_stage_id=stage_1,
        new_assignee_id=other_interviewer.id,
        prior_round_closed_status=RoundStatus.reassigned,
        reassigned_from_round_id=prior.id,
    )

    db_session.refresh(prior)
    assert prior.status == RoundStatus.reassigned
    assert new_round.reassigned_from_round_id == prior.id


def test_only_one_open_round_survives_concurrent_assign_next_round_calls(db_session):
    admin = _make_admin(db_session)
    position = _make_position(db_session, admin)
    interviewer = _make_interviewer(db_session)
    candidate = _make_candidate(db_session, admin, position)
    stage_ids = _stage_ids(db_session, position)
    stage_1 = stage_ids[0]
    db_session.commit()

    engine = create_engine(TEST_DATABASE_URL)
    Session = sessionmaker(bind=engine)
    results = []

    def assign():
        session = Session()
        try:
            close_and_open_round(
                session,
                candidate_id=candidate.id,
                new_stage_id=stage_1,
                new_assignee_id=interviewer.id,
            )
            results.append("ok")
        except Exception as exc:  # noqa: BLE001 - recording any failure mode, not swallowing
            results.append(type(exc).__name__)
        finally:
            session.close()

    threads = [threading.Thread(target=assign) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    engine.dispose()

    assert results.count("ok") == 2  # candidate-row lock serializes both calls; neither should error
    open_rounds = db_session.query(Round).filter(Round.candidate_id == candidate.id, Round.status == RoundStatus.open).all()
    assert len(open_rounds) == 1

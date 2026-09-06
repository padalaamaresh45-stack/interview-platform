import inspect

import pytest
from sqlalchemy.exc import IntegrityError

from app.auth.hashing import hash_password
from app.models.candidate import Candidate
from app.models.position import Position
from app.models.round import Round, RoundStatus
from app.models.stage import Stage
from app.models.user import User, UserRole
from app.pipeline.access import interviewer_has_access
from app.scoring import submit as submit_module


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


def test_access_true_for_open_round(db_session):
    admin = _make_admin(db_session)
    position = _make_position(db_session, admin)
    interviewer = _make_interviewer(db_session)
    candidate = _make_candidate(db_session, admin, position)
    db_session.add(
        Round(candidate_id=candidate.id, stage_id=_first_stage_id(db_session, position), assignee_id=interviewer.id)
    )
    db_session.commit()

    assert interviewer_has_access(db_session, candidate.id, interviewer.id) is True


def test_access_true_for_closed_round_regression_for_the_split_bug(db_session):
    # This split exists specifically so that submitting a scorecard (closing the
    # round) does not revoke the interviewer's access to the candidate.
    admin = _make_admin(db_session)
    position = _make_position(db_session, admin)
    interviewer = _make_interviewer(db_session)
    candidate = _make_candidate(db_session, admin, position)
    db_session.add(
        Round(
            candidate_id=candidate.id,
            stage_id=_first_stage_id(db_session, position),
            assignee_id=interviewer.id,
            status=RoundStatus.scored,
        )
    )
    db_session.commit()

    assert interviewer_has_access(db_session, candidate.id, interviewer.id) is True


def test_access_true_for_reassigned_round(db_session):
    admin = _make_admin(db_session)
    position = _make_position(db_session, admin)
    interviewer = _make_interviewer(db_session)
    candidate = _make_candidate(db_session, admin, position)
    db_session.add(
        Round(
            candidate_id=candidate.id,
            stage_id=_first_stage_id(db_session, position),
            assignee_id=interviewer.id,
            status=RoundStatus.reassigned,
        )
    )
    db_session.commit()

    assert interviewer_has_access(db_session, candidate.id, interviewer.id) is True


def test_access_false_when_no_round_at_all(db_session):
    admin = _make_admin(db_session)
    position = _make_position(db_session, admin)
    interviewer = _make_interviewer(db_session)
    candidate = _make_candidate(db_session, admin, position)

    assert interviewer_has_access(db_session, candidate.id, interviewer.id) is False


def test_rounds_partial_unique_index_rejects_second_open_round(db_session):
    admin = _make_admin(db_session)
    position = _make_position(db_session, admin)
    interviewer = _make_interviewer(db_session)
    candidate = _make_candidate(db_session, admin, position)
    stage_id = _first_stage_id(db_session, position)

    db_session.add(Round(candidate_id=candidate.id, stage_id=stage_id, assignee_id=interviewer.id))
    db_session.commit()

    db_session.add(Round(candidate_id=candidate.id, stage_id=stage_id, assignee_id=interviewer.id))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_submission_authorization_is_its_own_function_not_a_wrapper_around_access_or_ownership():
    # Strip the docstring so a mention in prose (explaining why it's separate)
    # doesn't get mistaken for a call.
    func = submit_module.submit_scores
    body_source = inspect.getsource(func).split('"""', 2)[-1]
    assert "interviewer_has_access(" not in body_source
    assert "compute_current_owner(" not in body_source
    assert "get_open_round(" not in body_source

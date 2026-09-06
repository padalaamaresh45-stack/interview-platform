"""Ticket #31 AC4: exhaustive check that an interviewer with an unsubmitted round
can never read another round's scorecard for the same candidate.

Route discovery is programmatic, not a hand-maintained docstring list: every
route in `app.routes` gated (anywhere in its dependency tree) by
`require_interviewer` is walked and exercised against a fixture where another
interviewer's round already holds a distinctive, sensitive scorecard. A route
added under `require_interviewer` next month is automatically picked up and
tested for the leak; the known-route-set assertion below additionally forces a
human to look at this file when the route set changes at all (new route, or
one removed), rather than letting the test go quiet.
"""

import pytest
from fastapi.routing import APIRoute

from app.auth.dependencies import require_interviewer
from app.auth.hashing import hash_password
from app.auth.session import SESSION_COOKIE_NAME, create_session
from app.main import app
from app.models.candidate import Candidate, CandidateStatus
from app.models.interview_score import InterviewScore
from app.models.question import Question
from app.models.round import Round, RoundStatus
from app.models.stage import Stage
from app.models.user import User, UserRole
from tests.integration.test_interviews import _admin_client, _make_position

# The leak-free assertion (below) covers any route landing under
# require_interviewer, known or not. This set exists on top of that so an
# added or removed route forces someone to look at this file rather than the
# test silently continuing to pass either way.
_KNOWN_INTERVIEWER_ROUTES = {
    ("GET", "/api/interviewer/candidates"),
    ("GET", "/api/interviewer/candidates/{candidate_id}"),
    ("POST", "/api/interviewer/rounds/{round_id}/scores"),
    ("GET", "/api/interviewer/interviews"),
}

_SENSITIVE_COMMENT = "Not a fit."


def _dependant_calls(dependant):
    calls = {dependant.call}
    for sub in dependant.dependencies:
        calls |= _dependant_calls(sub)
    return calls


def _interviewer_gated_routes():
    return [
        route
        for route in app.routes
        if isinstance(route, APIRoute) and require_interviewer in _dependant_calls(route.dependant)
    ]


def _stage_ids(db_session, position):
    return [
        row
        for (row,) in db_session.query(Stage.id)
        .filter(Stage.position_id == position.id)
        .order_by(Stage.sequence_order)
        .limit(2)
        .all()
    ]


def _build_two_round_candidate(db_session, admin):
    """Candidate with round_a (interviewer A, already scored, a sensitive
    comment) and round_b (interviewer B, still open) on two different stages
    of the same position."""
    position = _make_position(db_session, admin)
    q1 = Question(position_id=position.id, question_text="Q1", sequence_order=1)
    db_session.add(q1)
    db_session.commit()
    db_session.refresh(q1)

    stage_1_id, stage_2_id = _stage_ids(db_session, position)

    interviewer_a = User(
        email="a@example.com", password_hash=hash_password("pw-a"), full_name="Ivy A", role=UserRole.interviewer
    )
    interviewer_b = User(
        email="b@example.com", password_hash=hash_password("pw-b"), full_name="Ivy B", role=UserRole.interviewer
    )
    db_session.add_all([interviewer_a, interviewer_b])
    db_session.commit()
    db_session.refresh(interviewer_a)
    db_session.refresh(interviewer_b)

    candidate = Candidate(
        full_name="Cara Candidate", position_id=position.id, created_by=admin.id, status=CandidateStatus.not_started
    )
    db_session.add(candidate)
    db_session.flush()

    round_a = Round(
        candidate_id=candidate.id, stage_id=stage_1_id, assignee_id=interviewer_a.id, status=RoundStatus.scored
    )
    db_session.add(round_a)
    db_session.flush()
    db_session.add(
        InterviewScore(
            candidate_id=candidate.id, round_id=round_a.id, question_id=q1.id, score=1, comment=_SENSITIVE_COMMENT
        )
    )

    round_b = Round(
        candidate_id=candidate.id, stage_id=stage_2_id, assignee_id=interviewer_b.id, status=RoundStatus.open
    )
    db_session.add(round_b)
    db_session.commit()
    db_session.refresh(round_a)
    db_session.refresh(round_b)

    return candidate, round_a, round_b, interviewer_a, interviewer_b, q1


def test_known_interviewer_routes_unchanged(db_session):
    """Fails loudly the moment a route is added to or removed from
    require_interviewer's gate, so the change gets a human look rather than
    silently expanding or shrinking what this file actually exercises."""
    discovered = {(method, route.path) for route in _interviewer_gated_routes() for method in route.methods - {"HEAD", "OPTIONS"}}
    assert discovered == _KNOWN_INTERVIEWER_ROUTES, (
        "The set of require_interviewer-gated routes changed. Update "
        "_KNOWN_INTERVIEWER_ROUTES above (and the path-param substitution map "
        "in test_every_interviewer_route_is_leak_free if the new route takes "
        "a param this test doesn't already handle) after confirming the new "
        "route doesn't leak another round's score.\n"
        f"Discovered: {discovered}\nExpected:   {_KNOWN_INTERVIEWER_ROUTES}"
    )


def test_every_interviewer_route_is_leak_free(client, db_session):
    admin = _admin_client(client, db_session)
    candidate, round_a, round_b, interviewer_a, interviewer_b, q1 = _build_two_round_candidate(db_session, admin)

    # Log in as interviewer B — owns the still-open round, must never see A's.
    session = create_session(db_session, interviewer_b.id)
    client.cookies.set(SESSION_COOKIE_NAME, session.id)

    path_params = {"candidate_id": candidate.id, "round_id": round_a.id}

    for route in _interviewer_gated_routes():
        path = route.path
        for name, value in path_params.items():
            path = path.replace(f"{{{name}}}", str(value))
        if "{" in path:
            pytest.fail(
                f"Route {route.path} has a path param this test doesn't know how to fill in "
                "— add it to path_params above before this test can cover it."
            )

        for method in route.methods - {"HEAD", "OPTIONS"}:
            if method == "GET":
                resp = client.get(path)
            elif method == "POST":
                # A generic, schema-shaped body. Whether it 200s, 400s, 404s,
                # or 409s is not this test's concern — only whether the
                # response body ever carries interviewer A's scorecard text.
                resp = client.post(path, json={"scores": [{"question_id": q1.id, "score": 5}]})
            elif method == "PATCH":
                resp = client.patch(path, json={})
            else:
                pytest.fail(f"Route {route.path} uses method {method}, which this test doesn't know how to call.")

            assert _SENSITIVE_COMMENT not in resp.text, (
                f"{method} {path} leaked interviewer A's scorecard to interviewer B: {resp.text}"
            )

    # Positive control: confirm B's own round genuinely has no scorecard yet,
    # so the absence of the sensitive comment above is because it's scoped
    # correctly, not because B also can't see their own (legitimately empty)
    # data.
    detail = client.get(f"/api/interviewer/candidates/{candidate.id}")
    assert detail.status_code == 200
    assert detail.json()["round_id"] == round_b.id
    assert detail.json()["scores"] == []

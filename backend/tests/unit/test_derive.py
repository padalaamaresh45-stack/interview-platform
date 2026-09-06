from dataclasses import dataclass

from app.models.candidate import CandidateStatus
from app.pipeline.derive import compute_current_owner, compute_health, compute_next_action


@dataclass
class _FakeRound:
    assignee_id: int


def test_compute_current_owner_none_when_no_open_round():
    assert compute_current_owner(None) is None


def test_compute_current_owner_returns_assignee_when_open_round_present():
    assert compute_current_owner(_FakeRound(assignee_id=42)) == 42


def test_compute_health_on_track_when_under_limit():
    assert compute_health(2, 5, is_terminal=False) == "on_track"


def test_compute_health_stalled_when_over_limit():
    assert compute_health(6, 5, is_terminal=False) == "stalled"


def test_compute_health_on_track_when_no_limit():
    assert compute_health(100, None, is_terminal=False) == "on_track"


def test_compute_health_none_when_terminal_even_if_would_otherwise_stall():
    assert compute_health(999, 5, is_terminal=True) is None


def test_compute_health_none_when_terminal_with_no_limit():
    assert compute_health(0, None, is_terminal=True) is None


def test_compute_next_action_none_when_terminal():
    result = compute_next_action(
        candidate_status=CandidateStatus.completed,
        is_terminal=True,
        score_summary=_score(submitted=1, total=1),
    )
    assert result == "None"


def test_compute_next_action_submit_scores_when_not_started_and_not_terminal():
    result = compute_next_action(
        candidate_status=CandidateStatus.not_started,
        is_terminal=False,
        score_summary=_score(submitted=0, total=1),
    )
    assert result == "Submit interview scores"


def _score(*, submitted, total):
    from app.pipeline.derive import ScoreSummary

    return ScoreSummary(submitted_count=submitted, total_count=total, average=None)

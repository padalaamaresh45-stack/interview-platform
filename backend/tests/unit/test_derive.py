from dataclasses import dataclass

from app.models.candidate import CandidateStatus
from app.models.round import RoundStatus
from app.pipeline.derive import (
    compute_current_owner,
    compute_gap_state,
    compute_health,
    compute_next_action,
    compute_score_variance,
    compute_scorecard_due_at,
    compute_threshold_routing,
    is_split_decision,
)


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


def test_compute_next_action_awaiting_decision_reads_as_admin_task_not_interviewer_stall():
    result = compute_next_action(
        candidate_status=CandidateStatus.completed,
        is_terminal=False,
        score_summary=_score(submitted=2, total=2),
        gap_state="awaiting_decision",
        days_in_stage=3,
    )
    assert result == "Record decision — waiting 3d"
    assert "stall" not in result.lower() and "overdue" not in result.lower()


def test_compute_health_stalled_when_scorecard_overdue_even_under_day_limit():
    assert compute_health(1, 30, is_terminal=False, scorecard_overdue=True) == "stalled"


def test_compute_health_on_track_when_not_overdue_and_under_limit():
    assert compute_health(1, 30, is_terminal=False, scorecard_overdue=False) == "on_track"


def test_compute_health_none_when_terminal_even_if_scorecard_overdue():
    assert compute_health(1, 30, is_terminal=True, scorecard_overdue=True) is None


# --- threshold routing ---


def test_routing_above_advance_threshold_routes_to_assignment():
    assert compute_threshold_routing(5.0, advance_threshold=4) == "awaiting_assignment"


def test_routing_at_advance_threshold_routes_to_assignment():
    assert compute_threshold_routing(4.0, advance_threshold=4) == "awaiting_assignment"


def test_routing_below_advance_but_above_reject_routes_to_decision():
    assert compute_threshold_routing(3.0, advance_threshold=4) == "awaiting_decision"


def test_routing_at_or_below_reject_threshold_routes_to_decision_never_auto_rejects():
    assert compute_threshold_routing(1.0, advance_threshold=4) == "awaiting_decision"


def test_routing_both_thresholds_null_routes_to_decision():
    assert compute_threshold_routing(5.0, advance_threshold=None) == "awaiting_decision"


def test_routing_null_average_score_routes_to_decision():
    assert compute_threshold_routing(None, advance_threshold=4) == "awaiting_decision"


# --- compute_gap_state ---


def test_gap_state_terminal_wins_over_everything():
    assert (
        compute_gap_state(
            is_terminal=True,
            hold_reason="visa issue",
            has_open_round=True,
            open_round_has_active_interview=True,
            latest_closed_round_status=None,
            latest_round_average_score=None,
            advance_threshold=None,
        )
        == "terminal"
    )


def test_gap_state_on_hold():
    assert (
        compute_gap_state(
            is_terminal=False,
            hold_reason="visa issue",
            has_open_round=True,
            open_round_has_active_interview=False,
            latest_closed_round_status=None,
            latest_round_average_score=None,
            advance_threshold=None,
        )
        == "on_hold"
    )


def test_gap_state_assigned_but_unscheduled():
    assert (
        compute_gap_state(
            is_terminal=False,
            hold_reason=None,
            has_open_round=True,
            open_round_has_active_interview=False,
            latest_closed_round_status=None,
            latest_round_average_score=None,
            advance_threshold=None,
        )
        == "assigned_but_unscheduled"
    )


def test_gap_state_none_when_open_round_scheduled_and_in_progress():
    assert (
        compute_gap_state(
            is_terminal=False,
            hold_reason=None,
            has_open_round=True,
            open_round_has_active_interview=True,
            latest_closed_round_status=None,
            latest_round_average_score=None,
            advance_threshold=None,
        )
        is None
    )


def test_gap_state_awaiting_assignment_when_no_round_ever():
    assert (
        compute_gap_state(
            is_terminal=False,
            hold_reason=None,
            has_open_round=False,
            open_round_has_active_interview=False,
            latest_closed_round_status=None,
            latest_round_average_score=None,
            advance_threshold=None,
        )
        == "awaiting_assignment"
    )


def test_gap_state_awaiting_decision_after_scored_round_below_threshold():
    assert (
        compute_gap_state(
            is_terminal=False,
            hold_reason=None,
            has_open_round=False,
            open_round_has_active_interview=False,
            latest_closed_round_status=RoundStatus.scored,
            latest_round_average_score=2.0,
            advance_threshold=4,
        )
        == "awaiting_decision"
    )


def test_gap_state_awaiting_assignment_after_scored_round_above_threshold():
    assert (
        compute_gap_state(
            is_terminal=False,
            hold_reason=None,
            has_open_round=False,
            open_round_has_active_interview=False,
            latest_closed_round_status=RoundStatus.scored,
            latest_round_average_score=5.0,
            advance_threshold=4,
        )
        == "awaiting_assignment"
    )


# --- score variance / split decision ---


def test_score_variance_none_with_fewer_than_two_rounds():
    assert compute_score_variance([4.0]) is None
    assert compute_score_variance([]) is None


def test_score_variance_zero_when_rounds_agree():
    assert compute_score_variance([3.0, 3.0, 3.0]) == 0.0


def test_score_variance_positive_when_rounds_disagree():
    assert compute_score_variance([1.0, 5.0]) == 4.0


def test_is_split_decision_false_with_low_variance():
    assert is_split_decision([3.0, 3.2]) is False


def test_is_split_decision_true_with_high_variance():
    assert is_split_decision([1.0, 5.0]) is True


def test_is_split_decision_false_with_single_round():
    assert is_split_decision([4.0]) is False


# --- scorecard_due_at ---


def test_scorecard_due_at_adds_grace_hours_to_interview_end():
    from datetime import datetime, timezone

    end = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)
    due = compute_scorecard_due_at(end, feedback_grace_hours=24)
    assert due == datetime(2026, 1, 2, 10, 0, tzinfo=timezone.utc)


def test_scorecard_due_at_defaults_to_48h_when_grace_hours_is_none():
    from datetime import datetime, timezone

    end = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)
    due = compute_scorecard_due_at(end, feedback_grace_hours=None)
    assert due == datetime(2026, 1, 3, 10, 0, tzinfo=timezone.utc)

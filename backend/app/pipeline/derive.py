"""The single place daysInStage, health, nextAction, gapState, and the score
summary are computed. Every caller (board, candidate detail) must go through
here — never recompute any of these fields inline in a router or on the
frontend, or the board and the candidate page will silently disagree with
each other.

compute_health, compute_next_action, and compute_gap_state all read the same
shape of inputs (current round, its interview, Candidate.hold_reason,
stage.is_terminal) and must ship together in the same PR whenever any one of
them changes — this is the explicit fix for the drift the UI audit caught in
§4.1, where compute_health and compute_next_action independently handled (or
forgot to handle) terminal stages."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.models.candidate import CandidateStatus
from app.models.round import RoundStatus

# Variance (in score points^2) above which two-or-more scored rounds for the
# same candidate count as a "split decision" — panel disagreement worth an
# admin's attention, not a hard statistical cutoff.
SPLIT_DECISION_VARIANCE_THRESHOLD = 1.0

DEFAULT_FEEDBACK_GRACE_HOURS = 48


@dataclass(frozen=True)
class ScoreSummary:
    submitted_count: int
    total_count: int
    average: float | None


@dataclass(frozen=True)
class DerivedCandidateFields:
    current_stage_id: int
    current_stage_name: str
    days_in_stage: int
    health: str | None  # "on_track" | "stalled" | None (terminal stage: not applicable)
    next_action: str
    score: ScoreSummary


def compute_days_in_stage(entered_stage_at: datetime, *, now: datetime | None = None) -> int:
    now = now or datetime.now(timezone.utc)
    if entered_stage_at.tzinfo is None:
        entered_stage_at = entered_stage_at.replace(tzinfo=timezone.utc)
    return max((now - entered_stage_at).days, 0)


def compute_scorecard_due_at(
    interview_end_at: datetime, feedback_grace_hours: int | None
) -> datetime:
    """scorecard_due_at is derived, never stored: interview end + the stage's
    feedback_grace_hours (default 48h if the stage hasn't set one). Never the
    interview's own start/end time by itself — nobody writes feedback during
    the meeting."""
    if interview_end_at.tzinfo is None:
        interview_end_at = interview_end_at.replace(tzinfo=timezone.utc)
    grace_hours = feedback_grace_hours if feedback_grace_hours is not None else DEFAULT_FEEDBACK_GRACE_HOURS
    return interview_end_at + timedelta(hours=grace_hours)


def compute_health(
    days_in_stage: int,
    day_limit: int | None,
    is_terminal: bool,
    *,
    scorecard_overdue: bool = False,
) -> str | None:
    # A hired or rejected candidate cannot stall — health is inapplicable for a
    # terminal stage, not a default "on_track". None forces every caller to
    # handle the absence rather than silently defaulting.
    if is_terminal:
        return None
    if scorecard_overdue:
        return "stalled"
    if day_limit is not None and days_in_stage > day_limit:
        return "stalled"
    return "on_track"


def compute_score_summary(scores: list, total_questions: int) -> ScoreSummary:
    if not scores:
        return ScoreSummary(submitted_count=0, total_count=total_questions, average=None)
    average = sum(s.score for s in scores) / len(scores)
    return ScoreSummary(submitted_count=len(scores), total_count=total_questions, average=round(average, 2))


def compute_threshold_routing(average_score: float | None, advance_threshold: int | None) -> str:
    """Routing only, never a final decision: a round scoring at/above the
    stage's advance_threshold routes to "awaiting_assignment". Everything else
    — below the advance bar, a stage with no thresholds configured at all, or
    a score at/below reject_threshold — routes to "awaiting_decision". There is
    deliberately no path here that returns anything else: a low score is never
    auto-rejected, it always lands in front of a human."""
    if advance_threshold is not None and average_score is not None and average_score >= advance_threshold:
        return "awaiting_assignment"
    return "awaiting_decision"


def compute_score_variance(round_averages: list[float]) -> float | None:
    """Population variance across each scored round's own average — the input
    to the "split decision" badge and to #31's consolidation view. None (not
    zero) when fewer than two rounds have scored, since variance across a
    single data point isn't meaningful."""
    if len(round_averages) < 2:
        return None
    mean = sum(round_averages) / len(round_averages)
    return round(sum((v - mean) ** 2 for v in round_averages) / len(round_averages), 4)


def is_split_decision(round_averages: list[float]) -> bool:
    variance = compute_score_variance(round_averages)
    return variance is not None and variance > SPLIT_DECISION_VARIANCE_THRESHOLD


def compute_gap_state(
    *,
    is_terminal: bool,
    hold_reason: str | None,
    has_open_round: bool,
    open_round_has_active_interview: bool,
    latest_closed_round_status: RoundStatus | None,
    latest_round_average_score: float | None,
    advance_threshold: int | None,
) -> str | None:
    """The candidate-level gap state — separate from a single Round's status
    (a Round's `open`/`scored`/etc. describes one round; this describes what
    the candidate as a whole is waiting on). Returns None when there is no
    gap at all (an open round with a scheduled interview, proceeding normally)
    — every other state names a distinct wait:

    - "terminal": is_terminal wins over everything else, same ordering as
      compute_health.
    - "on_hold": Candidate.hold_reason set. Overrides open-round shape below —
      hold suspends health/next-action framing regardless of round state.
    - "assigned_but_unscheduled": an open Round exists with no active
      Interview yet.
    - None: an open Round exists with an active Interview — in progress, no
      gap to report.
    - "awaiting_assignment" / "awaiting_decision": no open Round. Either the
      candidate has never had one assigned (or the last one closed as
      closed_unscored/reassigned with nothing resolved) — awaiting_assignment
      — or the last round scored, in which case compute_threshold_routing
      decides between the two.
    """
    if is_terminal:
        return "terminal"
    if hold_reason is not None:
        return "on_hold"
    if has_open_round:
        return None if open_round_has_active_interview else "assigned_but_unscheduled"
    if latest_closed_round_status == RoundStatus.scored:
        return compute_threshold_routing(latest_round_average_score, advance_threshold)
    return "awaiting_assignment"


def compute_next_action(
    *,
    candidate_status: CandidateStatus,
    is_terminal: bool,
    score_summary: ScoreSummary,
    gap_state: str | None = None,
    days_in_stage: int = 0,
) -> str:
    if is_terminal:
        return "None"
    if gap_state == "awaiting_decision":
        # Deliberately admin-task framing, not interviewer-stall language —
        # this is the one place that distinction is made; see compute_health
        # for the (separate) health-signal side of the same state.
        return f"Record decision — waiting {days_in_stage}d"
    if candidate_status == CandidateStatus.not_started:
        return "Submit interview scores"
    if score_summary.submitted_count < score_summary.total_count:
        return "Finish submitting interview scores"
    return "Review scores and decide"


def compute_current_owner(open_round) -> int | None:
    """A candidate's current owner is the assignee of its single open Round —
    never derived from a stored column. `open_round` is that Round (or None if
    the candidate has none), fetched by the caller via the partial-unique-index
    -backed query in app.pipeline.access.get_open_round."""
    return open_round.assignee_id if open_round is not None else None


def derive_candidate_fields(
    *,
    candidate_status: CandidateStatus,
    current_stage_id: int,
    current_stage_name: str,
    stage_day_limit: int | None,
    is_terminal: bool,
    entered_stage_at: datetime,
    scores: list,
    total_questions: int,
    now: datetime | None = None,
) -> DerivedCandidateFields:
    days_in_stage = compute_days_in_stage(entered_stage_at, now=now)
    health = compute_health(days_in_stage, stage_day_limit, is_terminal=is_terminal)
    score_summary = compute_score_summary(scores, total_questions)
    next_action = compute_next_action(
        candidate_status=candidate_status,
        is_terminal=is_terminal,
        score_summary=score_summary,
    )
    return DerivedCandidateFields(
        current_stage_id=current_stage_id,
        current_stage_name=current_stage_name,
        days_in_stage=days_in_stage,
        health=health,
        next_action=next_action,
        score=score_summary,
    )

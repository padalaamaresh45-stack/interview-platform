"""The single place daysInStage, health, nextAction and the score summary are
computed. Every caller (board, candidate detail) must go through here — never
recompute any of these fields inline in a router or on the frontend, or the
board and the candidate page will silently disagree with each other."""

from dataclasses import dataclass
from datetime import datetime, timezone

from app.models.candidate import CandidateStatus


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
    health: str  # "on_track" | "stalled"
    next_action: str
    score: ScoreSummary


def compute_days_in_stage(entered_stage_at: datetime, *, now: datetime | None = None) -> int:
    now = now or datetime.now(timezone.utc)
    if entered_stage_at.tzinfo is None:
        entered_stage_at = entered_stage_at.replace(tzinfo=timezone.utc)
    return max((now - entered_stage_at).days, 0)


def compute_health(days_in_stage: int, day_limit: int | None) -> str:
    if day_limit is not None and days_in_stage > day_limit:
        return "stalled"
    return "on_track"


def compute_score_summary(scores: list, total_questions: int) -> ScoreSummary:
    if not scores:
        return ScoreSummary(submitted_count=0, total_count=total_questions, average=None)
    average = sum(s.score for s in scores) / len(scores)
    return ScoreSummary(submitted_count=len(scores), total_count=total_questions, average=round(average, 2))

def compute_next_action(
    *,
    candidate_status: CandidateStatus,
    current_stage_name: str,
    score_summary: ScoreSummary,
) -> str:
    if current_stage_name in ("Hired", "Rejected"):
        return "None"
    if candidate_status == CandidateStatus.not_started:
        return "Submit interview scores"
    if score_summary.submitted_count < score_summary.total_count:
        return "Finish submitting interview scores"
    return "Review scores and decide"


def derive_candidate_fields(
    *,
    candidate_status: CandidateStatus,
    current_stage_id: int,
    current_stage_name: str,
    stage_day_limit: int | None,
    entered_stage_at: datetime,
    scores: list,
    total_questions: int,
    now: datetime | None = None,
) -> DerivedCandidateFields:
    days_in_stage = compute_days_in_stage(entered_stage_at, now=now)
    health = compute_health(days_in_stage, stage_day_limit)
    score_summary = compute_score_summary(scores, total_questions)
    next_action = compute_next_action(
        candidate_status=candidate_status,
        current_stage_name=current_stage_name,
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

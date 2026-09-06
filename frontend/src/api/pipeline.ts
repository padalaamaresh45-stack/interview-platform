import { apiFetch } from "./client";

export interface Stage {
  id: number;
  position_id: number;
  name: string;
  sequence_order: number;
  day_limit: number | null;
  is_terminal: boolean;
}

export interface ScoreSummary {
  submitted_count: number;
  total_count: number;
  average: number | null;
}

export interface BoardCandidate {
  id: number;
  full_name: string;
  position_id: number;
  position_title: string;
  owner_id: number | null;
  status: "not_started" | "completed";
  current_stage_id: number;
  days_in_stage: number;
  health: "on_track" | "stalled" | null;
  next_action: string;
  gap_state:
    | "terminal"
    | "on_hold"
    | "assigned_but_unscheduled"
    | "awaiting_assignment"
    | "awaiting_decision"
    | null;
  score: ScoreSummary;
}

export interface BoardColumn {
  stage: Stage;
  candidates: BoardCandidate[];
}

export interface Board {
  columns: BoardColumn[];
}

export interface StageTransition {
  id: number;
  from_stage_id: number | null;
  from_stage_name: string | null;
  to_stage_id: number;
  to_stage_name: string;
  actor_id: number;
  actor_name: string;
  created_at: string;
}

export interface InterviewScore {
  id: number;
  candidate_id: number;
  question_id: number;
  score: number;
  comment: string | null;
  created_at: string;
}

export interface CandidateHistory {
  id: number;
  full_name: string;
  position_id: number;
  position_title: string;
  status: "not_started" | "completed";
  current_stage_id: number;
  current_stage_name: string;
  days_in_stage: number;
  health: "on_track" | "stalled" | null;
  next_action: string;
  score: ScoreSummary;
  stage_history: StageTransition[];
  scores: InterviewScore[];
}

export interface RoundConsolidation {
  id: number;
  stage_id: number;
  stage_name: string;
  assignee_id: number;
  assignee_name: string;
  status: "open" | "scored" | "reassigned" | "closed_unscored";
  created_at: string;
  closed_at: string | null;
  average_score: number | null;
  scores: InterviewScore[];
}

export interface Consolidation {
  candidate_id: number;
  rounds: RoundConsolidation[];
  average_score: number | null;
  variance: number | null;
  split_decision: boolean;
}

async function parseOrThrow<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail ?? "Something went wrong.");
  }
  return res.json();
}

export async function getBoard(positionId?: number): Promise<Board> {
  const query = positionId ? `?position_id=${positionId}` : "";
  return parseOrThrow(await apiFetch(`/api/pipeline/board${query}`));
}

export async function listStages(positionId: number): Promise<Stage[]> {
  return parseOrThrow(await apiFetch(`/api/pipeline/stages?position_id=${positionId}`));
}

export async function getCandidateHistory(candidateId: number): Promise<CandidateHistory> {
  return parseOrThrow(await apiFetch(`/api/pipeline/candidates/${candidateId}`));
}

export async function getConsolidation(candidateId: number): Promise<Consolidation> {
  return parseOrThrow(await apiFetch(`/api/pipeline/candidates/${candidateId}/consolidation`));
}

// Thrown when the server refuses a move because the candidate is currently
// in a terminal stage (Hired/Rejected) and the caller didn't pass force —
// callers catch this specifically to confirm with the user before retrying
// with force: true, rather than surfacing it as a generic error.
export class TerminalStageMoveError extends Error {}

export async function moveCandidate(
  candidateId: number,
  toStageId: number,
  force = false,
): Promise<CandidateHistory> {
  const res = await apiFetch(`/api/pipeline/candidates/${candidateId}/move`, {
    method: "POST",
    body: JSON.stringify({ to_stage_id: toStageId, force }),
  });
  if (res.status === 409) {
    const body = await res.json().catch(() => null);
    throw new TerminalStageMoveError(body?.detail ?? "Candidate is in a terminal stage.");
  }
  return parseOrThrow(res);
}

import { apiFetch } from "./client";
import type { Candidate } from "./candidates";

export interface InterviewQuestion {
  id: number;
  position_id: number;
  question_text: string;
  sequence_order: number;
  created_at: string;
  updated_at: string;
}

export interface ExistingScore {
  id: number;
  candidate_id: number;
  question_id: number;
  score: number;
  comment: string | null;
  created_at: string;
}

export interface CandidateDetail {
  id: number;
  full_name: string;
  email: string | null;
  phone: string | null;
  position_id: number;
  status: "not_started" | "completed";
  round_id: number | null;
  questions: InterviewQuestion[];
  scores: ExistingScore[];
}

async function parseOrThrow<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail ?? "Something went wrong.");
  }
  return res.json();
}

export async function listMyCandidates(): Promise<Candidate[]> {
  return parseOrThrow(await apiFetch("/api/interviewer/candidates"));
}

export async function getMyCandidate(id: number): Promise<CandidateDetail> {
  return parseOrThrow(await apiFetch(`/api/interviewer/candidates/${id}`));
}

export interface ScoreSubmission {
  question_id: number;
  score: number;
  comment?: string | null;
}

export async function submitScores(roundId: number, scores: ScoreSubmission[]): Promise<Candidate> {
  return parseOrThrow(
    await apiFetch(`/api/interviewer/rounds/${roundId}/scores`, {
      method: "POST",
      body: JSON.stringify({ scores }),
    }),
  );
}

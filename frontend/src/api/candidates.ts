import { apiFetch } from "./client";

export interface Candidate {
  id: number;
  full_name: string;
  email: string | null;
  phone: string | null;
  position_id: number;
  owner_id: number | null;
  open_round_id: number | null;
  status: "not_started" | "completed";
  hold_reason: string | null;
  hold_review_by: string | null;
  created_by: number;
  created_at: string;
  updated_at: string;
}

export interface Interviewer {
  id: number;
  full_name: string;
  email: string;
  timezone: string | null;
}

async function parseOrThrow<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail ?? "Something went wrong.");
  }
  return res.json();
}

export async function listCandidates(): Promise<Candidate[]> {
  return parseOrThrow(await apiFetch("/api/admin/candidates"));
}

export async function getCandidate(id: number): Promise<Candidate> {
  return parseOrThrow(await apiFetch(`/api/admin/candidates/${id}`));
}

export async function listActiveInterviewers(): Promise<Interviewer[]> {
  return parseOrThrow(await apiFetch("/api/admin/interviewers"));
}

export async function createCandidate(
  full_name: string,
  position_id: number,
  interviewer_id: number,
  email?: string,
  phone?: string,
): Promise<Candidate> {
  return parseOrThrow(
    await apiFetch("/api/admin/candidates", {
      method: "POST",
      body: JSON.stringify({ full_name, position_id, interviewer_id, email: email || null, phone: phone || null }),
    }),
  );
}

export async function updateCandidate(
  id: number,
  updates: Partial<Pick<Candidate, "full_name" | "email" | "phone">>,
): Promise<Candidate> {
  return parseOrThrow(
    await apiFetch(`/api/admin/candidates/${id}`, {
      method: "PATCH",
      body: JSON.stringify(updates),
    }),
  );
}

export async function reassignRound(candidateId: number, assigneeId: number): Promise<void> {
  await parseOrThrow(
    await apiFetch(`/api/admin/candidates/${candidateId}/rounds/reassign`, {
      method: "POST",
      body: JSON.stringify({ assignee_id: assigneeId }),
    }),
  );
}

export async function deleteCandidate(id: number): Promise<void> {
  const res = await apiFetch(`/api/admin/candidates/${id}`, { method: "DELETE" });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail ?? "Something went wrong.");
  }
}

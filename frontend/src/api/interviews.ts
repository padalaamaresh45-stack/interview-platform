import { apiFetch } from "./client";

export interface Interview {
  id: number;
  candidate_id: number;
  candidate_name: string;
  position_title: string;
  round_id: number;
  interviewer_id: number;
  interviewer_name: string;
  status: "scheduled" | "cancelled";
  scheduled_at: string;
  duration_minutes: number;
  notes: string | null;
  created_at: string;
}

async function parseOrThrow<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail ?? "Something went wrong.");
  }
  return res.json();
}

export async function listAllInterviews(): Promise<Interview[]> {
  return parseOrThrow(await apiFetch("/api/admin/interviews"));
}

export async function listMyInterviews(): Promise<Interview[]> {
  return parseOrThrow(await apiFetch("/api/interviewer/interviews"));
}

export async function scheduleInterview(
  roundId: number,
  scheduledAt: string,
  durationMinutes: number,
  notes?: string,
): Promise<Interview> {
  return parseOrThrow(
    await apiFetch("/api/admin/interviews", {
      method: "POST",
      body: JSON.stringify({
        round_id: roundId,
        scheduled_at: scheduledAt,
        duration_minutes: durationMinutes,
        notes: notes || null,
      }),
    }),
  );
}

export async function cancelInterview(id: number): Promise<void> {
  const res = await apiFetch(`/api/admin/interviews/${id}`, { method: "DELETE" });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail ?? "Something went wrong.");
  }
}

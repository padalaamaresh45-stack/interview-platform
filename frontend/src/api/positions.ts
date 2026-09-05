import { apiFetch } from "./client";

export interface Position {
  id: number;
  title: string;
  question_count: number;
  candidate_count: number;
  created_at: string;
  updated_at: string;
}

export interface Question {
  id: number;
  position_id: number;
  question_text: string;
  sequence_order: number;
  created_at: string;
  updated_at: string;
}

async function parseOrThrow<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail ?? "Something went wrong.");
  }
  return res.json();
}

export async function listPositions(): Promise<Position[]> {
  const res = await apiFetch("/api/admin/positions");
  return parseOrThrow(res);
}

export async function getPosition(id: number): Promise<Position | undefined> {
  const positions = await listPositions();
  return positions.find((position) => position.id === id);
}

export async function createPosition(title: string): Promise<Position> {
  const res = await apiFetch("/api/admin/positions", {
    method: "POST",
    body: JSON.stringify({ title }),
  });
  return parseOrThrow(res);
}

export async function updatePosition(id: number, title: string): Promise<Position> {
  const res = await apiFetch(`/api/admin/positions/${id}`, {
    method: "PATCH",
    body: JSON.stringify({ title }),
  });
  return parseOrThrow(res);
}

export async function listQuestions(positionId: number): Promise<Question[]> {
  const res = await apiFetch(`/api/admin/positions/${positionId}/questions`);
  return parseOrThrow(res);
}

export async function createQuestion(
  positionId: number,
  question_text: string,
  sequence_order: number,
): Promise<Question> {
  const res = await apiFetch(`/api/admin/positions/${positionId}/questions`, {
    method: "POST",
    body: JSON.stringify({ question_text, sequence_order }),
  });
  return parseOrThrow(res);
}

export async function updateQuestion(id: number, question_text: string): Promise<Question> {
  const res = await apiFetch(`/api/admin/questions/${id}`, {
    method: "PATCH",
    body: JSON.stringify({ question_text }),
  });
  return parseOrThrow(res);
}

export async function deleteQuestion(id: number): Promise<void> {
  const res = await apiFetch(`/api/admin/questions/${id}`, { method: "DELETE" });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail ?? "Something went wrong.");
  }
}

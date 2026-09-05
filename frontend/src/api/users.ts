import { apiFetch } from "./client";

export interface AdminUser {
  id: number;
  email: string;
  full_name: string;
  role: "admin" | "interviewer";
  is_active: boolean;
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

async function okOrThrow(res: Response): Promise<void> {
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail ?? "Something went wrong.");
  }
}

export async function listUsers(): Promise<AdminUser[]> {
  const res = await apiFetch("/api/admin/users");
  return parseOrThrow(res);
}

export async function createUser(
  email: string,
  password: string,
  full_name: string,
  role: "admin" | "interviewer",
): Promise<AdminUser> {
  const res = await apiFetch("/api/admin/users", {
    method: "POST",
    body: JSON.stringify({ email, password, full_name, role }),
  });
  return parseOrThrow(res);
}

export async function updateUserName(id: number, full_name: string): Promise<AdminUser> {
  const res = await apiFetch(`/api/admin/users/${id}`, {
    method: "PATCH",
    body: JSON.stringify({ full_name }),
  });
  return parseOrThrow(res);
}

export async function deactivateUser(id: number): Promise<void> {
  await okOrThrow(await apiFetch(`/api/admin/users/${id}/deactivate`, { method: "POST" }));
}

export async function reactivateUser(id: number): Promise<void> {
  await okOrThrow(await apiFetch(`/api/admin/users/${id}/reactivate`, { method: "POST" }));
}

export async function resetPassword(id: number, new_password: string): Promise<void> {
  await okOrThrow(
    await apiFetch(`/api/admin/users/${id}/reset-password`, {
      method: "POST",
      body: JSON.stringify({ new_password }),
    }),
  );
}

import { apiFetch } from "./client";

export interface CurrentUser {
  id: number;
  email: string;
  full_name: string;
  role: "admin" | "interviewer";
}

export async function login(email: string, password: string): Promise<CurrentUser> {
  const res = await apiFetch("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail ?? "Invalid email or password.");
  }
  return res.json();
}

export async function logout(): Promise<void> {
  await apiFetch("/api/auth/logout", { method: "POST" });
}

export async function fetchCurrentUser(): Promise<CurrentUser | null> {
  const res = await apiFetch("/api/auth/me");
  if (!res.ok) {
    return null;
  }
  return res.json();
}

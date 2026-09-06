import { apiFetch } from "./client";
import { browserTimezone } from "../utils/timezone";

export interface CurrentUser {
  id: number;
  email: string;
  full_name: string;
  role: "admin" | "interviewer";
  timezone: string | null;
}

export async function login(email: string, password: string): Promise<CurrentUser> {
  const res = await apiFetch("/api/auth/login", {
    method: "POST",
    // browser_timezone is only ever used server-side to fill in a null
    // User.timezone on this user's very first login — sending it on every
    // login is harmless because the backend ignores it once a timezone is
    // already set.
    body: JSON.stringify({ email, password, browser_timezone: browserTimezone() }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail ?? "Invalid email or password.");
  }
  return res.json();
}

export async function updateMyTimezone(timezone: string): Promise<CurrentUser> {
  const res = await apiFetch("/api/auth/me/timezone", {
    method: "PATCH",
    body: JSON.stringify({ timezone }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail ?? "Something went wrong.");
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

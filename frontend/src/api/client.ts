const BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export async function apiFetch(path: string, init?: RequestInit) {
  return fetch(`${BASE_URL}${path}`, {
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    ...init,
  });
}

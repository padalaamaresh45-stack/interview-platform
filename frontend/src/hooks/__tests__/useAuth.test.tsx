import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AuthProvider, useAuth } from "../useAuth";
import { fetchCurrentUser } from "../../api/auth";

vi.mock("../../api/auth", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../api/auth")>();
  return { ...actual, fetchCurrentUser: vi.fn() };
});

const mockFetchCurrentUser = vi.mocked(fetchCurrentUser);

function Probe() {
  const { user, initializing } = useAuth();
  if (initializing) return <p>checking session…</p>;
  return <p>{user ? `logged in as ${user.email}` : "not logged in"}</p>;
}

afterEach(() => {
  vi.resetAllMocks();
});

describe("AuthProvider", () => {
  it("starts in an initializing state and does not assume the user is logged out", () => {
    mockFetchCurrentUser.mockReturnValue(new Promise(() => {}));
    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );
    expect(screen.getByText("checking session…")).toBeInTheDocument();
  });

  it("rehydrates the user from an existing valid session cookie on mount", async () => {
    mockFetchCurrentUser.mockResolvedValue({
      id: 1,
      email: "admin@example.com",
      full_name: "Ada Admin",
      role: "admin",
      timezone: null,
    });
    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );
    await waitFor(() => expect(screen.getByText("logged in as admin@example.com")).toBeInTheDocument());
  });

  it("settles to logged-out when there is no valid session", async () => {
    mockFetchCurrentUser.mockResolvedValue(null);
    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );
    await waitFor(() => expect(screen.getByText("not logged in")).toBeInTheDocument());
  });

  it("settles to logged-out instead of an unhandled rejection when the session check itself fails (backend down, CORS, network)", async () => {
    mockFetchCurrentUser.mockRejectedValue(new Error("Failed to fetch"));
    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );
    await waitFor(() => expect(screen.getByText("not logged in")).toBeInTheDocument());
  });
});

import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { AuthenticatedShell } from "../AuthenticatedShell";
import { useAuth } from "../../hooks/useAuth";

vi.mock("../../hooks/useAuth");

const mockUseAuth = vi.mocked(useAuth);

function renderShell() {
  return render(
    <MemoryRouter initialEntries={["/"]}>
      <Routes>
        <Route path="/login" element={<p>Login page</p>} />
        <Route element={<AuthenticatedShell />}>
          <Route path="/" element={<p>Protected content</p>} />
        </Route>
      </Routes>
    </MemoryRouter>,
  );
}

describe("AuthenticatedShell", () => {
  it("shows a loading state instead of redirecting while the session check is in flight", () => {
    mockUseAuth.mockReturnValue({ user: null, initializing: true, login: vi.fn(), logout: vi.fn(), updateTimezone: vi.fn() });
    renderShell();
    expect(screen.getByText("Loading…")).toBeInTheDocument();
    expect(screen.queryByText("Login page")).not.toBeInTheDocument();
    expect(screen.queryByText("Protected content")).not.toBeInTheDocument();
  });

  it("redirects to /login instead of rendering protected content when there is no session", () => {
    mockUseAuth.mockReturnValue({ user: null, initializing: false, login: vi.fn(), logout: vi.fn(), updateTimezone: vi.fn() });
    renderShell();
    expect(screen.getByText("Login page")).toBeInTheDocument();
    expect(screen.queryByText("Protected content")).not.toBeInTheDocument();
  });

  it("renders admin-only navigation for an admin session", () => {
    mockUseAuth.mockReturnValue({
      user: { id: 1, email: "admin@example.com", full_name: "Ada Admin", role: "admin", timezone: null },
      initializing: false,
      login: vi.fn(),
      logout: vi.fn(),
      updateTimezone: vi.fn(),
    });
    renderShell();
    expect(screen.getByText("Protected content")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Positions" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Users" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Candidates" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "My Candidates" })).not.toBeInTheDocument();
  });

  it("renders only the interviewer's own queue link for an interviewer session, not admin surfaces", () => {
    mockUseAuth.mockReturnValue({
      user: { id: 2, email: "iv@example.com", full_name: "Ivy Interviewer", role: "interviewer", timezone: null },
      initializing: false,
      login: vi.fn(),
      logout: vi.fn(),
      updateTimezone: vi.fn(),
    });
    renderShell();
    expect(screen.getByRole("link", { name: "My Candidates" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Positions" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Users" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Candidates" })).not.toBeInTheDocument();
  });
});

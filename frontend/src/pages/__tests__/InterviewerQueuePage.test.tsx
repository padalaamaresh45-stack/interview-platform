import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { InterviewerQueuePage } from "../InterviewerQueuePage";
import { listMyCandidates, type InterviewerQueueRow } from "../../api/interviewer";
import { useAuth } from "../../hooks/useAuth";

vi.mock("../../api/interviewer");
vi.mock("../../hooks/useAuth");

const mockListMyCandidates = vi.mocked(listMyCandidates);
const mockUseAuth = vi.mocked(useAuth);

function renderQueue() {
  return render(
    <MemoryRouter>
      <InterviewerQueuePage />
    </MemoryRouter>,
  );
}

function makeRow(overrides: Partial<InterviewerQueueRow> = {}): InterviewerQueueRow {
  return {
    round_id: 1,
    candidate_id: 1,
    candidate_full_name: "Cara Candidate",
    stage_name: "Phone Screen",
    scheduled_at: null,
    brief: null,
    scorecard_due_at: null,
    state: "needs_scheduling",
    is_closed_unscored: false,
    next_stage_name: null,
    ...overrides,
  };
}

afterEach(() => {
  vi.resetAllMocks();
});

beforeEach(() => {
  mockUseAuth.mockReturnValue({
    user: { id: 9, email: "iv@example.com", full_name: "Ivy Interviewer", role: "interviewer", timezone: "America/New_York" },
    initializing: false,
    login: vi.fn(),
    logout: vi.fn(),
    updateTimezone: vi.fn(),
  });
});

describe("InterviewerQueuePage", () => {
  it("shows a loading state before candidates load", () => {
    mockListMyCandidates.mockReturnValue(new Promise(() => {}));
    renderQueue();
    expect(screen.getByText("Loading…")).toBeInTheDocument();
  });

  it("shows a clear empty-state message when there are no assigned candidates", async () => {
    mockListMyCandidates.mockResolvedValue([]);
    renderQueue();
    expect(await screen.findByText("You have no assigned candidates right now.")).toBeInTheDocument();
  });

  it("lists assigned candidates once loaded", async () => {
    mockListMyCandidates.mockResolvedValue([makeRow()]);
    renderQueue();
    expect(await screen.findByRole("link", { name: /Cara Candidate/ })).toBeInTheDocument();
  });

  it("renders assigned rounds as table rows linked to the candidate, not the round", async () => {
    mockListMyCandidates.mockResolvedValue([makeRow({ round_id: 10, candidate_id: 1 })]);
    renderQueue();
    const table = await screen.findByRole("table");
    expect(table).toBeInTheDocument();
    expect(screen.getAllByRole("row")).toHaveLength(2); // header + 1 round
    expect(screen.getByRole("link", { name: "Cara Candidate" })).toHaveAttribute("href", "/my-candidates/1");
  });

  it("shows an alert with the server's message on a generic fetch failure, not a leaked internal error", async () => {
    mockListMyCandidates.mockRejectedValue(new Error("Not authenticated."));
    renderQueue();
    expect(await screen.findByRole("alert")).toHaveTextContent("Not authenticated.");
  });

  it("renders each of the three states with a distinct data-state attribute, not just distinguishable text", async () => {
    mockListMyCandidates.mockResolvedValue([
      makeRow({ round_id: 1, candidate_id: 1, state: "needs_scheduling" }),
      makeRow({ round_id: 2, candidate_id: 2, state: "scheduled", scheduled_at: "2026-01-15T18:00:00Z" }),
      makeRow({ round_id: 3, candidate_id: 3, state: "overdue", scorecard_due_at: "2026-01-01T00:00:00Z" }),
    ]);
    renderQueue();
    const rows = await screen.findAllByRole("row");
    expect(rows.slice(1).map((r) => r.getAttribute("data-state"))).toEqual(["needs_scheduling", "scheduled", "overdue"]);
  });

  it("renders a closed_unscored round in the overdue bucket with stage-move copy distinct from generic overdue copy", async () => {
    mockListMyCandidates.mockResolvedValue([
      makeRow({
        state: "overdue",
        is_closed_unscored: true,
        next_stage_name: "Onsite",
      }),
    ]);
    renderQueue();
    const row = (await screen.findAllByRole("row"))[1];
    expect(row.getAttribute("data-state")).toBe("overdue");
    expect(await screen.findByText(/Candidate has moved to Onsite — your feedback is still needed\./)).toBeInTheDocument();
  });

  it("uses generic overdue copy (not the stage-move copy) for a plain still-open overdue round", async () => {
    mockListMyCandidates.mockResolvedValue([makeRow({ state: "overdue", is_closed_unscored: false })]);
    renderQueue();
    expect(await screen.findByText("Interview completed — your scorecard is overdue.")).toBeInTheDocument();
    expect(screen.queryByText(/your feedback is still needed/)).not.toBeInTheDocument();
  });

  it("renders scheduled_at and scorecard_due_at in the interviewer's profile timezone, not browser-local, when they differ", async () => {
    // Browser is effectively UTC in this test environment; the profile
    // timezone (set in beforeEach to America/New_York) must win.
    mockListMyCandidates.mockResolvedValue([
      makeRow({
        state: "scheduled",
        scheduled_at: "2026-01-15T18:00:00Z",
        scorecard_due_at: "2026-01-15T20:00:00Z",
      }),
    ]);
    renderQueue();
    // 20:00 UTC is 3:00 PM in America/New_York (EST) — not 8:00 PM, which is
    // what a browser-local render would have produced. 18:00 UTC is 1:00 PM.
    expect(await screen.findByText(/1:00\s?PM/)).toBeInTheDocument();
    expect(await screen.findByText(/3:00\s?PM/)).toBeInTheDocument();
  });
});

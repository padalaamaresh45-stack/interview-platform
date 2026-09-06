import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { InterviewerQueuePage } from "../InterviewerQueuePage";
import { listMyCandidates } from "../../api/interviewer";

vi.mock("../../api/interviewer");

const mockListMyCandidates = vi.mocked(listMyCandidates);

function renderQueue() {
  return render(
    <MemoryRouter>
      <InterviewerQueuePage />
    </MemoryRouter>,
  );
}

afterEach(() => {
  vi.resetAllMocks();
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
    mockListMyCandidates.mockResolvedValue([
      {
        id: 1,
        full_name: "Cara Candidate",
        email: null,
        phone: null,
        position_id: 1,
        owner_id: 5,
        open_round_id: 10,
        status: "not_started",
        hold_reason: null,
        hold_review_by: null,
        created_by: 1,
        created_at: "",
        updated_at: "",
      },
    ]);
    renderQueue();
    // The link's accessible name now includes the status pill text alongside
    // the candidate's name (e.g. "Cara Candidate Awaiting your scorecard") —
    // match on the name being present rather than exact, since that's a
    // legitimate accessibility improvement (a screen reader hears status
    // and name together as one link), not a regression to pin exactly.
    expect(await screen.findByRole("link", { name: /Cara Candidate/ })).toBeInTheDocument();
  });

  it("renders assigned candidates as table rows", async () => {
    mockListMyCandidates.mockResolvedValue([
      {
        id: 1,
        full_name: "Cara Candidate",
        email: null,
        phone: null,
        position_id: 1,
        owner_id: 5,
        open_round_id: 10,
        status: "completed",
        hold_reason: null,
        hold_review_by: null,
        created_by: 1,
        created_at: "",
        updated_at: "",
      },
    ]);
    renderQueue();
    const table = await screen.findByRole("table");
    expect(table).toBeInTheDocument();
    expect(screen.getAllByRole("row")).toHaveLength(2); // header + 1 candidate
    expect(screen.getByRole("link", { name: "Cara Candidate" })).toHaveAttribute("href", "/my-candidates/1");
    expect(screen.getByText("Scored")).toBeInTheDocument();
  });

  it("shows an alert with the server's message on a generic fetch failure, not a leaked internal error", async () => {
    mockListMyCandidates.mockRejectedValue(new Error("Not authenticated."));
    renderQueue();
    expect(await screen.findByRole("alert")).toHaveTextContent("Not authenticated.");
  });
});

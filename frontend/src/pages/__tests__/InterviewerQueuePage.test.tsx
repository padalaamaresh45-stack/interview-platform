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
        interviewer_id: 5,
        status: "not_started",
        created_by: 1,
        created_at: "",
        updated_at: "",
      },
    ]);
    renderQueue();
    expect(await screen.findByRole("link", { name: "Cara Candidate" })).toBeInTheDocument();
  });

  it("shows an alert with the server's message on a generic fetch failure, not a leaked internal error", async () => {
    mockListMyCandidates.mockRejectedValue(new Error("Not authenticated."));
    renderQueue();
    expect(await screen.findByRole("alert")).toHaveTextContent("Not authenticated.");
  });
});

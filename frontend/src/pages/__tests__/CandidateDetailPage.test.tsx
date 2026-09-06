import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { CandidateDetailPage } from "../CandidateDetailPage";
import { getCandidate, reassignRound, updateCandidate } from "../../api/candidates";
import { listPositions } from "../../api/positions";
import { listUsers } from "../../api/users";
import { getCandidateHistory, listStages } from "../../api/pipeline";
import { listAllInterviews } from "../../api/interviews";

vi.mock("../../api/candidates");
vi.mock("../../api/positions");
vi.mock("../../api/users");
vi.mock("../../api/pipeline");
vi.mock("../../api/interviews");

const mockGetCandidate = vi.mocked(getCandidate);
const mockUpdateCandidate = vi.mocked(updateCandidate);
const mockReassignRound = vi.mocked(reassignRound);
const mockListPositions = vi.mocked(listPositions);
const mockListUsers = vi.mocked(listUsers);
const mockGetCandidateHistory = vi.mocked(getCandidateHistory);
const mockListStages = vi.mocked(listStages);
const mockListAllInterviews = vi.mocked(listAllInterviews);

const CANDIDATE_ID = 7;
const DEACTIVATED_INTERVIEWER_ID = 99;

const candidate = {
  id: CANDIDATE_ID,
  full_name: "Cara Candidate",
  email: null,
  phone: null,
  position_id: 1,
  owner_id: DEACTIVATED_INTERVIEWER_ID,
  open_round_id: 1,
  status: "not_started" as const,
  hold_reason: null,
  hold_review_by: null,
  created_by: 1,
  created_at: "",
  updated_at: "",
};

function renderPage() {
  return render(
    <MemoryRouter initialEntries={[`/candidates/${CANDIDATE_ID}`]}>
      <Routes>
        <Route path="/candidates/:candidateId" element={<CandidateDetailPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

afterEach(() => {
  vi.resetAllMocks();
});

describe("CandidateDetailPage", () => {
  it("shows the current owner as read-only text, even if since deactivated", async () => {
    mockListAllInterviews.mockResolvedValue([]);
    mockGetCandidateHistory.mockRejectedValue(new Error("Could not load pipeline history."));
    mockGetCandidate.mockResolvedValue(candidate);
    mockListPositions.mockResolvedValue([
      { id: 1, title: "Backend Engineer", question_count: 1, candidate_count: 0, created_at: "", updated_at: "" },
    ]);
    mockListUsers.mockResolvedValue([
      {
        id: DEACTIVATED_INTERVIEWER_ID,
        email: "deactivated@example.com",
        full_name: "Ivy Deactivated",
        role: "interviewer",
        is_active: false,
        created_at: "",
        updated_at: "",
      },
      {
        id: 2,
        email: "active@example.com",
        full_name: "Andy Active",
        role: "interviewer",
        is_active: true,
        created_at: "",
        updated_at: "",
      },
    ]);

    renderPage();

    expect((await screen.findAllByText("Ivy Deactivated")).length).toBeGreaterThan(0);
    expect(screen.queryByRole("combobox", { name: "Interviewer" })).not.toBeInTheDocument();

    // Saving must never send an owner/interviewer reassignment field —
    // reassignment goes through its own endpoint (ticket #30), not the
    // candidate PATCH form.
    const form = screen.getByRole("button", { name: "Save" }).closest("form");
    expect(form).not.toBeNull();
    // eslint-disable-next-line testing-library/no-node-access
    form!.requestSubmit();
    await vi.waitFor(() => expect(mockUpdateCandidate).toHaveBeenCalled());
    const [, updates] = mockUpdateCandidate.mock.calls[0];
    expect(updates).not.toHaveProperty("interviewer_id");
    expect(updates).not.toHaveProperty("owner_id");
  });

  it("reassigns the open round's interviewer via the reassign endpoint", async () => {
    mockListAllInterviews.mockResolvedValue([]);
    mockGetCandidateHistory.mockRejectedValue(new Error("Could not load pipeline history."));
    mockGetCandidate.mockResolvedValue(candidate);
    mockListPositions.mockResolvedValue([
      { id: 1, title: "Backend Engineer", question_count: 1, candidate_count: 0, created_at: "", updated_at: "" },
    ]);
    mockListUsers.mockResolvedValue([
      {
        id: DEACTIVATED_INTERVIEWER_ID,
        email: "deactivated@example.com",
        full_name: "Ivy Deactivated",
        role: "interviewer",
        is_active: false,
        created_at: "",
        updated_at: "",
      },
      {
        id: 2,
        email: "active@example.com",
        full_name: "Andy Active",
        role: "interviewer",
        is_active: true,
        created_at: "",
        updated_at: "",
      },
    ]);
    mockReassignRound.mockResolvedValue(undefined);

    renderPage();

    const select = await screen.findByLabelText("Reassign interviewer");
    fireEvent.change(select, { target: { value: "2" } });

    const reassignButton = screen.getByRole("button", { name: "Reassign" });
    fireEvent.click(reassignButton);

    await vi.waitFor(() => expect(mockReassignRound).toHaveBeenCalledWith(CANDIDATE_ID, 2));
  });

  function mockHistoryData() {
    mockGetCandidate.mockResolvedValue(candidate);
    mockListPositions.mockResolvedValue([
      { id: 1, title: "Backend Engineer", question_count: 1, candidate_count: 0, created_at: "", updated_at: "" },
    ]);
    mockListUsers.mockResolvedValue([]);
    mockGetCandidateHistory.mockResolvedValue({
      id: CANDIDATE_ID,
      full_name: "Cara Candidate",
      position_id: 1,
      position_title: "Backend Engineer",
      status: "not_started",
      current_stage_id: 1,
      current_stage_name: "Screen",
      days_in_stage: 1,
      health: null,
      next_action: "Schedule interview",
      score: { submitted_count: 0, total_count: 0, average: null },
      stage_history: [
        {
          id: 1,
          from_stage_id: null,
          from_stage_name: null,
          to_stage_id: 1,
          to_stage_name: "Screen",
          actor_id: 1,
          actor_name: "Admin",
          created_at: "2026-01-01T00:00:00Z",
        },
      ],
      scores: [{ id: 1, candidate_id: CANDIDATE_ID, question_id: 1, score: 4, comment: null, created_at: "" }],
    });
    mockListStages.mockResolvedValue([
      { id: 1, position_id: 1, name: "Screen", sequence_order: 1, day_limit: null, is_terminal: false },
    ]);
    mockListAllInterviews.mockResolvedValue([
      {
        id: 1,
        candidate_id: CANDIDATE_ID,
        candidate_name: "Cara Candidate",
        position_title: "Backend Engineer",
        round_id: 1,
        interviewer_id: 2,
        interviewer_name: "Andy Active",
        status: "scheduled",
        scheduled_at: "2026-01-02T15:00:00Z",
        duration_minutes: 30,
        notes: null,
        created_at: "",
      },
    ]);
  }

  it("gives the interview list its own class, not the shared history-list default", async () => {
    mockHistoryData();
    const { container } = renderPage();
    await screen.findByRole("heading", { name: "Scores" });
    expect(container.querySelector("ul.interview-history-list")).not.toBeNull();
  });

  it("gives the stage-history list its own class, not the shared history-list default", async () => {
    mockHistoryData();
    const { container } = renderPage();
    await screen.findByRole("heading", { name: "Scores" });
    expect(container.querySelector("ul.stage-history-list")).not.toBeNull();
  });

  it("gives the score list its own class, not the shared history-list default", async () => {
    mockHistoryData();
    const { container } = renderPage();
    await screen.findByRole("heading", { name: "Scores" });
    expect(container.querySelector("ul.score-history-list")).not.toBeNull();
  });
});

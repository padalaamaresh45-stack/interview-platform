import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { CandidateDetailPage } from "../CandidateDetailPage";
import { getCandidate, updateCandidate } from "../../api/candidates";
import { listPositions } from "../../api/positions";
import { listUsers } from "../../api/users";

vi.mock("../../api/candidates");
vi.mock("../../api/positions");
vi.mock("../../api/users");

const mockGetCandidate = vi.mocked(getCandidate);
const mockUpdateCandidate = vi.mocked(updateCandidate);
const mockListPositions = vi.mocked(listPositions);
const mockListUsers = vi.mocked(listUsers);

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

    expect(await screen.findByText("Ivy Deactivated")).toBeInTheDocument();
    expect(screen.queryByRole("combobox", { name: "Interviewer" })).not.toBeInTheDocument();

    // Saving must never send an owner/interviewer reassignment field — that
    // capability doesn't exist yet (see ticket #26/#30).
    const form = screen.getByRole("button", { name: "Save" }).closest("form");
    expect(form).not.toBeNull();
    // eslint-disable-next-line testing-library/no-node-access
    form!.requestSubmit();
    await vi.waitFor(() => expect(mockUpdateCandidate).toHaveBeenCalled());
    const [, updates] = mockUpdateCandidate.mock.calls[0];
    expect(updates).not.toHaveProperty("interviewer_id");
    expect(updates).not.toHaveProperty("owner_id");
  });
});

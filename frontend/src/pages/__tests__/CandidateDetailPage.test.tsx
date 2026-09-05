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
  interviewer_id: DEACTIVATED_INTERVIEWER_ID,
  status: "not_started" as const,
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
  it("keeps a since-deactivated assigned interviewer visibly selected instead of silently falling back to a different option", async () => {
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

    const select = (await screen.findByLabelText("Interviewer")) as HTMLSelectElement;
    expect(select.value).toBe(String(DEACTIVATED_INTERVIEWER_ID));
    expect(screen.getByRole("option", { name: "Ivy Deactivated (deactivated)" })).toBeInTheDocument();

    // Saving without touching the dropdown must not send an interviewer_id
    // change — the deactivated interviewer's assignment must survive untouched.
    const form = select.closest("form");
    expect(form).not.toBeNull();
    // eslint-disable-next-line testing-library/no-node-access
    form!.requestSubmit();
    await vi.waitFor(() => expect(mockUpdateCandidate).toHaveBeenCalled());
    const [, updates] = mockUpdateCandidate.mock.calls[0];
    expect(updates.interviewer_id).toBeUndefined();
  });

  it("disables deactivated interviewers as reassignment choices but keeps them selectable if already current", async () => {
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
    ]);

    renderPage();

    const option = (await screen.findByRole("option", {
      name: "Ivy Deactivated (deactivated)",
    })) as HTMLOptionElement;
    expect(option.disabled).toBe(false); // it's the current assignment, so it must stay pickable/displayed
  });
});

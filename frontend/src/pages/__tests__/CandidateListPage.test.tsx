import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { CandidateListPage } from "../CandidateListPage";
import { createCandidate, listActiveInterviewers, listCandidates } from "../../api/candidates";
import { listPositions } from "../../api/positions";
import { listUsers } from "../../api/users";

vi.mock("../../api/candidates");
vi.mock("../../api/positions");
vi.mock("../../api/users");

const mockListCandidates = vi.mocked(listCandidates);
const mockCreateCandidate = vi.mocked(createCandidate);
const mockListPositions = vi.mocked(listPositions);
const mockListActiveInterviewers = vi.mocked(listActiveInterviewers);
const mockListUsers = vi.mocked(listUsers);

function renderPage() {
  return render(
    <MemoryRouter>
      <CandidateListPage />
    </MemoryRouter>,
  );
}

afterEach(() => {
  vi.resetAllMocks();
});

const position = { id: 1, title: "Backend Engineer", question_count: 3, candidate_count: 0, created_at: "", updated_at: "" };
const interviewer = { id: 2, full_name: "Ivy Interviewer", email: "ivy@example.com", timezone: null };

describe("CandidateListPage create modal", () => {
  it("opens the create form in a modal from the + New Candidate trigger, and closes it on Escape", async () => {
    mockListCandidates.mockResolvedValue([]);
    mockListPositions.mockResolvedValue([position]);
    mockListActiveInterviewers.mockResolvedValue([interviewer]);
    mockListUsers.mockResolvedValue([]);

    renderPage();
    await screen.findByText(/No candidates yet/);

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "+ New Candidate" }));
    expect(screen.getByRole("dialog")).toBeInTheDocument();

    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("creates a candidate from the modal and closes it, refreshing the list", async () => {
    mockListCandidates
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([
        {
          id: 1,
          full_name: "Cara Candidate",
          email: null,
          phone: null,
          position_id: 1,
          owner_id: 2,
          open_round_id: 10,
          status: "not_started",
          hold_reason: null,
          hold_review_by: null,
          created_by: 1,
          created_at: "",
          updated_at: "",
        },
      ]);
    mockListPositions.mockResolvedValue([position]);
    mockListActiveInterviewers.mockResolvedValue([interviewer]);
    mockListUsers.mockResolvedValue([]);
    mockCreateCandidate.mockResolvedValue({} as never);

    renderPage();
    await screen.findByText(/No candidates yet/);

    await userEvent.click(screen.getByRole("button", { name: "+ New Candidate" }));
    await userEvent.type(screen.getByLabelText("Full name"), "Cara Candidate");
    await userEvent.selectOptions(screen.getByLabelText("Position"), "1");
    await userEvent.selectOptions(screen.getByLabelText("Interviewer"), "2");
    await userEvent.click(screen.getByRole("button", { name: "Create candidate" }));

    expect(mockCreateCandidate).toHaveBeenCalledWith("Cara Candidate", 1, 2, "", "");
    await screen.findByText("Cara Candidate");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});

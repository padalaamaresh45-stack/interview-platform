import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { InterviewerScorecardPage } from "../InterviewerScorecardPage";
import { getMyCandidate, submitScores } from "../../api/interviewer";

vi.mock("../../api/interviewer");

const mockGetMyCandidate = vi.mocked(getMyCandidate);
const mockSubmitScores = vi.mocked(submitScores);

const CANDIDATE_ID = 42;
const ROUND_ID = 100;
const DRAFT_KEY = `interview-draft-${CANDIDATE_ID}`;

const notStartedCandidate = {
  id: CANDIDATE_ID,
  full_name: "Cara Candidate",
  email: null,
  phone: null,
  position_id: 1,
  round_id: ROUND_ID,
  status: "not_started" as const,
  questions: [
    { id: 1, position_id: 1, question_text: "Question one?", sequence_order: 1, created_at: "", updated_at: "" },
    { id: 2, position_id: 1, question_text: "Question two?", sequence_order: 2, created_at: "", updated_at: "" },
  ],
  scores: [],
};

function renderScorecard() {
  return render(
    <MemoryRouter initialEntries={[`/my-candidates/${CANDIDATE_ID}`]}>
      <Routes>
        <Route path="/my-candidates" element={<p>Queue page</p>} />
        <Route path="/my-candidates/:candidateId" element={<InterviewerScorecardPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  window.localStorage.clear();
});

afterEach(() => {
  vi.resetAllMocks();
});

describe("InterviewerScorecardPage", () => {
  it("shows a loading state before the candidate loads", () => {
    mockGetMyCandidate.mockReturnValue(new Promise(() => {}));
    renderScorecard();
    expect(screen.getByText("Loading…")).toBeInTheDocument();
  });

  it("shows an alert when the candidate fails to load", async () => {
    mockGetMyCandidate.mockRejectedValue(new Error("Candidate not found."));
    renderScorecard();
    expect(await screen.findByRole("alert")).toHaveTextContent("Candidate not found.");
  });

  it("autosaves each field change to localStorage keyed by candidate id", async () => {
    mockGetMyCandidate.mockResolvedValue(notStartedCandidate);
    const user = userEvent.setup();
    renderScorecard();

    const scoreInput = await screen.findByLabelText("Score (1-5)", {
      selector: `#score-${notStartedCandidate.questions[0].id}`,
    });
    await user.type(scoreInput, "4");

    await waitFor(() => {
      const stored = JSON.parse(window.localStorage.getItem(DRAFT_KEY) ?? "{}");
      expect(stored[notStartedCandidate.questions[0].id].score).toBe("4");
    });
  });

  it("repopulates an unsubmitted draft from localStorage on reload", async () => {
    window.localStorage.setItem(
      DRAFT_KEY,
      JSON.stringify({
        1: { score: "5", comment: "Great answer" },
        2: { score: "3", comment: "" },
      }),
    );
    mockGetMyCandidate.mockResolvedValue(notStartedCandidate);
    renderScorecard();

    const firstScoreInput = (await screen.findByLabelText("Score (1-5)", {
      selector: "#score-1",
    })) as HTMLInputElement;
    expect(firstScoreInput.value).toBe("5");
    expect(screen.getByDisplayValue("Great answer")).toBeInTheDocument();
  });

  it("clears the draft from localStorage after a successful submit", async () => {
    window.localStorage.setItem(
      DRAFT_KEY,
      JSON.stringify({ 1: { score: "4", comment: "" }, 2: { score: "5", comment: "" } }),
    );
    mockGetMyCandidate.mockResolvedValue(notStartedCandidate);
    mockSubmitScores.mockResolvedValue({ ...notStartedCandidate, status: "completed" } as never);
    const user = userEvent.setup();
    renderScorecard();

    const submitButton = await screen.findByRole("button", { name: "Submit scores" });
    await waitFor(() => expect(submitButton).toBeEnabled());
    await user.click(submitButton);

    await waitFor(() => expect(mockSubmitScores).toHaveBeenCalled());
    expect(window.localStorage.getItem(DRAFT_KEY)).toBeNull();
  });

  it("does not clear the draft when submit fails", async () => {
    window.localStorage.setItem(
      DRAFT_KEY,
      JSON.stringify({ 1: { score: "4", comment: "" }, 2: { score: "5", comment: "" } }),
    );
    mockGetMyCandidate.mockResolvedValue(notStartedCandidate);
    mockSubmitScores.mockRejectedValue(new Error("This candidate has already been submitted."));
    const user = userEvent.setup();
    renderScorecard();

    const submitButton = await screen.findByRole("button", { name: "Submit scores" });
    await waitFor(() => expect(submitButton).toBeEnabled());
    await user.click(submitButton);

    expect(await screen.findByRole("alert")).toHaveTextContent("already been submitted");
    expect(window.localStorage.getItem(DRAFT_KEY)).not.toBeNull();
  });

  it("shows a completed candidate's scores read-only with no form", async () => {
    mockGetMyCandidate.mockResolvedValue({
      ...notStartedCandidate,
      status: "completed",
      scores: [
        { id: 1, candidate_id: CANDIDATE_ID, question_id: 1, score: 4, comment: "Good", created_at: "" },
        { id: 2, candidate_id: CANDIDATE_ID, question_id: 2, score: 5, comment: null, created_at: "" },
      ],
    });
    renderScorecard();

    expect(await screen.findByText(/already been scored/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Submit scores" })).not.toBeInTheDocument();
    expect(screen.getByText(/Question one\?.*score: 4/)).toBeInTheDocument();
  });
});

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { HomePage } from "../HomePage";
import { useAuth } from "../../hooks/useAuth";
import { getBoard, type Board } from "../../api/pipeline";
import { listPositions, type Position } from "../../api/positions";

vi.mock("../../hooks/useAuth");
vi.mock("../../api/pipeline");
vi.mock("../../api/positions");

const mockNavigate = vi.fn();
vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom");
  return { ...actual, useNavigate: () => mockNavigate };
});

const mockUseAuth = vi.mocked(useAuth);
const mockGetBoard = vi.mocked(getBoard);
const mockListPositions = vi.mocked(listPositions);

const positions: Position[] = [
  { id: 6, title: "Product Engineer (Demo)", question_count: 3, candidate_count: 7, created_at: "", updated_at: "" },
  { id: 7, title: "Designer", question_count: 2, candidate_count: 4, created_at: "", updated_at: "" },
];

const board: Board = {
  columns: [
    {
      stage: { id: 1, position_id: 6, name: "Applied", sequence_order: 1, day_limit: 3, is_terminal: false },
      candidates: [],
    },
  ],
};

function renderHome() {
  return render(
    <MemoryRouter>
      <HomePage />
    </MemoryRouter>,
  );
}

afterEach(() => {
  vi.resetAllMocks();
});

describe("HomePage board header", () => {
  it("shows the count with the scoped position title", async () => {
    mockUseAuth.mockReturnValue({
      user: { id: 1, role: "admin", full_name: "Admin", email: "a@a.com", timezone: null },
      initializing: false,
      login: vi.fn(),
      logout: vi.fn(),
      updateTimezone: vi.fn(),
    });
    mockListPositions.mockResolvedValue(positions);
    mockGetBoard.mockResolvedValue(board);

    renderHome();

    expect(await screen.findByText("0 candidates — Product Engineer (Demo) · 0 stalled")).toBeInTheDocument();
  });
});

describe("HomePage pipeline card keyboard activation", () => {
  const boardWithCandidate: Board = {
    columns: [
      {
        stage: { id: 1, position_id: 6, name: "Applied", sequence_order: 1, day_limit: 3, is_terminal: false },
        candidates: [
          {
            id: 42,
            full_name: "Jamie Rivera",
            position_id: 6,
            position_title: "Product Engineer (Demo)",
            owner_id: 1,
            status: "not_started",
            current_stage_id: 1,
            days_in_stage: 1,
            health: "on_track",
            next_action: "Move to Screening",
            gap_state: null,
            score: { submitted_count: 0, total_count: 0, average: null },
          },
        ],
      },
    ],
  };

  it("navigates to the candidate on Enter", async () => {
    mockUseAuth.mockReturnValue({
      user: { id: 1, role: "admin", full_name: "Admin", email: "a@a.com", timezone: null },
      initializing: false,
      login: vi.fn(),
      logout: vi.fn(),
      updateTimezone: vi.fn(),
    });
    mockListPositions.mockResolvedValue(positions);
    mockGetBoard.mockResolvedValue(boardWithCandidate);

    renderHome();
    const user = userEvent.setup();

    const card = await screen.findByText("Jamie Rivera");
    (card.closest('[role="button"]') as HTMLElement).focus();
    await user.keyboard("{Enter}");

    expect(mockNavigate).toHaveBeenCalledWith("/candidates/42");
  });

  it("navigates to the candidate on Space", async () => {
    mockUseAuth.mockReturnValue({
      user: { id: 1, role: "admin", full_name: "Admin", email: "a@a.com", timezone: null },
      initializing: false,
      login: vi.fn(),
      logout: vi.fn(),
      updateTimezone: vi.fn(),
    });
    mockListPositions.mockResolvedValue(positions);
    mockGetBoard.mockResolvedValue(boardWithCandidate);

    renderHome();
    const user = userEvent.setup();

    const card = await screen.findByText("Jamie Rivera");
    (card.closest('[role="button"]') as HTMLElement).focus();
    await user.keyboard(" ");

    expect(mockNavigate).toHaveBeenCalledWith("/candidates/42");
  });
});

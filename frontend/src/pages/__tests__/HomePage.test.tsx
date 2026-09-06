import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { HomePage } from "../HomePage";
import { useAuth } from "../../hooks/useAuth";
import { getBoard, type Board } from "../../api/pipeline";
import { listPositions, type Position } from "../../api/positions";

vi.mock("../../hooks/useAuth");
vi.mock("../../api/pipeline");
vi.mock("../../api/positions");

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

import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { PositionListPage } from "../PositionListPage";
import { listPositions } from "../../api/positions";

vi.mock("../../api/positions");

const mockListPositions = vi.mocked(listPositions);

function renderPage() {
  return render(
    <MemoryRouter>
      <PositionListPage />
    </MemoryRouter>,
  );
}

afterEach(() => {
  vi.resetAllMocks();
});

describe("PositionListPage", () => {
  it("shows a loading state before positions load", () => {
    mockListPositions.mockReturnValue(new Promise(() => {}));
    renderPage();
    expect(screen.getByText("Loading…")).toBeInTheDocument();
  });

  it("shows a clear empty-state message instead of a bare table when there are no positions", async () => {
    mockListPositions.mockResolvedValue([]);
    renderPage();
    expect(await screen.findByText(/No positions yet/)).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("shows a 0-questions badge for a position with no questions", async () => {
    mockListPositions.mockResolvedValue([
      { id: 1, title: "Backend Engineer", question_count: 0, created_at: "", updated_at: "" },
    ]);
    renderPage();
    expect(await screen.findByText(/0 questions/)).toBeInTheDocument();
  });

  it("surfaces a fetch failure as an alert", async () => {
    mockListPositions.mockRejectedValue(new Error("Insufficient permissions."));
    renderPage();
    expect(await screen.findByRole("alert")).toHaveTextContent("Insufficient permissions.");
  });
});

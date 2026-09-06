import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { PositionListPage } from "../PositionListPage";
import { createPosition, listPositions } from "../../api/positions";

vi.mock("../../api/positions");

const mockListPositions = vi.mocked(listPositions);
const mockCreatePosition = vi.mocked(createPosition);

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
      { id: 1, title: "Backend Engineer", question_count: 0, candidate_count: 0, created_at: "", updated_at: "" },
    ]);
    renderPage();
    expect(await screen.findByText(/0 questions/)).toBeInTheDocument();
  });

  it("renders positions as table rows with a link per title", async () => {
    mockListPositions.mockResolvedValue([
      { id: 1, title: "Backend Engineer", question_count: 3, candidate_count: 0, created_at: "", updated_at: "" },
      { id: 2, title: "Designer", question_count: 1, candidate_count: 0, created_at: "", updated_at: "" },
    ]);
    renderPage();
    const table = await screen.findByRole("table");
    expect(table).toBeInTheDocument();
    expect(screen.getAllByRole("row")).toHaveLength(3); // header + 2 positions
    expect(screen.getByRole("link", { name: "Backend Engineer" })).toHaveAttribute("href", "/positions/1");
  });

  it("surfaces a fetch failure as an alert", async () => {
    mockListPositions.mockRejectedValue(new Error("Insufficient permissions."));
    renderPage();
    expect(await screen.findByRole("alert")).toHaveTextContent("Insufficient permissions.");
  });

  it("opens the create form in a modal from the + New Position trigger, and closes it on Escape", async () => {
    mockListPositions.mockResolvedValue([]);
    renderPage();
    await screen.findByText(/No positions yet/);

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "+ New Position" }));
    expect(screen.getByRole("dialog")).toBeInTheDocument();

    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("creates a position from the modal and closes it, refreshing the list", async () => {
    mockListPositions.mockResolvedValueOnce([]).mockResolvedValueOnce([
      { id: 1, title: "Backend Engineer", question_count: 0, candidate_count: 0, created_at: "", updated_at: "" },
    ]);
    mockCreatePosition.mockResolvedValue({
      id: 1,
      title: "Backend Engineer",
      question_count: 0,
      candidate_count: 0,
      created_at: "",
      updated_at: "",
    });
    renderPage();
    await screen.findByText(/No positions yet/);

    await userEvent.click(screen.getByRole("button", { name: "+ New Position" }));
    await userEvent.type(screen.getByLabelText("New position title"), "Backend Engineer");
    await userEvent.click(screen.getByRole("button", { name: "Create position" }));

    expect(mockCreatePosition).toHaveBeenCalledWith("Backend Engineer");
    await screen.findByText("Backend Engineer");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});

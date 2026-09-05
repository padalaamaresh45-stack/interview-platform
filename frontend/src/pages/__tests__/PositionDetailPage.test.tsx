import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { PositionDetailPage } from "../PositionDetailPage";
import { getPosition, listQuestions } from "../../api/positions";

vi.mock("../../api/positions");

const mockGetPosition = vi.mocked(getPosition);
const mockListQuestions = vi.mocked(listQuestions);

const POSITION_ID = 5;

function renderPage() {
  return render(
    <MemoryRouter initialEntries={[`/positions/${POSITION_ID}`]}>
      <Routes>
        <Route path="/positions/:positionId" element={<PositionDetailPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

afterEach(() => {
  vi.resetAllMocks();
});

describe("PositionDetailPage", () => {
  it("suggests sequence order 1 for the first question on an empty position", async () => {
    mockGetPosition.mockResolvedValue({
      id: POSITION_ID,
      title: "Backend Engineer",
      question_count: 0,
      candidate_count: 0,
      created_at: "",
      updated_at: "",
    });
    mockListQuestions.mockResolvedValue([]);
    renderPage();

    const orderInput = (await screen.findByLabelText("Sequence order")) as HTMLInputElement;
    expect(orderInput.value).toBe("1");
  });

  it("suggests the next sequence order after the highest existing one, not just count + 1", async () => {
    mockGetPosition.mockResolvedValue({
      id: POSITION_ID,
      title: "Backend Engineer",
      question_count: 2,
      candidate_count: 0,
      created_at: "",
      updated_at: "",
    });
    mockListQuestions.mockResolvedValue([
      { id: 1, position_id: POSITION_ID, question_text: "Q1", sequence_order: 1, created_at: "", updated_at: "" },
      { id: 2, position_id: POSITION_ID, question_text: "Q5", sequence_order: 5, created_at: "", updated_at: "" },
    ]);
    renderPage();

    const orderInput = (await screen.findByLabelText("Sequence order")) as HTMLInputElement;
    expect(orderInput.value).toBe("6");
  });
});

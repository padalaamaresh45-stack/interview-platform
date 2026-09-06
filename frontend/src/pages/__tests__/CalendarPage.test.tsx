import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { CalendarPage } from "../CalendarPage";
import { useAuth } from "../../hooks/useAuth";
import { cancelInterview, listAllInterviews, type Interview } from "../../api/interviews";
import { listCandidates } from "../../api/candidates";

vi.mock("../../hooks/useAuth");
vi.mock("../../api/interviews");
vi.mock("../../api/candidates");

const mockUseAuth = vi.mocked(useAuth);
const mockListAllInterviews = vi.mocked(listAllInterviews);
const mockCancelInterview = vi.mocked(cancelInterview);
const mockListCandidates = vi.mocked(listCandidates);

function todayKey(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function renderCalendar() {
  return render(
    <MemoryRouter>
      <CalendarPage />
    </MemoryRouter>,
  );
}

afterEach(() => {
  vi.resetAllMocks();
});

describe("CalendarPage day-detail list", () => {
  it("renders today's interviews as table rows, with a per-row Cancel action for admins", async () => {
    mockUseAuth.mockReturnValue({
      user: { id: 1, role: "admin", full_name: "Admin", email: "a@a.com" },
      login: vi.fn(),
      logout: vi.fn(),
    } as unknown as ReturnType<typeof useAuth>);
    mockListCandidates.mockResolvedValue([]);

    const interview: Interview = {
      id: 1,
      candidate_id: 5,
      candidate_name: "Cara Candidate",
      position_title: "Backend Engineer",
      round_id: 1,
      interviewer_id: 2,
      interviewer_name: "Andy Active",
      status: "scheduled",
      scheduled_at: `${todayKey()}T15:00:00`,
      duration_minutes: 30,
      notes: "Bring laptop",
      created_at: "",
    };
    mockListAllInterviews.mockResolvedValue([interview]);
    mockCancelInterview.mockResolvedValue(undefined as never);

    renderCalendar();

    const table = await screen.findByRole("table");
    expect(table).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Cara Candidate/ })).toBeInTheDocument();

    const cancelButton = screen.getByRole("button", { name: "Cancel" });
    await userEvent.click(cancelButton);
    expect(mockCancelInterview).toHaveBeenCalledWith(interview.id);
  });
});

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { CalendarPage } from "../CalendarPage";
import { useAuth } from "../../hooks/useAuth";
import { cancelInterview, listAllInterviews, scheduleInterview, type Interview } from "../../api/interviews";
import { listActiveInterviewers, listCandidates } from "../../api/candidates";

vi.mock("../../hooks/useAuth");
vi.mock("../../api/interviews");
vi.mock("../../api/candidates");

const mockUseAuth = vi.mocked(useAuth);
const mockListAllInterviews = vi.mocked(listAllInterviews);
const mockCancelInterview = vi.mocked(cancelInterview);
const mockListCandidates = vi.mocked(listCandidates);
const mockListActiveInterviewers = vi.mocked(listActiveInterviewers);
const mockScheduleInterview = vi.mocked(scheduleInterview);

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
    mockListActiveInterviewers.mockResolvedValue([]);

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

describe("CalendarPage scheduling picker — assignee-local-time preview", () => {
  it("shows the assignee's local time next to the picker, updating live as a time is chosen", async () => {
    mockUseAuth.mockReturnValue({
      user: { id: 1, role: "admin", full_name: "Admin", email: "a@a.com" },
      login: vi.fn(),
      logout: vi.fn(),
    } as unknown as ReturnType<typeof useAuth>);
    mockListAllInterviews.mockResolvedValue([]);
    mockListCandidates.mockResolvedValue([
      {
        id: 5,
        full_name: "Priya Interviewer's Candidate",
        email: null,
        phone: null,
        position_id: 1,
        owner_id: 42,
        open_round_id: 10,
        status: "not_started",
        hold_reason: null,
        hold_review_by: null,
        created_by: 1,
        created_at: "",
        updated_at: "",
      },
    ]);
    mockListActiveInterviewers.mockResolvedValue([
      { id: 42, full_name: "Priya", email: "priya@example.com", timezone: "Asia/Kolkata" },
    ]);

    renderCalendar();

    await userEvent.click(await screen.findByRole("button", { name: "+ New Interview" }));
    await userEvent.selectOptions(await screen.findByLabelText("Candidate"), "5");
    await userEvent.type(screen.getByLabelText("When"), "2026-01-15T09:00");

    expect(await screen.findByText(/for Priya/)).toBeInTheDocument();
  });

  it("does not show a preview before a candidate and time are both chosen", async () => {
    mockUseAuth.mockReturnValue({
      user: { id: 1, role: "admin", full_name: "Admin", email: "a@a.com" },
      login: vi.fn(),
      logout: vi.fn(),
    } as unknown as ReturnType<typeof useAuth>);
    mockListAllInterviews.mockResolvedValue([]);
    mockListCandidates.mockResolvedValue([]);
    mockListActiveInterviewers.mockResolvedValue([]);

    renderCalendar();
    await screen.findByRole("heading", { name: "Calendar" });

    expect(screen.queryByText(/ for /)).not.toBeInTheDocument();
  });
});

describe("CalendarPage schedule modal", () => {
  it("opens the scheduling form in a modal from the + New Interview trigger, and closes it on Escape", async () => {
    mockUseAuth.mockReturnValue({
      user: { id: 1, role: "admin", full_name: "Admin", email: "a@a.com" },
      login: vi.fn(),
      logout: vi.fn(),
    } as unknown as ReturnType<typeof useAuth>);
    mockListAllInterviews.mockResolvedValue([]);
    mockListCandidates.mockResolvedValue([]);
    mockListActiveInterviewers.mockResolvedValue([]);

    renderCalendar();
    await screen.findByRole("heading", { name: "Calendar" });

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "+ New Interview" }));
    expect(screen.getByRole("dialog")).toBeInTheDocument();

    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("schedules an interview from the modal and closes it, refreshing the list", async () => {
    mockUseAuth.mockReturnValue({
      user: { id: 1, role: "admin", full_name: "Admin", email: "a@a.com" },
      login: vi.fn(),
      logout: vi.fn(),
    } as unknown as ReturnType<typeof useAuth>);
    mockListAllInterviews.mockResolvedValueOnce([]).mockResolvedValueOnce([
      {
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
        notes: "",
        created_at: "",
      },
    ]);
    mockListCandidates.mockResolvedValue([
      {
        id: 5,
        full_name: "Cara Candidate",
        email: null,
        phone: null,
        position_id: 1,
        owner_id: 42,
        open_round_id: 10,
        status: "not_started",
        hold_reason: null,
        hold_review_by: null,
        created_by: 1,
        created_at: "",
        updated_at: "",
      },
    ]);
    mockListActiveInterviewers.mockResolvedValue([
      { id: 42, full_name: "Andy Active", email: "andy@example.com", timezone: null },
    ]);
    mockScheduleInterview.mockResolvedValue({} as never);

    renderCalendar();
    await screen.findByRole("heading", { name: "Calendar" });

    await userEvent.click(screen.getByRole("button", { name: "+ New Interview" }));
    await userEvent.selectOptions(screen.getByLabelText("Candidate"), "5");
    await userEvent.type(screen.getByLabelText("When"), `${todayKey()}T15:00`);
    await userEvent.click(screen.getByRole("button", { name: "Schedule interview" }));

    expect(mockScheduleInterview).toHaveBeenCalledWith(10, expect.any(String), 60, "");
    await screen.findByText(/Cara Candidate/);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});

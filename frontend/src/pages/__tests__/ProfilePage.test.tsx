import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ProfilePage } from "../ProfilePage";
import { useAuth } from "../../hooks/useAuth";

vi.mock("../../hooks/useAuth");

const mockUseAuth = vi.mocked(useAuth);

function renderProfile() {
  return render(
    <MemoryRouter>
      <ProfilePage />
    </MemoryRouter>,
  );
}

afterEach(() => {
  vi.resetAllMocks();
});

describe("ProfilePage", () => {
  it("lets a user view and change their own timezone", async () => {
    const mockUpdateTimezone = vi.fn().mockResolvedValue(undefined);
    mockUseAuth.mockReturnValue({
      user: { id: 1, email: "iv@example.com", full_name: "Ivy Interviewer", role: "interviewer", timezone: "America/New_York" },
      initializing: false,
      login: vi.fn(),
      logout: vi.fn(),
      updateTimezone: mockUpdateTimezone,
    });

    renderProfile();

    const select = screen.getByLabelText("Timezone") as HTMLSelectElement;
    expect(select.value).toBe("America/New_York");

    await userEvent.selectOptions(select, "Europe/London");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    expect(mockUpdateTimezone).toHaveBeenCalledWith("Europe/London");
    expect(await screen.findByText("Timezone saved.")).toBeInTheDocument();
  });

  it("surfaces an error message when saving fails", async () => {
    const mockUpdateTimezone = vi.fn().mockRejectedValue(new Error("Something went wrong."));
    mockUseAuth.mockReturnValue({
      user: { id: 1, email: "iv@example.com", full_name: "Ivy Interviewer", role: "interviewer", timezone: "America/New_York" },
      initializing: false,
      login: vi.fn(),
      logout: vi.fn(),
      updateTimezone: mockUpdateTimezone,
    });

    renderProfile();
    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Something went wrong.");
  });
});

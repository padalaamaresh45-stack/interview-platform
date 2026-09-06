import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { UserListPage } from "../UserListPage";
import { createUser, listUsers } from "../../api/users";

vi.mock("../../api/users");

const mockListUsers = vi.mocked(listUsers);
const mockCreateUser = vi.mocked(createUser);

afterEach(() => {
  vi.resetAllMocks();
});

describe("UserListPage create modal", () => {
  it("opens the create form in a modal from the + New User trigger, and closes it on Escape", async () => {
    mockListUsers.mockResolvedValue([]);
    render(<UserListPage />);
    await screen.findByText(/No users yet/);

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "+ New User" }));
    expect(screen.getByRole("dialog")).toBeInTheDocument();

    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("creates a user from the modal and closes it, refreshing the list", async () => {
    mockListUsers
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([
        {
          id: 1,
          email: "new@example.com",
          full_name: "New Person",
          role: "interviewer",
          is_active: true,
          created_at: "",
          updated_at: "",
        },
      ]);
    mockCreateUser.mockResolvedValue({} as never);

    render(<UserListPage />);
    await screen.findByText(/No users yet/);

    await userEvent.click(screen.getByRole("button", { name: "+ New User" }));
    await userEvent.type(screen.getByLabelText("Email"), "new@example.com");
    await userEvent.type(screen.getByLabelText("Initial password"), "hunter2pass");
    await userEvent.type(screen.getByLabelText("Full name"), "New Person");
    await userEvent.click(screen.getByRole("button", { name: "Create user" }));

    expect(mockCreateUser).toHaveBeenCalledWith("new@example.com", "hunter2pass", "New Person", "interviewer");
    await screen.findByText("New Person");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});

describe("UserListPage status pill tone (#24)", () => {
  it("renders neutral tone for both active and deactivated users", async () => {
    mockListUsers.mockResolvedValue([
      {
        id: 1,
        email: "active@example.com",
        full_name: "Active Amy",
        role: "interviewer",
        is_active: true,
        created_at: "",
        updated_at: "",
      },
      {
        id: 2,
        email: "deactivated@example.com",
        full_name: "Deactivated Dan",
        role: "interviewer",
        is_active: false,
        created_at: "",
        updated_at: "",
      },
    ]);

    render(<UserListPage />);

    expect(await screen.findByText("Active")).toHaveClass("status-pill--neutral");
    expect(screen.getByText("Deactivated")).toHaveClass("status-pill--neutral");
  });
});

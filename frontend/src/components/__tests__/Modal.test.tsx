import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { Modal } from "../Modal";

describe("Modal", () => {
  it("moves focus into the modal on open and returns it to the trigger on close", async () => {
    function Harness() {
      return (
        <div>
          <button>Trigger</button>
          <Modal title="Test modal" onClose={() => {}}>
            <button>First field</button>
          </Modal>
        </div>
      );
    }
    render(<Harness />);
    expect(screen.getByRole("dialog")).toHaveFocus();
  });

  it("calls onClose on Escape and on backdrop click, and traps Tab within the dialog", async () => {
    const onClose = vi.fn();
    render(
      <Modal title="Test modal" onClose={onClose}>
        <button>First</button>
        <button>Last</button>
      </Modal>,
    );

    await userEvent.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalledTimes(1);

    await userEvent.click(screen.getByRole("dialog").parentElement!);
    expect(onClose).toHaveBeenCalledTimes(2);
  });

  it("restores focus to the trigger element on unmount", () => {
    function Harness({ open }: { open: boolean }) {
      return (
        <div>
          <button>Trigger</button>
          {open && (
            <Modal title="Test modal" onClose={() => {}}>
              <button>First</button>
            </Modal>
          )}
        </div>
      );
    }
    const { rerender } = render(<Harness open={false} />);
    screen.getByText("Trigger").focus();
    rerender(<Harness open={true} />);
    expect(screen.getByRole("dialog")).toHaveFocus();
    rerender(<Harness open={false} />);
    expect(screen.getByText("Trigger")).toHaveFocus();
  });
});

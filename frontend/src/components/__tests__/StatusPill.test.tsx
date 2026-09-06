import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { StatusPill } from "../StatusPill";

describe("StatusPill", () => {
  it("renders the neutral tone class", () => {
    render(<StatusPill tone="neutral">Deactivated</StatusPill>);
    expect(screen.getByText("Deactivated")).toHaveClass("status-pill", "status-pill--neutral");
  });

  it("renders the warning tone class", () => {
    render(<StatusPill tone="warning">Overdue</StatusPill>);
    expect(screen.getByText("Overdue")).toHaveClass("status-pill", "status-pill--warning");
  });

  it("renders the success tone class", () => {
    render(<StatusPill tone="success">Scheduled</StatusPill>);
    expect(screen.getByText("Scheduled")).toHaveClass("status-pill", "status-pill--success");
  });
});

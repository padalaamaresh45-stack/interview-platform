import { describe, expect, it } from "vitest";
import { formatTimeInZone, zoneAbbreviation } from "../timezone";

describe("formatTimeInZone", () => {
  it("renders a UTC instant as the correct local time for a given IANA zone", () => {
    // 14:00 UTC is 9:00 AM in America/New_York (EST, UTC-5) in January.
    expect(formatTimeInZone("2026-01-15T14:00:00Z", "America/New_York")).toBe("9:00 AM");
  });

  it("renders the same instant differently for two different zones", () => {
    // 14:00 UTC is 7:30 PM in Asia/Kolkata (IST, UTC+5:30).
    expect(formatTimeInZone("2026-01-15T14:00:00Z", "Asia/Kolkata")).toBe("7:30 PM");
  });
});

describe("zoneAbbreviation", () => {
  it("returns a short label for the zone at the given instant", () => {
    expect(zoneAbbreviation("2026-01-15T14:00:00Z", "America/New_York")).toBe("EST");
  });
});

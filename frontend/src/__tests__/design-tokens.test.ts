import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

// jsdom doesn't apply an actual stylesheet cascade, so these assert directly
// against the source of truth (index.css) rather than a rendered DOM's
// getComputedStyle — the same values a browser would compute from these
// rules, checked at the point they're declared.
const css = readFileSync(resolve(__dirname, "../index.css"), "utf-8");

function escapeRegExp(literal: string): string {
  return literal.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

// Matches a rule whose selector list starts with this exact line — not
// preceded by a trailing comma from a prior selector line, so a lookup for
// the standalone ".login-card form button { ... }" rule doesn't match its
// last line inside the combined ".btn-primary,\n...,\n.login-card form
// button { ... }" rule above it.
function rule(selector: string): string {
  const pattern = new RegExp(`(?<!,)\\n${escapeRegExp(selector)}\\s*\\{([^}]*)\\}`);
  const match = css.match(pattern);
  if (!match) throw new Error(`No standalone rule found for selector: ${selector}`);
  const body = match[0];
  return body.slice(body.indexOf("{") + 1, body.lastIndexOf("}"));
}

function declares(selector: string, property: string, value: string) {
  expect(rule(selector)).toMatch(new RegExp(`${property}:\\s*${value}\\s*;`));
}

describe("login page type scale (#19)", () => {
  it("uses documented general-heading and secondary/body sizes, not bespoke ones", () => {
    declares(".login-card h1", "font-size", "17px");
    declares(".login-subtitle", "font-size", "12.5px");
    declares(".login-footer", "font-size", "12.5px");
    declares(".login-card form label", "font-size", "12.5px");
    declares(".login-forgot", "font-size", "12.5px");
    declares(".login-card form input", "font-size", "13.5px");
    declares(".app-mark", "font-size", "11px");
  });

  it("keeps the heading's weight and tracking from the earlier login rework", () => {
    declares(".login-card h1", "font-weight", "500");
    declares(".login-card h1", "letter-spacing", "-0.01em");
  });
});

describe("small-control border radius (#20)", () => {
  it("has no bare 8px or 12px small-control radius left anywhere", () => {
    expect(css).not.toMatch(/border-radius:\s*8px/);
    expect(css).not.toMatch(/border-radius:\s*12px/);
  });

  it("collapses inputs, record cards, and table end-caps onto the shared 10px value", () => {
    declares(".page input,\n.page select,\n.page textarea", "border-radius", "10px");
    declares(".record-card", "border-radius", "10px");
    declares(".page td:first-child", "border-top-left-radius", "10px");
    declares(".page td:last-child", "border-top-right-radius", "10px");
  });
});

describe("primary button consolidation (#21)", () => {
  it("defines shape/color/text once, shared by all three call sites", () => {
    const shared = rule('.btn-primary,\n.page button[type="submit"],\n.login-card form button');
    expect(shared).toMatch(/border-radius:\s*999px\s*;/);
    expect(shared).toMatch(/font-size:\s*13px\s*;/);
    expect(shared).toMatch(/font-weight:\s*600\s*;/);
    expect(shared).toMatch(/background:\s*var\(--cta-bg\)\s*;/);
  });

  it("no longer repeats shape/color/text on the login button or .page submit button", () => {
    const loginButton = rule(".login-card form button");
    expect(loginButton).not.toMatch(/border-radius/);
    expect(loginButton).not.toMatch(/font-size/);

    const pageSubmit = rule('.page button[type="submit"]');
    expect(pageSubmit).not.toMatch(/border-radius/);
    expect(pageSubmit).not.toMatch(/font-size/);
  });
});

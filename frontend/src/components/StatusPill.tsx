import type { ReactNode } from "react";

export type StatusPillTone = "neutral" | "warning" | "success";

interface StatusPillProps {
  tone: StatusPillTone;
  children: ReactNode;
}

// Every caller must pass an explicit tone — no boolean/className guess at
// what a given status means. A binary like "deactivated" or "not started"
// is a state, not a problem, so it renders neutral rather than inheriting
// whatever tint another caller's alarming state happens to use.
export function StatusPill({ tone, children }: StatusPillProps) {
  return <span className={`status-pill status-pill--${tone}`}>{children}</span>;
}

# Panel interviews, scorecards, auto-advance, and a calendar view

Status: **proposal, not yet decided.** This is a scoping document, not an ADR — it
exists to get schema and rules right on paper before any code changes. If
approved, `CONTEXT.md` needs updating as part of the same change, since two of
its recorded decisions get reversed (see below).

## This reverses two decisions already recorded in CONTEXT.md

> "The tool never runs or schedules the interview itself."

> "Candidate: One person being interviewed for exactly one Position by
> **exactly one assigned Interviewer**."

Those weren't gaps — they were deliberate scope cuts (the original ticket-01
spec — `docs/spec-v1-mvp.md` — lists "Panel interviews (multiple interviewers
per round)" and "Auto-computed pipeline status" explicitly as out-of-scope for
v1, "to ship the smallest useful loop first"). This proposal is the
follow-on: building what v1 deliberately deferred. Worth having eyes-open
that it's a scope reversal, not a bug fix, before signing off.

## What's being asked for (source: your feedback items 12–15)

1. A candidate can be interviewed by multiple people (a **Panel**) across
   different stages, not one fixed Interviewer for the candidate's whole life.
2. Each panel member submits their own scorecard — summary, key highlights,
   a recommendation — independently.
3. Once all panel members for a stage have submitted, the candidate should
   auto-advance (or an admin can override).
4. An interviewer needs their own view: candidates/interviews assigned to
   them, and a form to submit a scorecard when the interview happens.
5. A user (e.g. "Jack") should have a profile showing every interview he's
   conducted and has yet to conduct.
6. A calendar view of scheduled interviews.

## Proposed schema

Reuses the ubiquitous language from the original pipeline brief (Loop,
Panel, Scorecard, Debrief) rather than inventing new terms.

```
loops
  id
  candidate_id      -> candidates.id
  stage_id          -> stages.id        (which stage this loop belongs to)
  scheduled_start    timestamptz null   (null until scheduled)
  scheduled_end       timestamptz null
  status              enum: scheduled | completed | canceled
  created_by         -> users.id
  created_at

panel_members
  id
  loop_id           -> loops.id
  interviewer_id    -> users.id
  UNIQUE(loop_id, interviewer_id)

scorecards
  id
  loop_id           -> loops.id
  interviewer_id    -> users.id
  recommendation     enum: advance | reject | no_decision
  summary            text            (the "highlights" writeup)
  submitted_at       timestamptz null  (null = not yet submitted)
  UNIQUE(loop_id, interviewer_id)     -- one scorecard per panelist per loop
```

Notes:
- `loops.stage_id` ties a loop to one Stage — a candidate can have multiple
  loops over their lifetime (one per stage that needs a panel), which is
  what "interviewed by multiple stakeholders under different stages" means
  concretely.
- `Candidate.interviewer_id` (today's single-owner FK) becomes the
  **primary/owning interviewer** — used for `/my-candidates` triage and
  admin defaults — while `panel_members` is the actual source of truth for
  "who interviews this candidate at this stage." Existing single-interviewer
  data migrates as one `panel_members` row per candidate's current loop.
- The existing `interview_scores`/`Question` 1-5 rubric is a *different*
  concept (a fixed scored question set per Position) and stays as-is —
  `scorecards.summary` is the free-text panel writeup, not a replacement.

## The auto-advance rule — needs your confirmation, not my guess

"Move automatically based on scores" needs a concrete rule. Proposing:

- **All panel members submitted, all `recommendation = advance`** → auto-move
  candidate to the position's next Stage (by `sequence_order`).
- **Any panel member submits `recommendation = reject`** → do *not*
  auto-move. Surface it on the board (a new next-action: "Debrief needed")
  and require an admin to move it manually — this is the "admin exceptions"
  you mentioned.
- **Split decision with no `reject`** (e.g. two `advance`, one
  `no_decision`) → also holds for manual admin decision rather than
  guessing a majority rule.

This needs your sign-off specifically because "auto-advance" silently moving
a candidate the wrong way is exactly the kind of bug that erodes trust in
the board — better to over-ask for a manual Debrief than under-ask.

## New/changed UI

- **Interviewer queue** (`/my-candidates`, existing page): today shows
  candidates for one-time scoring. Add a second section: "Your upcoming
  loops" (scheduled, not yet completed) and "Needs your scorecard"
  (completed loops, no scorecard submitted yet from this interviewer).
- **Scorecard submission form** (new): click a loop from the queue → summary
  textarea + recommendation select → submit. Submitting one panelist's
  scorecard never blocks or auto-advances anything by itself; the
  auto-advance check runs after *every* panel member's card is in.
- **Interviewer profile** (new, e.g. `/users/:id`): every loop where that
  user is a panel member, split into upcoming / awaiting their scorecard /
  completed. This is "under Jack's profile, all the interviews he has
  conducted and has yet to conduct."
- **Calendar view** (new, e.g. `/calendar`): week/month grid of `loops` by
  `scheduled_start`, filterable by interviewer. Built from `loops` directly
  — no external calendar integration, per your answer.

## What this does NOT include (flag if you actually want it)

- Email/notification reminders for scheduled loops.
- External calendar sync (Google/Outlook) — you said build from scratch.
- Editing a submitted scorecard (mirrors the existing immutable-Score rule
  in CONTEXT.md — a scorecard, once submitted, stays submitted).
- Changing the existing 1-5 rubric scoring flow — that's untouched.

## Suggested build order

1. Migration: `loops`, `panel_members`, `scorecards` tables + backfill
   existing candidates into one loop/panel row each.
2. Backend: create-loop, add-panelist, submit-scorecard, auto-advance-check
   endpoints.
3. Interviewer queue + scorecard form (highest-value surface first).
4. Interviewer profile page.
5. Calendar view (depends on loops already existing and being scheduled).

Each step should ship and get reviewed independently rather than as one
large change — this is a genuinely new subsystem, not a styling pass.

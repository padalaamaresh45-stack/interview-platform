# Epic: Interview rounds with per-round ownership

## Decisions that changed and why

- **`closed_unscored`** went from a single (rejection-path) writer to two independent, equally-primary writers. Why: advancing a candidate to the next round while the prior round was still unscored needed the same "close it out without a scorecard" outcome as rejection — inventing a second status for that case would have reintroduced the exact drift pattern (`compute_health`/`compute_next_action`, §4.1) this epic exists to avoid.
- **Invariant 3** went from "a round cannot close without a submitted scorecard" to "a round can only transition to `scored` if a scorecard was submitted for it." Why: the original wording was already false the moment `closed_unscored` existed — rejection closes a round with no scorecard by design. Correction to a pre-existing doc defect, not a consequence of any later rule.
- **Submission authorization** went from candidate-scoped ("an open `Round` exists for this candidate with this user as assignee") to `round_id`-scoped ("does this specific `round_id` belong to this user, with no scorecard yet"). Why: the candidate-scoped version directly contradicted one-open-round-per-candidate — a round-1 interviewer's late submission, after the admin already opened round 2, needed round 1 to be both closed (satisfying the uniqueness rule) and still submittable, which an "is it open" filter can't express. The caller must say which round it means, since a re-interviewed candidate can have more than one round per interviewer.
- **#16 AC4** (`TERMINAL_STAGE_NAMES` grep must return zero matches): became "zero matches outside the backfill migration file." Why: the two remaining hits are historical record of a one-time backfill, not runtime code.
- **#29 AC1** ("`User.timezone` set exactly once, at account creation"): became "set from browser inference on any login where it's still unset." Why: behaviorally equivalent for the property the AC actually protects — a set value, however it was set, is never overwritten by inference again — and simpler to implement than gating specifically on first-ever login.

No code has been written for this epic. This document captures the design as decided in conversation; it precedes `/spec` and ticket creation.

## Why

Today, `Candidate.interviewer_id` (`backend/app/models/candidate.py:23`) is a single, static foreign key set once at candidate creation. It doesn't change as a candidate moves through stages, and `InterviewScore` (`backend/app/models/interview_score.py`) has no interviewer attribution at all — a unique constraint on `(candidate_id, question_id)` assumes exactly one score per question, full stop. Neither model can represent "a different interviewer owns this candidate at each stage of the loop," which is the actual shape of a multi-round interview process.

## Timezone investigation (settled before any of the below)

Traced the full round-trip for `Interview.scheduled_at`:

- Column is `DateTime(timezone=True)` (Postgres `timestamptz`); confirmed via direct query that stored values carry `tzinfo=UTC` correctly.
- Write path: the calendar form's `<input type="datetime-local">` yields an offset-less string; `new Date(scheduledAt)` parses this as **local** time per spec (only bare dates get UTC treatment), and `.toISOString()` correctly converts to UTC before the API call.
- Read path: `GET /api/admin/interviews` returns explicit `Z`-suffixed UTC strings (verified live); the frontend's `new Date(iso)` + `toLocaleTimeString()` correctly renders local time.
- The specific "11:19 PM – 12:19 AM" observation is real but not a bug: `03:19 UTC` on a machine in EDT (UTC-4) is exactly `23:19 EDT` the previous day. No seed script creates `Interview` rows — this was a manually-entered row at a genuinely odd hour.

**Conclusion: the timezone pipeline is correct end-to-end.** This epic inherits no defect here. If a concrete mismatch shows up later, re-verify against this trace rather than assuming the plumbing is untrustworthy.

## The round loop

```
Round open (assignee, assignment_due_at, brief)
  -> interviewer submits scorecard, round closes
  -> compare score to that STAGE's thresholds
  -> two lanes, neither auto-executing:
       clears advance bar        -> awaiting assignment
       below bar OR ambiguous    -> awaiting decision
  -> awaiting assignment -> admin assigns next round with a NEW assignee -> loop
  -> awaiting decision   -> admin records Hire / No hire / Hold
```

**Why no auto-reject**: a score ending a candidacy with no human in the loop encodes exactly the bias blind feedback exists to remove, and it's unappealable. Rejecting still takes one click — it just takes a click. The default is routing, not deciding.

**Thresholds are config, per stage, not hardcoded.** `advance_threshold` and `reject_threshold` live on the `Stage` row (alongside the existing `day_limit`, `is_terminal`), both nullable. A stage with no thresholds always routes to `awaiting decision`. Early screen stages justify a strict reject bar; an onsite loop should probably have none and always go to a human.

**"Admin assigns next round" is a close-then-open transaction, not just an insert.** If the prior round is still `open` when the next one is assigned — the admin didn't wait for a scorecard — that prior round closes as `closed_unscored` first, in the same transaction, before the new round opens. This is what keeps the one-open-round-per-candidate guarantee (see the `rounds.status` schema entry) from ever being violated; the partial unique index is the safety net, this transaction is the actual mechanism. It only fires when a prior round is genuinely still open — the normal happy path (prior round already `scored`) has nothing to close. **This transaction is shared code with reassignment** (below) — same close-then-open shape, different resulting status (`closed_unscored` vs. `reassigned`) — implemented once, not twice. Two independent copies of the same transaction is exactly how `compute_health` and `compute_next_action` drifted apart in §4.1 of the UI audit; this is the same risk with a different pair of call sites.

## States

Four states, kept distinct because each has a different next action and different health behavior:

| State | Accrues days / can stall | Health applies |
|---|---|---|
| `awaiting assignment` | yes | yes |
| `assigned but unscheduled` | yes | yes — next action: "schedule interview" |
| `awaiting decision` | yes, but next-action copy reads as an admin task ("Record decision — waiting Nd"), not an interviewer stall | yes, distinct framing from interviewer-side stalls |
| `on hold` | admin-initiated, has a reason and optional `review_by` | health **suspended entirely** — never stalled, never shows a warning color |
| terminal (Hired/Rejected) | n/a | `health` returns `None` (already shipped in #16) |

`assigned but unscheduled` is a state in its own right, not a transient UI gap — a `Round` can exist with an assignee and no `Interview` yet. It must be visible on the board and countable in the header, same as any other gap.

**Resolved**: "ambiguous" does not get its own state. It folds into `awaiting decision` (the next action — admin decides — is identical either way), but the *reason* it routed there (split panel vs. low score) is preserved as a computed "split decision" badge on `awaiting decision`, driven by the same cross-round variance calculation used in the consolidation view. This is display metadata, not a lifecycle state.

## Assignment carries a brief

Every round assignment includes `assignment_due_at` and a `brief` — what this interviewer should probe (Google's model: assign attributes per interviewer rather than everyone assessing everything). The brief appears in the assignee's queue (`/my-candidates`).

`scorecard_due_at` is **derived**, not the interview datetime: `interview end + Stage.feedback_grace_hours` (config per stage, default 48h). Never the interview's own start/end time — nobody writes feedback during the meeting.

## Reassignment (resolved)

Reassigning a round mid-flight (interviewer leaves, goes on holiday) creates a **new `Round` row**, not an edit to the existing one. Editing destroys history — this codebase already treats history as sacred elsewhere (`InterviewScore` is explicitly immutable by design; the `is_terminal` migration deliberately left 21 historically-wrong transition rows untouched rather than "fixing" them). The old round closes as `reassigned` with no scorecard; the new round links back via a nullable self-referential `reassigned_from_round_id`. A round with two assignees and no scorecard from the first isn't a data integrity problem under this design — it's the actual, inspectable history.

This is the same close-then-open transaction the round loop's "assign next round" step uses (see above) — implemented as one shared helper, not a second copy with `reassigned` hardcoded in place of `closed_unscored`.

## Consolidation view

The decision view lists every round in order: assignee, dates, score, written feedback, plus a computed average and **variance** across rounds. Variance is what tells the admin where the panel actually disagreed, which is where attention should go. The blind-review rule still holds through this: an interviewer can't read another round's scorecard until their own is submitted.

## Linking Interview and Round (resolved)

`Interview` gets a `round_id`. A round has **at most one active interview**. `Interview.interviewer_id` is **dropped** as an independent field — the interviewer IS the round's assignee, derived, not stored twice. Two sources of truth for "who is interviewing" is how the portal and the calendar end up silently disagreeing after a reassignment.

## Scheduling: one step or two (resolved)

Both must be independently possible at the data-model level (an `assigned but unscheduled` round is a real, reachable state), but the UI shouldn't force two round-trips when the admin already knows availability at assignment time. Recommend: one form, optional inline scheduling fields, one atomic backend transaction that creates the `Round` and (if scheduling info was given) the `Interview` together — never a UI state that assumes "scheduled" succeeded when only the round write did.

## Hold vs. scheduled interviews (resolved — revised)

Auto-cancelling a scheduled interview as a side effect of holding a candidate is implicit behavior nobody asked for. But silently leaving it alone is *equally* implicit from the other direction: the interviewer shows up tomorrow for a candidate who was paused today, and nothing told them.

**Resolution: the hold action must surface the conflict and require an explicit choice.** If an admin puts a candidate with a scheduled interview on hold, the hold flow presents that interview and forces a decision — keep it, or cancel it (invariant 6 already defines what cancelling does: returns the round to `assigned but unscheduled`). There is no default; the admin cannot complete the hold without answering. This is explicit in both directions and adds no hidden behavior — it just moves a decision that was implicitly being made by inaction into an explicit click.

A candidate with no scheduled interview at hold time has nothing to ask about — hold proceeds immediately, unchanged from before.

## Timezone awareness in scheduling (new)

Times render in the viewer's own browser zone today, which is correct. The gap: **the admin scheduling a round has no visibility into what their chosen time means for the assignee.** An admin picks 9am ET; an interviewer in Bangalore gets 6:30pm, and nothing surfaces that at scheduling time.

**`User` gets a `timezone` field** (IANA zone name, e.g. `"America/New_York"`). Resolved on how it's set (grilled and settled): **self-set, with a browser-inferred default applied once at account creation only** — never re-inferred on subsequent logins. Continuous re-inference is actively wrong, not just unnecessary: it would silently reassign someone's scheduling timezone to wherever they're currently logged in from, which breaks exactly the traveling case that makes naive inference unreliable in the first place. A profile setting lets anyone correct or update it anytime by hand.

**When scheduling**, the time picker shows the assignee's local time alongside the admin's own selection, computed live as they choose a time — e.g. "9:00 AM ET · 6:30 PM IST for Priya." **Out-of-hours times are not blocked**, only surfaced — a legitimately early or late round is the admin's call, not a validation error.

**The same surfacing applies to `scorecard_due_at`** in the interviewer's own portal (`/my-candidates`) — already planned to render in the viewer's own timezone; no change there beyond confirming it reads from `User.timezone` rather than assuming browser-local for that specific value if the two ever diverge (e.g. the interviewer is traveling and their browser zone differs from their profile zone — portal should show their working/profile zone, matching the "stable working timezone" reasoning above, not wherever their browser currently is).

## Invariants (server-side, not form validation)

1. An interview's assignee always equals its round's assignee. Reassigning the round reassigns the interview, or the write is rejected.
2. A scorecard cannot be submitted before its interview's end time.
3. **Reworded** — original wording ("a round cannot close without a submitted scorecard") was already false the moment `closed_unscored` existed at all (rejection closes a round with no scorecard by design); this is a correction to a pre-existing doc defect, not a consequence of the one-open-round-per-candidate rule added later in this doc. Corrected: **a round can only transition to `scored` if a scorecard was submitted for it.** Closing as `closed_unscored` or `reassigned` never requires one, and never has.
4. A round cannot be assigned to a deactivated user (`User.is_active = false`, `backend/app/models/user.py:23`), and deactivating a user must surface their open rounds rather than silently orphaning them.
5. An interview cannot be scheduled without an open round.
6. Cancelling an interview returns the round to `assigned but unscheduled`. It does not close the round.

## Interviewer portal (`/my-candidates`)

Reads rounds where `assignee = me` and no scorecard has been submitted yet — `open` or `closed_unscored`, matching submission authorization exactly. This is a deliberate broadening from "open rounds only": an interviewer whose round was closed as `closed_unscored` because the admin advanced the candidate still owes feedback, and dropping them from their own queue the moment that happens would silently recreate the "lost feedback" failure this epic exists to prevent — just moved from the data model into the UI instead of fixed.

Each row: candidate, stage, scheduled datetime in the viewer's own timezone, the brief, and scorecard due date. Sorted by what's due soonest. Three states must be visually distinguishable at a glance: needs scheduling, scheduled and upcoming, interview done and scorecard overdue. **No fourth state for `closed_unscored`** — an interviewer doesn't care about the admin's internal round bookkeeping, only that they owe feedback, so a `closed_unscored` row folds into the existing "scorecard overdue" bucket rather than getting its own visual state. The row's **copy** still has to reflect it, though: submitting feedback on someone who's already moved to the next round is a different ask than on someone interviewed yesterday, and hiding that distinction would make the portal feel wrong even though the underlying query is right. A `closed_unscored` row reads something like *"Candidate has moved to \<next stage\> — your feedback is still needed,"* not the generic overdue copy used for a still-`open` round.

The blind-review rule still applies here too — no other round's scores are visible from this view.

## Health

An overdue scorecard is a stall condition and must feed `compute_health` (the same function from #16, extended with a new input), not just sit passively in the portal — this is the single failure the pipeline board exists to catch.

## Schema (consolidated — new for this review, not yet built)

This is a synthesis of every schema-affecting decision above in one place, so it can be checked as a unit before `/spec`. Several entries make an implementation call the prose above implied but didn't spell out — each is marked so it can be overridden.

**`stages`** (existing table) — add columns:
- `advance_threshold: int | null`
- `reject_threshold: int | null`
- `feedback_grace_hours: int | null`, default `48`

**`users`** (existing table) — add column:
- `timezone: string | null` (IANA zone name, e.g. `"America/New_York"`) — self-set, browser-inferred once at account creation, never re-inferred.

**`rounds`** (new table):
- `id`
- `candidate_id -> candidates.id`
- `stage_id -> stages.id`
- `assignee_id -> users.id`
- `status: enum {open, scored, reassigned, closed_unscored}` — a round's own lifecycle. `closed_unscored` has **two sibling writers, neither more primary than the other**:
  1. **Rejection.** Recording a rejection closes any still-open round as `closed_unscored` — the candidate is done, that round will never be scored.
  2. **Advancing past an unscored round.** The one-open-round-per-candidate rule (below) means opening the next round while a prior one is still `open` must first close that prior round as `closed_unscored` — otherwise the ownership query returns an arbitrary row between two simultaneously-open rounds, and the board's displayed owner flips between requests depending on which row a query happens to return first. This transactional close-then-open is owned by ticket #27 (the "assign next round" step of the loop) and shared with reassignment (ticket #30), which does the same close-then-open with a different resulting status (`reassigned`) — one helper, not two independent implementations of the same transaction (see #27/#30 for why this is a hard requirement, not a suggestion).

  **`closed_unscored` is not fully terminal** — a late scorecard submitted against a `closed_unscored` round transitions it to `scored` (see submission authorization, below). It's "closed" in the sense of no longer being the candidate's active round, not in the sense of being unable to ever receive a scorecard.

  **Hold does not close the round** — resolved separately (see "Hold vs. scheduled interviews" below): hold is meant to be resumable, so an in-progress round stays `open` while the candidate is paused; health is already suspended by the hold itself. (The candidate-level gap state — `awaiting assignment` / `assigned but unscheduled` / `awaiting decision` / `on hold` — is a separate concept from a single round's status; see the derivation note below.)

  **One open round per candidate, enforced, not just recommended**: a partial unique index, `CREATE UNIQUE INDEX ON rounds (candidate_id) WHERE status = 'open'`, guarantees `compute_current_owner` is never ambiguous. The index is the safety net against races; the transactional close-then-open above (owned by #27/#30) is the primary mechanism that keeps the index from ever being violated in the first place.
- `assignment_due_at: datetime | null` — the assignment-level deadline set at round creation (distinct from `scorecard_due_at`, which is derived, not stored — see below). Named specifically (not `due_at`) because two deadlines exist on/near this table and a generic name reads as the scorecard deadline within a month.
- `brief: text`
- `reassigned_from_round_id: int | null -> rounds.id` (self-referential)
- `created_at`, `closed_at: datetime | null` — **set on any transition out of `open`**, for all three non-open statuses (`scored`, `reassigned`, `closed_unscored`) alike — "non-open," not "terminal," since `closed_unscored` can still receive a late scorecard and move to `scored` (see above). `closed_at` is not rewound or cleared when that happens; it still records when the round stopped being the candidate's active round, and the invariant that matters is unaffected by the revival: `closed_at IS NULL` must be exactly equivalent to `status = 'open'`, because both `compute_health` and `compute_gap_state` (below) read `closed_at` to decide whether a round is still active — if any closing transition forgot to set it, those functions would see a "closed" round that still looks open.

**`interviews`** (existing table) — modify:
- add `round_id: int -> rounds.id`, NOT NULL (invariant 5: no interview without an open round)
- **drop `interviewer_id`** — derived from `round.assignee_id`, per the "two sources of truth" reasoning above
- **add `status: enum {scheduled, cancelled}`.** This does not exist today — checked directly: `Interview` has no status column, and the current "Cancel interview" action (`backend/app/routers/interviews.py:75-84`) is a hard `db.delete(interview)`, not a soft cancel. That has to change as part of this epic: "at most one active interview per round" only means anything if a cancelled interview still exists as a row (per invariant 6, a cancelled interview keeps its `round_id` while a replacement is created for the same round) — a hard delete already trivially satisfies uniqueness by destroying the evidence, which also silently regresses the history-preservation principle the rest of this design leans on (immutable scores, reassignment-as-new-row). So cancellation becomes an update (`status = 'cancelled'`), not a delete.
- **constraint: a partial unique index on `interviews(round_id) WHERE status != 'cancelled'`, not an app-level check.** An app-level "does this round already have an active interview" check loses the race on a double-submit (two concurrent requests can both pass the check before either writes); a partial unique index is enforced by Postgres itself and can't be raced. This is exactly why `status` has to exist as a real column and not just be inferred from "the row still exists."

**`interview_scores`** (existing table) — modify:
- add `round_id: int -> rounds.id`
- **the existing unique constraint on `(candidate_id, question_id)` cannot survive** and is dropped. Multiple rounds means the same question can legitimately be scored twice by different interviewers (or the same interviewer re-running a stage) — keeping it would make the migration fail the moment two rounds for one candidate both scored the same question, which is exactly the shape real multi-round data has. New unique constraint: `(round_id, question_id)`.
- migration: every existing `interview_scores` row backfills its new `round_id` from the same backfilled `Round` its candidate got (see `candidates` below) — one round per legacy candidate means every legacy score attaches to that one round unambiguously. Column is added nullable, backfilled, then set NOT NULL, then the old constraint is dropped and the new one added — standard expand/contract order so the migration never has a moment where a row violates either constraint.

**`candidates`** (existing table) — modify:
- **`interviewer_id` is dropped as a stored column, and it splits into THREE independent queries, not two** — the first pass at this design collapsed a genuinely distinct third case into "access," which was wrong:
  - **Ownership (display)** — "who owns this candidate right now" = the assignee of the candidate's currently **open** `Round`. Nullable (a candidate between rounds, e.g. `awaiting assignment`, has no current owner). Used by: the board, the candidate detail header, anywhere showing "assigned to X" as a present-tense fact. Lives in `app/pipeline/derive.py` alongside the other derived-fields logic as e.g. `compute_current_owner`.
  - **Access (read authorization)** — "can this user see this candidate" = **any** `Round` exists for this candidate with `assignee_id = this user`, in **any** status, including `closed` and `reassigned`. Existence check across all rounds, not "the open one" — computing this from only the open round means an interviewer loses access the instant their scorecard is submitted, breaking both re-reading their own feedback and the consolidation view for anyone whose round already closed. Lives in the auth/access-control layer, as its own query, never derived from or sharing code with ownership.
  - **Submission authorization — corrected, not just refined.** The first pass at this defined it as "an open `Round` exists for this candidate with this user as assignee," which turned out to directly contradict the one-open-round-per-candidate rule (below): if a round-1 interviewer's late submission must succeed after the admin has already opened round 2, round 1 can't simultaneously be required to stay `open` (there'd be two open rounds) and be findable by an "is it open" check. Resolved: **advancing to the next round closes the prior one as `closed_unscored` if it was still open** (see the `rounds.status` entry above), and submission authorization stops filtering on `open` at all — it's **"does `round_id X` belong to this user, and does it have no scorecard yet"** (status `open` or `closed_unscored`, not `scored`/`reassigned`). It's also now scoped by an explicit `round_id`, not resolved implicitly from `candidate_id` — if the same interviewer was ever assigned to this candidate more than once (re-interviewed across stages), "a qualifying round exists" could match more than one row, and the caller has to say which one a given submission is for. This is `app/scoring/submit.py:29`'s actual shape once rounds exist, and it stays a fully separate query, not a variant of either of the other two above.
  - **The round-1-late-submission edge case, resolved**: an admin opens round 2 while round 1's scorecard is still unsubmitted → round 1 closes as `closed_unscored` (the transactional close-then-open owned by #27, shared with #30's reassignment). The round-1 interviewer's late submission still succeeds — submission authorization finds `round_id` = round 1, confirms it belongs to them and has no scorecard yet (its `closed_unscored` status doesn't disqualify it), and scoring it transitions it to `scored`. Round 2 existing is irrelevant to whether round 1 can still be scored.
  - **One open round per candidate is now enforced, not flagged as an open question.** A partial unique index (`rounds(candidate_id) WHERE status='open'`) guarantees `compute_current_owner` is never ambiguous — the earlier version of this doc left this as an unresolved fork between "enforce uniqueness" and "allow concurrency with a tie-break"; it's settled on enforcement, because the alternative (concurrent open rounds) had no clean answer to "who does the board say owns this candidate" and this one does.
  - Concretely: `/my-candidates` (the portal's "what am I working on") filters by ownership (open round) **plus any `closed_unscored` round with no scorecard yet** — an interviewer whose round got closed out from under them by an advance still needs to see it, worded so the copy reflects that the candidate moved on (see "Interviewer portal" below); a direct fetch of a specific candidate's detail/consolidation view by an interviewer checks access (any round, ever); a scorecard submission checks submission authorization (a specific `round_id`, no scorecard yet, `open` or `closed_unscored`). Three call sites, three queries — none of them share an implementation.
  - **Complete call-site inventory** (grepped `Candidate.interviewer_id` across the backend — every hit, classified):
    - `app/routers/interviewer.py:19` (`_get_own_candidate_or_404`) — **access check**, gates GET/detail routes under `/api/interviewer/candidates/{id}`. Becomes the access query (any round, ever).
    - `app/routers/interviewer.py:31` (`list_my_candidates`) — **ownership query**, the actual `/my-candidates` list. Becomes the ownership query (open round), unchanged in kind.
    - `app/scoring/submit.py:29` (`submit_scores`) — **submission authorization**, its own third query (see above), not a variant of access or ownership.
    - `app/routers/pipeline.py:140` (board response) — **display**, becomes `compute_current_owner`.
    - `app/routers/admin_candidates.py:42-51` (candidate creation) — **write**, sets the initial owner. Becomes "create the candidate's first `Round`" instead of setting a column.
    - `app/routers/admin_candidates.py:87-98` (candidate update, admin changes `interviewer_id`) — **write**, today's version of reassignment. This line range does not get a minimal in-place rewrite: **#26 removes this write path entirely** (the column it mutates no longer exists), and **#30 builds its replacement** (close current round as `reassigned`, open a new one) as new code, not an edit to what #26 leaves behind. Reassignment is unavailable between #26 landing and #30 landing — an explicit, honest gap, not a half-built mechanic split across two PRs.
    - `app/seed/backfill_realistic_positions.py:97-99,132`, `app/seed/seed_demo_pipeline.py:94` — seed scripts that set `Candidate.interviewer_id`/`Interview.interviewer_id` directly. Not app logic, but they break the moment the column is dropped and need updating to create `Round` rows instead — worth its own checklist item in the migration ticket, not something to discover mid-PR.
    - `app/schemas/candidate.py:13,20,29`, `app/schemas/interview.py:8,19`, `app/schemas/pipeline.py:31` — Pydantic field declarations following the model; update in lockstep with the model changes, no independent logic of their own.
- add `hold_reason: text | null`, `hold_review_by: date | null` — hold is orthogonal to `Stage` (a candidate can be on hold at any stage), so it lives on `Candidate`, not `Round` or `Stage`.
- the candidate-level gap state (`awaiting assignment` / `assigned but unscheduled` / `awaiting decision` / `on hold` / terminal) is **derived, not a stored column** — and it must be derived in the same module as `compute_health` and `compute_next_action` (`app/pipeline/derive.py`), not a fourth place that independently reasons about candidate state. This is the exact failure mode the UI audit already caught once (§4.1): `compute_health` and `compute_next_action` drifted because terminal-stage handling was implemented in one and forgotten in the other. A new `compute_gap_state` (or equivalent) belongs in `derive.py`, reads the same inputs (current round, its interview, hold fields, `stage.is_terminal`) the other two functions already read, and ships in the same PR as any change to either of them so the three can't drift apart again.
- **migration for the 21 existing candidates**: `interviewer_id` is **backfilled into a `Round` row**, not dropped. Each existing candidate gets exactly one `Round` created: `candidate_id` = the candidate, `stage_id` = the candidate's current stage, `assignee_id` = their current `interviewer_id`, `status = "open"` (there's no historical data to tell us it was ever scored and closed), `assignment_due_at = null`, `brief = null`. This is what makes both the ownership query and the access query keep working immediately post-migration: the open round gives every legacy candidate a display owner identical to what `interviewer_id` showed before, and the access check now has a real `Round` row to find instead of coming up empty and locking every existing interviewer out of every existing candidate. Dropping `interviewer_id` outright with no backfill would silently break both.

## Accepted deviations (implementation-status audit, 2026-09-06)

**#29 AC1** ("`User.timezone` is set automatically... exactly once, at account creation, and never overwritten by inference again"): the shipped mechanism (`app/routers/auth.py`'s `login`) sets it from browser inference on **any** login where `user.timezone is None`, not specifically the first-ever login. Accepted as-is: the two are behaviorally equivalent for the property AC1 actually protects — once a value exists (whether set by inference or by the user manually), it is never overwritten by inference again. The literal "at account creation" phrasing is stricter than necessary; not reworked.

## Out of scope for this doc

- No code. This is the design; `/spec` and ticket creation follow once this is confirmed.
- Migrating the 21 existing historically-backwards `CandidateStageTransition` rows — unaffected by this epic, same reasoning as #16 (audit log, not corrected data).
- Deciding whether `Hired`/`Rejected` need their own round semantics beyond what `is_terminal` already gives them (#16) — not raised in this design, flag separately if it turns out to matter.

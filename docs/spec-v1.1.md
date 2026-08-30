# Feature Specification: Interview Management Portal — v1.1

**Status:** Design complete, ready for implementation
**Owner:** Amaresh Padala
**Last updated:** 2026-08-30
**Supersedes:** `spec-v1-mvp.md` (this doc extends it with edit/delete/deactivate; the
core scoring loop, schema shape, and stack are unchanged)

---

## 1. Goal

Same as v1: replace ad hoc spreadsheet-based interview feedback with a
structured, persistent record. Interviews still happen physically/verbally —
the tool manages the record, not the interview itself.

**Change from v1:** v1 was strictly create-only (no way to fix a mistake
short of a DB edit). v1.1 adds edit/delete/deactivate for
positions/questions/candidates/users, gated so that once real interview data
exists against a record, that data can never be silently destroyed or
invalidated.

**Still explicitly out of scope** (unchanged from v1's "Later Phases"):
candidate-facing anything, email/notifications, panel interviews, full
audit history (field-level change log), CSV export, admin aggregation
dashboards, position lifecycle (Draft/Open/Closed), multiple applications
per candidate, reopening a completed candidate / editing submitted scores.

---

## 2. Roles

| Role | Can do |
|---|---|
| **Admin** | Log in. Create/edit Positions (title). Create/edit/delete Questions (delete only if unscored). Create/edit/delete Candidates (delete only if `not_started`); reassign interviewer while `not_started`. Create/edit Users; deactivate/reactivate (no hard delete); reset a user's password. |
| **Interviewer** | Log in. See candidates assigned to them, not yet completed. Open a candidate, see ordered questions, score 1–5 + comment each, submit once (atomic, immutable after). |

No candidate accounts. No public signup. First admin is created via a
one-time seed script; every account after that is created by an admin
through the app.

---

## 3. Explicit Decisions & Assumptions

Decided this session (see conversation for full rationale on each):

1. **Scope**: v1's minimal loop stays, but create-only is dropped —
   edit/delete added per-entity, gated by whether dependent data exists.
2. **Stack locked**: FastAPI + PostgreSQL + SQLAlchemy + Alembic + React. No
   framework spike.
3. **CI**: GitHub Actions runs the full test suite on every push; merge
   blocked on failure. No deploy automation yet.
4. **Bootstrap**: one-time seed script (`create_admin.py`) creates the first
   admin from env vars / prompt, run once at deploy time.
5. **User creation**: `POST /api/admin/users`, admin-only, can create more
   admins or interviewers — no special-casing.
6. **Password reset**: admin-triggered (`POST /api/admin/users/{id}/reset-password`),
   relayed out-of-band (verbal/Slack) — no email in v1.1.
7. **Edit/delete matrix** (see §5) — the core new decision this round.
8. **Position with zero questions**: blocked at candidate creation (400) +
   proactive "0 questions" badge on the admin's position list.
9. **Scores are immutable once submitted** — no reopen mechanism, no
   per-score edit, even though everything else is now editable. This is the
   one line that didn't move, because a real audit trail (deferred) is the
   real prerequisite for making score edits safe.
10. **Draft persistence**: `localStorage` autosave keyed by candidate id,
    frontend-only, cleared on successful submit. Never touches the DB
    pre-submit — doesn't compromise the atomic-submit invariant.
11. **Duplicate/concurrent submission**: `candidate.status` checked before
    insert; already-`completed` → `409` with a clear message, not a raw
    `UNIQUE` constraint 500.
12. **Minimal audit signal**: `updated_at` on all four editable entities.
    No `updated_by`, no field-level history (that's the deferred full audit
    trail).
13. **User deactivation**: `is_active` boolean, not a hard delete. Login
    rejects inactive users with the same generic 401 as a bad password (no
    account-state leakage). Deactivated interviewers drop out of the
    candidate-assignment picker for *new* candidates; existing candidates
    keep their `interviewer_id` unchanged.
14. **Frontend floor**: empty/loading/403/generic-error states; mobile-friendly
    (not mobile-first); semantic HTML + labeled inputs, no formal WCAG audit.
15. **Local dev**: Docker Compose (Postgres + API + frontend), one-command
    spin-up.

**Assumptions** (not explicitly stated by you, carried forward as
reasonable defaults — flag if wrong):

- Error responses use FastAPI's default `{"detail": "..."}` shape.
- `ON DELETE RESTRICT` (or no cascade) at the DB level for all FKs — the app
  layer already prevents delete attempts where dependents exist, so the DB
  constraint is a backstop, not the primary enforcement.
- No seed *sample data* beyond the bootstrap admin — positions/questions
  created manually through the app during dev/testing.
- Editing a Question's text does not retroactively invalidate or require
  re-scoring already-recorded `interview_scores` rows against it (per your
  Q13 answer — edit allowed even with scores attached).

---

## 4. Data Model

```sql
CREATE TYPE user_role AS ENUM ('admin', 'interviewer');

CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    role user_role NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE sessions (
    id VARCHAR(64) PRIMARY KEY,
    user_id INT NOT NULL REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE positions (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    created_by INT NOT NULL REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE questions (
    id SERIAL PRIMARY KEY,
    position_id INT NOT NULL REFERENCES positions(id),
    question_text TEXT NOT NULL,
    sequence_order INT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (position_id, sequence_order)
);

CREATE TABLE candidates (
    id SERIAL PRIMARY KEY,
    full_name VARCHAR(255) NOT NULL,
    email VARCHAR(255),
    phone VARCHAR(50),
    position_id INT NOT NULL REFERENCES positions(id),
    interviewer_id INT NOT NULL REFERENCES users(id),
    status VARCHAR(20) NOT NULL DEFAULT 'not_started',  -- not_started | completed
    created_by INT NOT NULL REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE interview_scores (
    id SERIAL PRIMARY KEY,
    candidate_id INT NOT NULL REFERENCES candidates(id),
    question_id INT NOT NULL REFERENCES questions(id),
    score INT NOT NULL CHECK (score BETWEEN 1 AND 5),
    comment TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (candidate_id, question_id)
    -- no updated_at: rows are immutable once written, by design (decision 9)
);
```

**Delete/edit gating enforced in the application layer** (not purely in the
DB), because the rule depends on *related-row existence*, not a static
constraint:

| Entity | Edit | Delete |
|---|---|---|
| Position | title | never (no endpoint) |
| Question | text — always, even with scores | only if zero `interview_scores` rows reference it → else `400` |
| Candidate | name/email/phone — always; `interviewer_id` — only while `status = 'not_started'` | only while `status = 'not_started'` → else `400` |
| User | full_name | never — `POST .../deactivate` / `.../reactivate` instead |

---

## 5. API Surface

| Method | Path | Role | Purpose |
|---|---|---|---|
| POST | `/api/auth/login` | anyone | Email+password → session cookie |
| POST | `/api/auth/logout` | logged in | Clear session |
| POST | `/api/admin/users` | admin | Create a user (admin or interviewer) |
| GET | `/api/admin/users` | admin | List users |
| PATCH | `/api/admin/users/{id}` | admin | Edit `full_name` |
| POST | `/api/admin/users/{id}/deactivate` | admin | Set `is_active = false` |
| POST | `/api/admin/users/{id}/reactivate` | admin | Set `is_active = true` |
| POST | `/api/admin/users/{id}/reset-password` | admin | Set a new password hash |
| POST | `/api/admin/positions` | admin | Create a Position |
| GET | `/api/admin/positions` | admin | List Positions, incl. `question_count` for the "0 questions" badge |
| PATCH | `/api/admin/positions/{id}` | admin | Edit `title` |
| POST | `/api/admin/positions/{id}/questions` | admin | Add a question |
| GET | `/api/admin/positions/{id}/questions` | admin | List questions, ordered |
| PATCH | `/api/admin/questions/{id}` | admin | Edit `question_text` |
| DELETE | `/api/admin/questions/{id}` | admin | Delete; `400` if scores exist |
| POST | `/api/admin/candidates` | admin | Create; `400` if position has 0 questions |
| GET | `/api/admin/candidates` | admin | List candidates |
| GET | `/api/admin/candidates/{id}` | admin | Get one candidate |
| PATCH | `/api/admin/candidates/{id}` | admin | Edit fields; `interviewer_id` change rejected (`400`) unless `status = 'not_started'` |
| DELETE | `/api/admin/candidates/{id}` | admin | Delete; `400` if `status = 'completed'` |
| GET | `/api/interviewer/candidates` | interviewer | My candidates, `not_started` only |
| GET | `/api/interviewer/candidates/{id}` | interviewer | Candidate + ordered questions + any existing scores |
| POST | `/api/interviewer/candidates/{id}/scores` | interviewer | Submit all scores atomically; `409` if already `completed` |

Interviewer routes always filter by `interviewer_id = current session
user` at the query level — never just hidden in the UI.

**Scorecard payload** (`POST .../scores`):
```json
{
  "scores": [
    { "question_id": 12, "score": 4, "comment": "Strong on tradeoffs" },
    { "question_id": 13, "score": 3, "comment": "" }
  ]
}
```
Server validates the submitted `question_id` set exactly matches the
position's current question set before writing anything (all-or-nothing,
per the existing `submit_scores` algorithm in `ia-documentation-v1.md`).

**Error shape**: `{"detail": "<human-readable message>"}`, FastAPI default.
Specific 400/409 messages should name the concrete reason (e.g. `"Cannot
delete question — 3 scores already recorded against it."`) rather than a
generic "bad request."

---

## 6. Folder Structure

```
interview-platform/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py              # env-driven settings
│   │   ├── database.py            # SQLAlchemy engine/session
│   │   ├── models/                # user.py, position.py, question.py,
│   │   │                          # candidate.py, interview_score.py
│   │   ├── schemas/                # Pydantic request/response models
│   │   ├── routers/                # auth.py, admin_users.py,
│   │   │                          # admin_positions.py, admin_questions.py,
│   │   │                          # admin_candidates.py, interviewer.py
│   │   ├── auth/                   # hashing.py, session.py, dependencies.py
│   │   └── seed/
│   │       └── create_admin.py
│   ├── alembic/
│   │   └── versions/
│   ├── tests/
│   │   ├── unit/
│   │   └── integration/
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── pages/                  # Login, AdminPositions,
│   │   │                          # AdminPositionDetail, AdminUsers,
│   │   │                          # AdminCandidates, InterviewerQueue,
│   │   │                          # InterviewerScoreCandidate
│   │   ├── components/
│   │   ├── api/                    # typed API client
│   │   ├── hooks/
│   │   └── App.tsx
│   ├── package.json
│   └── Dockerfile
├── docker-compose.yml
├── .github/workflows/ci.yml
└── README.md                        # local dev setup, migration/seed commands
```

---

## 7. Implementation Plan

| Phase | Work | Est. |
|---|---|---|
| 1 | Schema + Alembic migrations + `create_admin.py` seed script | 0.5d |
| 2 | Auth: login/logout/session, password hashing, reset-password, deactivate/reactivate | 1d |
| 3 | Admin Users: create/edit/list | 0.5d |
| 4 | Admin Positions + Questions: create/edit position; create/edit/delete question (score-check) | 1d |
| 5 | Admin Candidates: create (zero-question block), edit, delete (`not_started`-only), reassign | 1d |
| 6 | Interviewer queue + scoring form + atomic submit + 409 duplicate handling | 1.5d |
| 7 | Frontend states (empty/loading/403/error) + `localStorage` autosave + responsive pass | 1d |
| 8 | Tests: unit + integration (see §9) | 1.5d |
| 9 | Docker Compose + GitHub Actions CI | 0.5d |

**Total: ~8.5 days** (up from v1's 4 days — the edit/delete/deactivate
surface roughly doubles the entity-CRUD work).

---

## 8. Risks & Unresolved Questions

Flagging these now rather than letting them surface mid-build:

1. **Deactivating an interviewer with active (`not_started`) candidates
   assigned** — not decided. Does the admin get warned at deactivation time
   ("this interviewer has 3 pending candidates"), or is it silent (the
   candidates just sit there until someone reassigns them manually)?
2. **`localStorage` autosave is per-browser/device** — if an interviewer
   switches devices or clears site data mid-interview, the draft is lost
   with no warning. Acceptable for v1.1 per your call, but worth knowing
   it's a real (if small) gap.
3. **No field-level audit trail** — if a question's text is disputed later
   ("it used to say X, now it says Y, who changed it and when"),
   `updated_at` can confirm *that* it changed but not *what* or *who*. This
   was an explicit tradeoff (decision 12), not an oversight.
4. **Growing pressure toward "Later Phases"** — the number of things you
   pulled forward this session (edit/delete/deactivate) suggests some of
   the still-deferred items (CSV export, aggregation dashboard,
   Draft/Open/Closed position lifecycle) may get requested sooner than
   "later." Worth a lightweight re-check after the first real usage round
   rather than assuming they stay deferred indefinitely.

---

## 9. Tests Needed

Extends `ia-documentation-v1.md`'s T1–T15 (still all valid, unchanged) with:

| Test ID | Description | Expected Outcome |
|---|---|---|
| T16 | Login as deactivated user | `401`, generic message (same as bad password) |
| T17 | Deactivated interviewer in candidate-creation picker | Excluded from the list |
| T18 | Reactivate a deactivated user | Can log in again |
| T19 | Edit position title | `200`, title updated, `updated_at` bumped |
| T20 | Edit question text with existing scores attached | `200`, allowed, scores untouched |
| T21 | Delete question with zero scores | `200`/`204`, removed |
| T22 | Delete question with existing scores | `400`, not deleted |
| T23 | Edit candidate name/email/phone regardless of status | `200` in both `not_started` and `completed` |
| T24 | Reassign interviewer on `not_started` candidate | `200`, `interviewer_id` updated |
| T25 | Reassign interviewer on `completed` candidate | `400`, rejected |
| T26 | Delete candidate while `not_started` | `200`/`204`, removed |
| T27 | Delete candidate while `completed` | `400`, rejected |
| T28 | Create candidate against a position with 0 questions | `400`, candidate not created |
| T29 | Admin position list shows "0 questions" badge | Badge present for empty positions only |
| T30 | Re-submit scores for an already-`completed` candidate | `409`, not `500`, no duplicate rows written |
| T31 | Admin resets a user's password | Old password fails login, new one succeeds |
| T32 | `updated_at` bumps on edit | Verified for each of the 4 editable entities |

All 8 original success criteria remain covered by T1–T15; T16–T32 cover the
v1.1 edit/delete/deactivate surface end to end, including every gating rule
from §4/§5's tables (both the "allowed" and "blocked" branch of each).

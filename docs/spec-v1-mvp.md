# Feature Specification: Interview Feedback Platform — v1 (First Step)

**Status:** Draft
**Owner:** Amaresh Padala
**Last updated:** 2026-08-21

## 1. Goal

Replace ad hoc, undocumented interview feedback with a structured, persistent
record. This platform **manages** interviews — it does not **run** them.
Interviews happen physically, verbally, outside the tool. The tool's only job
is: let an interviewer record structured scores against a known question set,
and store that data reliably in Postgres for later reference.

**Out of scope for this step:** candidate-facing anything (no candidate
login), email/notifications, panel interviews, audit history, CSV export,
admin aggregation dashboards, position lifecycle (Draft/Open/Closed),
multiple applications per candidate. Those are real, already-scoped
follow-on work — see "Later phases" at the bottom — but they are not part of
this first cut.

## 2. Roles

| Role | Can do |
|------|--------|
| **Admin** | Log in. Create Positions. Create an ordered Question list per Position. Create Candidates. Assign an Interviewer to a Candidate for a Position. |
| **Interviewer** | Log in. See the list of candidates assigned to them. Open an assigned candidate, see the ordered question list, ask them verbally, enter a 1-5 score + comment per question, submit. |

No candidate accounts. No public sign-up — Admin creates all user accounts.

## 3. Data Model (v1 slice)

```sql
CREATE TYPE user_role AS ENUM ('admin', 'interviewer');

CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    role user_role NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE sessions (
    id VARCHAR(64) PRIMARY KEY,          -- random session token
    user_id INT NOT NULL REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE positions (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    created_by INT NOT NULL REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE questions (
    id SERIAL PRIMARY KEY,
    position_id INT NOT NULL REFERENCES positions(id),
    question_text TEXT NOT NULL,
    sequence_order INT NOT NULL,
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
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE interview_scores (
    id SERIAL PRIMARY KEY,
    candidate_id INT NOT NULL REFERENCES candidates(id),
    question_id INT NOT NULL REFERENCES questions(id),
    score INT NOT NULL CHECK (score BETWEEN 1 AND 5),
    comment TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (candidate_id, question_id)
);
```

Note: this collapses the fuller model (Position → Rounds → Questions,
Candidate → Application → RoundAssignment) down to one interviewer per
candidate per position, one flat question list. That richer model is the
target for later phases; this table shape is the minimum that satisfies "one
interviewer, one candidate, one question list, one set of scores."

## 4. API Surface (v1 slice)

| Method | Path | Role | Purpose |
|--------|------|------|---------|
| POST | `/api/auth/login` | anyone | Email+password → session cookie |
| POST | `/api/auth/logout` | logged in | Clear session |
| POST | `/api/admin/positions` | admin | Create a Position |
| POST | `/api/admin/positions/{id}/questions` | admin | Add a question to a Position |
| GET | `/api/admin/positions/{id}/questions` | admin | List questions for a Position |
| POST | `/api/admin/candidates` | admin | Create a Candidate, assign Position + Interviewer |
| GET | `/api/interviewer/candidates` | interviewer | List candidates assigned to me, not yet completed |
| GET | `/api/interviewer/candidates/{id}` | interviewer | Get candidate + ordered question list + any existing scores |
| POST | `/api/interviewer/candidates/{id}/scores` | interviewer | Submit all scores for this candidate (score+comment per question), marks candidate `completed` |

Interviewers only ever see candidates assigned to them (`interviewer_id`
filter on every query) — no cross-interviewer visibility.

## 5. User Flows

**Admin — set up a Position:**
1. Log in.
2. Create Position ("Backend Engineer").
3. Add questions in order ("Explain how you'd design a rate limiter", "Walk through a bug you fixed under pressure", ...).
4. Create a Candidate, pick the Position, pick an Interviewer.

**Interviewer — score a candidate:**
1. Log in.
2. See list of assigned candidates (status: not started).
3. Open a candidate → see the ordered question list for that Position.
4. Ask each question verbally, enter a 1-5 score + optional comment per question.
5. Submit → candidate status becomes `completed`, scores are persisted.

## 6. Acceptance Criteria

1. Admin can create a Position and add an ordered list of questions to it.
2. Admin can create a Candidate, assigning exactly one Position and one Interviewer.
3. Interviewer sees only candidates assigned to them, filtered to `not_started`.
4. Interviewer can open a candidate and see the Position's questions in order.
5. Interviewer can enter a 1-5 score (enforced by DB CHECK constraint) plus an optional comment per question.
6. Submitting writes all scores to `interview_scores` and flips the candidate's status to `completed` in the same transaction.
7. A submitted candidate no longer appears in the interviewer's active queue.
8. Data survives a server restart (Postgres-backed, no in-memory state).

## 7. Testing Plan

| Layer | What | Count |
|-------|------|-------|
| Unit | Password hashing/verification, session expiry check, score CHECK constraint (reject 0, 6, null) | +5 |
| Integration | Admin creates position+questions, admin creates candidate, interviewer sees queue, interviewer submits scores, candidate disappears from queue | +5 |

## 8. Effort Estimate

- Auth (users, sessions, login/logout): 1 day
- Position + question CRUD (admin): 0.5 day
- Candidate CRUD + assignment (admin): 0.5 day
- Interviewer queue + scoring form + submit: 1.5 days
- Tests: 0.5 day

**Total: ~4 days**

## 9. Later Phases (explicitly deferred, already scoped in the fuller epic)

- Multiple Rounds per Position, each with its own question list
- Panel interviews (multiple interviewers per round)
- Multiple Applications per Candidate over time (reapplication)
- Admin aggregated cross-interviewer view + Final Decision field
- Score edit window + audit history (`score_history`)
- Position lifecycle (Draft → Open → Closed → reopen)
- Email notifications (assignment + password reset) via Gmail SMTP
- Auto-computed pipeline status ("Round 2 of 4 in progress")

These were fully designed in the grilling session preceding this doc; this
v1 slice intentionally leaves them out to ship the smallest useful loop first.

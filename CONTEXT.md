# Interview Management Portal

Internal tool that manages the *record* of a physical, verbal interview — an admin sets up who gets asked what, an interviewer scores it once. The tool never runs or schedules the interview itself.

## Language

**Position**:
A role being hired for, with a title and an ordered set of Questions. Positions are never deleted, only their title edited.

**Question**:
A single ordered prompt belonging to one Position, asked verbally and scored 1-5. Editable at any time (even with scores recorded against it); deletable only while it has zero recorded scores.
_Avoid_: Competency, prompt

**Candidate**:
One person being interviewed for exactly one Position by exactly one assigned Interviewer. Has a `status` of `not_started` or `completed`. Fields (name/email/phone) are always editable; the assigned Interviewer is only reassignable while `not_started`; the record is only deletable while `not_started`.
_Avoid_: Applicant

**Interviewer**:
A `user` role that can see and score only the Candidates assigned to them. Deactivating an Interviewer (see below) doesn't change who they're already assigned to — it only removes them from the picker for *new* assignments.

**Admin**:
A `user` role that manages Positions, Questions, Candidates, and Users. Can create other Admins — no special-casing.

**Score**:
One Interviewer's 1-5 rating + optional comment for one Question against one Candidate. Written once, atomically, alongside every other Score for that Candidate in the same submission — immutable after that. There is no mechanism to edit or delete a Score, and no way to reopen a `completed` Candidate to add more.
_Avoid_: Rating, evaluation, feedback (in the DB-row sense — "feedback" is fine as the general product concept)

**Deactivate**:
Disabling a User's ability to log in (`is_active = false`) without deleting the row — Users are never hard-deleted, since doing so would orphan every Candidate/Position they created or were assigned to. Reversible via reactivate.
_Avoid_: Delete (a User), disable, suspend

**Draft**:
An interviewer's in-progress, not-yet-submitted scores for a Candidate, held only in the browser's `localStorage` — never written to the database until a full atomic Submit. Cleared on successful submit.

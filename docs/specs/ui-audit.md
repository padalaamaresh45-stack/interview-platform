# UI Consistency & Data Integrity Audit

Scope: pipeline board (`/`), `/positions`, `/candidates`, `/candidates/:id`, `/users`, `/my-candidates`, `/calendar`, `/login`. All values below are read directly from `frontend/src/index.css`, the page components, and (for Part 2) live queries against the running dev database. Nothing in this document has been fixed — it's an inventory.

## 1. Five tables of actual values found

### 1.1 Font-sizes

| Size | Where it comes from |
|---|---|
| 10px | `.health-pill`, `.status-pill`, `.calendar-day-count` |
| 11px | `.stat-label`, `.calendar-weekday`, `.field-hint` |
| 12px | Login: `.login-card form label`, `.login-forgot` |
| 12.5px | App-wide `.page form label`, `.page-header-count`, `.record-card-meta`, `.toggle-caption` |
| 13px | `.pipeline-column-header`, `.pipeline-column-collapsed`, buttons (global scale); Login: subtitle, footer |
| 13.5px | Default body/table-cell/input copy (global scale), `.pipeline-card` |
| 14px | Login: input, button text |
| 15px | `.stat-value`, `.record-card-title` |
| 17px | `h2` (global) |
| 20px | Login: `h1` |
| 22px | `.board-header h1` |
| 26px | `h1` (global, every `.page`-wrapped page) |

**12 distinct sizes app-wide.** `index.css` documents its own type scale in a comment (lines 64–76) listing 10 sizes as the intended total, **including a stated intentional override**: "22px/800 — h1 inside `.board-header` (denser context)" is explicitly one of the 10 — the board's 22px is compliant, not a violation. The two genuine violations are login's 12/13/14/20 set, none of which appear anywhere in the documented list. Login's scale shares **zero** exact values with the rest of the app; its nearest neighbors (12 vs 12.5, 13 vs 13.5) are off by 0.5px, so it reads as a parallel near-duplicate scale rather than reuse of existing sizes.

### 1.2 Border-radii

| Radius | Where |
|---|---|
| 8px | `.page input/select/textarea` (Positions, Candidates, Users, Calendar) |
| 10px | Login input/button/`.app-mark`, `.page button.calendar-day`, `.nav-rail-item` |
| 12px | `.record-card`, `.page td:first-child/last-child` |
| 14px | `.panel`, `.page form` |
| 16px | `.pipeline-card`, `.pipeline-column-empty`, `.login-card` |
| 50% | `.stage-progress-dot` |
| 999px | Every pill: `.btn-primary`, `.btn-secondary`, `.page button[type=submit]`, `.page button:not([type=submit])`, `.status-pill`, `.health-pill`, `.toggle-track` |

**7 distinct values**, with 8px/10px/12px doing near-identical jobs (rounding a small interactive rectangle) on different pages.

### 1.3 Accent colors

| Color | Token | Where it appears |
|---|---|---|
| Coral/orange `#e0562f` | `--health-stalled` | `.danger`, `.health-pill.stalled`, `.pipeline-card.health-stalled` (border-left), `.status-pill.status-inactive`, `.page > p[role=alert]`, `.page button.btn-danger`, `.login-error` |
| Unstyled blue (browser default) | none — no token | `.nav-rail-item` focus ring (no `:focus`/`:focus-visible` rule exists for it anywhere, so Tab lands the browser's default outline against the black rail) |

**There is exactly one designed accent color in the entire app** (`--health-stalled`), doing six different semantic jobs (stalled health, inactive user, generic error banner, destructive button, error icon, generic "danger" text). The "blue" on the nav rail isn't a designed accent at all — it's an omission (no focus style was ever written for `.nav-rail-item`).

### 1.4 Spacing values

| Context | Values in use |
|---|---|
| App-wide (ad hoc, no spacing token) | 4, 6, 8, 10, 12, 14, 16, 20, 24, 28, 32, 40, 56 |
| Login card (its own scale) | 4, 6, 20, 28 |

Login reuses 20 and 28 from the app-wide set, but its 4 and 6 don't appear anywhere else in the app (the nearest app-wide value below 8 is nothing — the app-wide scale has no 4 or 6).

### 1.5 List-row treatments

| Treatment | Used on |
|---|---|
| Real `<table>` rows | Candidates, Users |
| `.record-card` as `<Link>` | Positions, InterviewerQueue (`/my-candidates`) |
| `.record-card` as a plain `<div>` wrapping a nested `<Link>` | Calendar's day-detail interview list |
| `.pipeline-card` (custom `<div role="button">`) | Pipeline board |
| `.history-list li` (bordered row) | Candidate detail — shared by three unrelated data types: interviews, stage history, and scores |

**Five different idioms** for what is, conceptually, "render a list of records" in every one of these cases.

## 2. Per-page inventory

### Pipeline board (`/`)
No `.page` wrapper — its own full-width layout.
- Title: `.board-header h1`, 22px/800 — the only page whose `<h1>` isn't 26px.
- Font-sizes: 10, 12.5, 13, 13.5, 22.
- Radii: 16 (`.pipeline-column-empty`, `.pipeline-card`), 999 (`.pipeline-column-collapsed`, `.pipeline-card-avatar`, `.health-pill`, `.btn-primary`, `.btn-secondary`).
- Accent: `--health-stalled` on `.pipeline-card.health-stalled` (border-left), `.health-pill.stalled`, `.danger` text.
- List rendering: `.pipeline-card`, a `<div role="button" tabIndex={0}>` with `onClick`/`onDragStart` but **no `onKeyDown`** — reachable by Tab, not activatable by Enter/Space.
- Creation: "+ Add candidate" is a `.btn-primary` that **navigates to `/candidates`** — a separate page, not inline/modal/drawer. The one list page whose creation flow isn't a permanently-open form on the same page.
- Primary button: `.btn-primary` — pill, `--cta-bg`, 13px/600.

### Positions (`/positions`)
- Title: `<h1>`, 26px/800 (global).
- Font-sizes: 12.5, 13.5, 15, 26.
- Radii: 12 (`.record-card`), 8 (input), 999 (submit).
- Accent: none.
- List rendering: `.record-card` as `<Link>` inside `.card-grid`.
- Creation: inline `<form>` permanently rendered above the list, no collapse/toggle.
- Primary button: `.page button[type=submit]` — visually identical to `.btn-primary` (pill, ink, 13px/600) but a separate CSS rule.

### Candidates (`/candidates`)
- Title: `<h1>`, 26px/800.
- Font-sizes: 10, 12.5, 13.5, 26.
- Radii: 8 (inputs/selects), 999 (status-pill, submit), 12 (table row end-caps).
- Accent: none — `.status-pill` here never turns orange (Not started / Completed both render neutral gray).
- List rendering: real `<table>` — a different idiom from Positions' card-grid for the same underlying pattern ("list of records with a create form above").
- Creation: inline `<form>` (5 fields) permanently visible above the table.
- Primary button: `.page button[type=submit]`.

### Candidate detail (`/candidates/:id`)
Most font-size diversity of any page.
- Title: `<h1>`, 26px/800 (candidate name).
- Font-sizes: 10, 11, 12.5, 13.5, 15, 17, 26.
- Radii: 14 (`.panel`), 8 (inputs), 999 (status-pill, submit), 50% (`.stage-progress-dot`).
- Accent: `--health-stalled` on `.stat-value.danger` (stalled Health stat); `.btn-danger` (Delete candidate) is outline-only (text + tinted border, no filled background) — visually lighter-weight than the board's filled `.pipeline-card.health-stalled` treatment of the same semantic color.
- List rendering: three treatments on one page — the `.stage-progress` stepper (bespoke dot/line component), `.history-list li` (shared by Interviews, Stage history, and Scores — three different data types, one row style), and the edit form living in a `.panel` box.
- Primary button: `.page button[type=submit]` for Save/Move; `.btn-danger` (outline) for Delete.
- **Stage stepper data source**: `CandidateDetailPage.tsx` (~line 231) calls `listStages(position_id)` → `GET /api/pipeline/stages?position_id=…` → `backend/app/routers/pipeline.py` `list_stages` (~line 79): `db.query(Stage).filter(Stage.position_id==position_id).order_by(Stage.sequence_order).all()`. No terminal-stage filtering — it renders every `Stage` row in raw `sequence_order`, including Rejected. See §3.4.

### Users (`/users`)
- Title: `<h1>`, 26px/800.
- Font-sizes: 10, 12.5, 13.5, 26.
- Radii: 8 (inputs/select), 999 (buttons, status-pill, `.toggle-track`).
- Accent: `--health-stalled` on `.status-pill.status-inactive` — **the only page where `.status-pill` actually renders orange**, despite Candidates using the identical component/class for its own "incomplete" states without ever tinting it.
- List rendering: real `<table>` (same idiom as Candidates).
- Creation: inline `<form>` permanently visible above the table.
- Row actions: in edit mode, Save and Cancel render as the same `.page button:not([type=submit])` style — no visual distinction between a commit action and an abort action.
- Primary button: `.page button[type=submit]`.

### My Candidates (`/my-candidates`)
- Title: `<h1>`, 26px/800.
- Font-sizes: 10, 12.5, 15, 26.
- Radii: 12 (`.record-card`), 999 (status-pill).
- Accent: none.
- List rendering: `.record-card` as `<Link>` — same component as Positions.
- Creation: no form at all — interviewers can't create candidates. The one list page without a permanent inline form, but by feature absence, not design choice.
- Primary button: n/a.

### Calendar (`/calendar`)
Second-most font-size diversity.
- Title: `<h1>`, 26px/800; the month label inside the grid is an `<h2>`, 17px/700.
- Font-sizes: 10, 11, 12.5, 13, 15, 17, 26.
- Radii: 8 (inputs), 10 (`.page button.calendar-day`), 12 (`.record-card` for the day's interview list), 999 (`.btn-secondary` month-nav, `.calendar-day-count`).
- Accent: `--health-stalled` on `.btn-danger` (Cancel interview) only.
- List rendering: three treatments — the calendar grid's day buttons (bespoke), `.record-card` as a plain `<div>` for the selected day's interviews (unlike Positions/InterviewerQueue's Link-based card), and a nested `.record-card-meta` link inside that.
- Creation: inline admin-only `<form>` permanently visible above the calendar.
- Primary button: `.page button[type=submit]` (Schedule); month prev/next use `.btn-secondary` — a secondary-styled button standing in for the primary way most people will interact with this section of the page.

### Login (`/login`)
Its own isolated `.login-shell`/`.login-card` system, not `.page`.
- Title: `.login-card h1`, 20px/500, letter-spacing -0.01em — every other page's `<h1>` is 22 or 26px/800.
- Font-sizes: 12, 13, 14, 20 — a self-contained scale sharing no exact size with the rest of the app.
- Radii: 16 (card), 10 (input, button, `.app-mark`) — the only page whose submit button isn't a 999px pill.
- Accent: none — focus ring uses `--cta-bg` (ink), not a saturated color.
- Primary button: `.login-card form button` — a third, independent primary-button definition (see §3 below).

## 3. Same concept, styled two ways / two concepts, styled the same way

- **Primary CTA button has three independent CSS definitions**: `.btn-primary` (board), `.page button[type=submit]` (every `.page`-wrapped screen), `.login-card form button` (login). The first two agree visually (pill, ink, 13px/600); login's disagrees (radius 10, not a pill, 14px).
- **"Create new X" lives in two different places**: a same-page permanently-open form (Positions, Candidates, Users, Calendar) vs. a full route navigation (board's "+ Add candidate" → `/candidates`).
- **"List of records" is rendered five different ways** (table / Link-card / div-card / pipeline-card / bordered-`<li>`) with no apparent rule for which pattern applies where — Positions and InterviewerQueue happen to agree; Candidates and Users happen to agree; the board and Calendar's day list are each unique.
- **`.status-pill` means different things on different pages despite being the same component**: on Users it turns orange for `status-inactive`; on Candidates the identical class/component never turns orange for any status, even though "not started" is arguably just as attention-worthy as "deactivated."
- **A secondary-styled button (`.btn-secondary`) carries primary navigational weight** on Calendar (month prev/next) — visually demoted relative to its actual role on that page.
- **Login's type and radius scales are parallel systems**, not reuses of the app-wide ones — nearest-neighbor sizes are off by 0.5px, and its buttons/inputs use a radius (10) and shape (non-pill) that appear nowhere else in the app.
- **Focus indication is inconsistent by omission, not by design**: `.page input/select/textarea` and login inputs get a deliberate custom focus ring (ink border + soft shadow); `.nav-rail-item` gets the raw unstyled browser default (blue) against a black background; `.pipeline-card`, `.record-card`, and `.pipeline-column-collapsed` get no focus styling at all.
- **The one accent color (`--health-stalled`) is overloaded across six unrelated semantic roles** (stalled health, inactive user, generic error banner, destructive-button text/border, error icon, generic "danger" text) — and even within "destructive," the treatment isn't consistent in weight: the board fills `.pipeline-card.health-stalled`'s border solid, while `.btn-danger` (Delete/Cancel) stays outline-only.

## 4. Data integrity findings

All four items you flagged are confirmed real, plus the scan below turned up no additional corrupted rows (referential integrity — orphaned transitions, duplicate sequence orders, out-of-order timestamps, missing transitions — came back clean). Nothing here has been fixed.

### 4.1 Candidates at "Rejected" showing health "on_track" — **derivation bug**
Confirmed, 4 of 21 candidates (ids 14, 15, 1, 32) sit in `Rejected` with `health = "on_track"`.

Root cause — `backend/app/pipeline/derive.py`, `compute_health()`:
```python
def compute_health(days_in_stage: int, day_limit: int | None) -> str:
    if day_limit is not None and days_in_stage > day_limit:
        return "stalled"
    return "on_track"
```
`Rejected` and `Hired` seed with `day_limit = None` (`backend/app/pipeline/stages.py`), so this function always falls through to `"on_track"` for a terminal stage. The very next function in the same file, `compute_next_action()`, *does* special-case `current_stage_name in ("Hired", "Rejected")` — the terminal-stage exclusion exists one function away and was never applied here. Fixable without a schema change; this is purely a gap in derivation logic.

### 4.2 Backwards stage-transition history — **data-model / business-logic gap**
Confirmed, 21 transition rows move to a lower `sequence_order` than they came from, e.g. `Rejected(6) → Hired(5)`, `Under review(3) → Screening(2)`, `Under review(3) → Applied(1)`.

Root cause — `backend/app/routers/pipeline.py`, `move_candidate()`: the only backward-move guard checks whether the *name* of the `from_stage` is in a hardcoded `TERMINAL_STAGE_NAMES` set (leaving Hired or Rejected requires a `force` flag + a frontend `window.confirm`). There is **no comparison of `sequence_order` between the two stages** for any other move — `Under review → Applied` or `Screening → Applied` are both allowed silently. The guard is keyed on "is this stage terminal by name," not "is this move going backwards," which is a narrower check than the model implies.

### 4.3 Board count (7) vs. candidates count (21) — **derivation/display bug, not corrupt data**
Both numbers are individually correct for what they measure: 21 is the total candidate count across all 5 positions; 7 is the board's count for whichever single position it defaults to (position 6, "Product Engineer (Demo)," which happens to be the busiest). `HomePage.tsx`'s `getBoard` call is always scoped to one `position_id`; `/candidates` lists globally. Per-position breakdown: position 6 = 7, position 1 = 4, position 2 = 3, position 3 = 4, position 4 = 3 (sums to 21). The bug is that neither page's header discloses the scope difference — the board header reads "7 candidates" with no position name in that count, so it reads as a global total when it isn't one.

### 4.4 "Rejected" rendered as a linear step after "Hired" — **data-model problem**
Confirmed at the schema level, not just in rendering. `backend/app/pipeline/stages.py`:
```python
DEFAULT_STAGES: list[tuple[str, int | None]] = [
    ("Applied", 3), ("Screening", 5), ("Under review", 5),
    ("Offer", 3), ("Hired", None), ("Rejected", None),
]
```
Seeded via `enumerate(..., start=1)`, so every position gets `Rejected.sequence_order = 6`, one past `Hired.sequence_order = 5` (verified across all 5 positions). Both the stepper (`CandidateDetailPage.tsx`) and the stages API (`list_stages` in `pipeline.py`) just render/return `ORDER BY sequence_order` with no filtering — they're faithfully displaying what the schema encodes. `Stage` has no `is_terminal` (or `is_exit`) flag; the codebase already knows this is missing — both `stages.py` and `HomePage.tsx` carry comments noting `Stage` has no terminal flag yet and fake it with a hardcoded `TERMINAL_STAGE_NAMES` set for other purposes (the force-move confirmation). The ordering itself, not merely a missing flag, is what encodes rejection as happening after being hired.

### 4.5 Other anomalies checked — none found
No candidates with zero stage-transition rows; no transitions referencing a nonexistent candidate or stage; no duplicate `sequence_order` within a position; no position with zero stages; no candidate with `updated_at < created_at`; no interview score referencing a question belonging to a different position than the candidate. Referential integrity is clean everywhere else — every issue above is a logic or schema-design gap, not a corrupted row.

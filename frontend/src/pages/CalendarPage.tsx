import { useEffect, useMemo, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import {
  cancelInterview,
  listAllInterviews,
  listMyInterviews,
  scheduleInterview,
  type Interview,
} from "../api/interviews";
import { listCandidates, type Candidate } from "../api/candidates";

const WEEKDAY_LABELS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

function toDateKey(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function timeRange(iso: string, durationMinutes: number): string {
  const start = new Date(iso);
  const end = new Date(start.getTime() + durationMinutes * 60_000);
  const fmt = (d: Date) => d.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
  return `${fmt(start)} – ${fmt(end)}`;
}

/** Every cell in a standard 6-week month grid, including the padding days
 * from the previous/next month needed to fill out full weeks. */
function buildMonthGrid(monthStart: Date): Date[] {
  const firstWeekday = monthStart.getDay();
  const gridStart = new Date(monthStart);
  gridStart.setDate(gridStart.getDate() - firstWeekday);

  return Array.from({ length: 42 }, (_, i) => {
    const d = new Date(gridStart);
    d.setDate(gridStart.getDate() + i);
    return d;
  });
}

export function CalendarPage() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";

  const [interviews, setInterviews] = useState<Interview[] | null>(null);
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [error, setError] = useState<string | null>(null);

  const today = useMemo(() => new Date(), []);
  const [monthStart, setMonthStart] = useState(() => new Date(today.getFullYear(), today.getMonth(), 1));
  const [selectedDay, setSelectedDay] = useState(() => toDateKey(today));

  const [candidateId, setCandidateId] = useState("");
  const [scheduledAt, setScheduledAt] = useState("");
  const [duration, setDuration] = useState("60");
  const [notes, setNotes] = useState("");
  const [scheduling, setScheduling] = useState(false);

  async function refresh() {
    try {
      const data = isAdmin ? await listAllInterviews() : await listMyInterviews();
      setInterviews(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    }
  }

  useEffect(() => {
    refresh();
    if (isAdmin) {
      listCandidates().then(setCandidates);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isAdmin]);

  async function handleSchedule(e: FormEvent) {
    e.preventDefault();
    const candidate = candidates.find((c) => c.id === Number(candidateId));
    if (!candidate?.open_round_id) {
      setError("This candidate has no open round to schedule against.");
      return;
    }
    setScheduling(true);
    try {
      await scheduleInterview(
        candidate.open_round_id,
        new Date(scheduledAt).toISOString(),
        Number(duration),
        notes,
      );
      setCandidateId("");
      setScheduledAt("");
      setDuration("60");
      setNotes("");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setScheduling(false);
    }
  }

  function handleSelectDay(key: string) {
    setSelectedDay(key);
    if (isAdmin) {
      // Clicking a day is how you say "schedule here" — carry it straight
      // into the form's date, keeping whatever time-of-day was already
      // there (or defaulting to a plausible 9am start) so the two controls
      // don't read as unrelated to each other.
      const time = scheduledAt.includes("T") ? scheduledAt.slice(11) : "09:00";
      setScheduledAt(`${key}T${time}`);
    }
  }

  async function handleCancel(id: number) {
    try {
      await cancelInterview(id);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    }
  }

  if (interviews === null) {
    return (
      <main className="page">
        {error ? <p role="alert">{error}</p> : <p>Loading…</p>}
      </main>
    );
  }

  const byDay = new Map<string, Interview[]>();
  for (const interview of interviews) {
    const key = toDateKey(new Date(interview.scheduled_at));
    const list = byDay.get(key);
    if (list) list.push(interview);
    else byDay.set(key, [interview]);
  }

  const grid = buildMonthGrid(monthStart);
  const monthLabel = monthStart.toLocaleDateString(undefined, { month: "long", year: "numeric" });
  const selectedInterviews = (byDay.get(selectedDay) ?? []).slice().sort((a, b) => a.scheduled_at.localeCompare(b.scheduled_at));

  return (
    <main className="page">
      <div className="page-header">
        <h1>Calendar</h1>
        <span className="page-header-count">
          {interviews.length} scheduled {isAdmin ? "across all interviewers" : "for you"}
        </span>
      </div>
      {error && <p role="alert">{error}</p>}

      {isAdmin && (
        <form onSubmit={handleSchedule}>
          <div className="field">
            <label htmlFor="cal-candidate">Candidate</label>
            <select id="cal-candidate" value={candidateId} onChange={(e) => setCandidateId(e.target.value)} required>
              <option value="" disabled>
                Select a candidate
              </option>
              {candidates.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.full_name}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="cal-when">When</label>
            <input
              id="cal-when"
              type="datetime-local"
              value={scheduledAt}
              onChange={(e) => setScheduledAt(e.target.value)}
              required
            />
          </div>
          <div className="field">
            <label htmlFor="cal-duration">Duration (min)</label>
            <input
              id="cal-duration"
              type="number"
              min={15}
              max={480}
              step={15}
              value={duration}
              onChange={(e) => setDuration(e.target.value)}
              required
            />
          </div>
          <div className="field">
            <label htmlFor="cal-notes">Notes (optional)</label>
            <input id="cal-notes" value={notes} onChange={(e) => setNotes(e.target.value)} />
          </div>
          <p className="field-hint">Tip: click a date on the calendar below to fill in "When" automatically.</p>
          <button type="submit" disabled={scheduling}>
            {scheduling ? "Scheduling…" : "Schedule interview"}
          </button>
        </form>
      )}

      <section>
        <div className="calendar-month-header">
          <button
            className="btn-secondary"
            onClick={() => setMonthStart((m) => new Date(m.getFullYear(), m.getMonth() - 1, 1))}
            aria-label="Previous month"
          >
            ←
          </button>
          <h2>{monthLabel}</h2>
          <button
            className="btn-secondary"
            onClick={() => setMonthStart((m) => new Date(m.getFullYear(), m.getMonth() + 1, 1))}
            aria-label="Next month"
          >
            →
          </button>
        </div>

        <div className="calendar-grid">
          {WEEKDAY_LABELS.map((w) => (
            <div key={w} className="calendar-weekday">
              {w}
            </div>
          ))}
          {grid.map((d) => {
            const key = toDateKey(d);
            const count = byDay.get(key)?.length ?? 0;
            const inMonth = d.getMonth() === monthStart.getMonth();
            const isToday = key === toDateKey(today);
            const isSelected = key === selectedDay;
            return (
              <button
                key={key}
                className={`calendar-day${inMonth ? "" : " calendar-day-outside"}${isSelected ? " calendar-day-selected" : ""}${isToday ? " calendar-day-today" : ""}`}
                onClick={() => handleSelectDay(key)}
              >
                <span className="calendar-day-number">{d.getDate()}</span>
                {count > 0 && <span className="calendar-day-count">{count}</span>}
              </button>
            );
          })}
        </div>
      </section>

      <section>
        <h2>
          {new Date(selectedDay + "T00:00:00").toLocaleDateString(undefined, {
            weekday: "long",
            month: "long",
            day: "numeric",
          })}
        </h2>
        {selectedInterviews.length === 0 ? (
          <p className="detail-meta">Nothing scheduled this day.</p>
        ) : (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Time</th>
                  <th>Candidate</th>
                  {isAdmin && <th>Interviewer</th>}
                  <th>Notes</th>
                  {isAdmin && <th>Actions</th>}
                </tr>
              </thead>
              <tbody>
                {selectedInterviews.map((interview) => (
                  <tr key={interview.id}>
                    <td>{timeRange(interview.scheduled_at, interview.duration_minutes)}</td>
                    <td>
                      <Link to={`/candidates/${interview.candidate_id}`}>
                        {interview.candidate_name} · {interview.position_title}
                      </Link>
                    </td>
                    {isAdmin && <td>{interview.interviewer_name}</td>}
                    <td>{interview.notes}</td>
                    {isAdmin && (
                      <td>
                        <button className="btn-danger" onClick={() => handleCancel(interview.id)}>
                          Cancel
                        </button>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </main>
  );
}

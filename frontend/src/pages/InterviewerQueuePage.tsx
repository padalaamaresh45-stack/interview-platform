import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { listMyCandidates, type InterviewerQueueRow, type InterviewerQueueState } from "../api/interviewer";
import { useAuth } from "../hooks/useAuth";
import { browserTimezone, formatDateTimeInZone } from "../utils/timezone";

const STATE_LABEL: Record<InterviewerQueueState, string> = {
  needs_scheduling: "Needs scheduling",
  scheduled: "Interview scheduled",
  overdue: "Scorecard overdue",
};

function rowCopy(row: InterviewerQueueRow): string {
  if (row.is_closed_unscored) {
    return row.next_stage_name
      ? `Candidate has moved to ${row.next_stage_name} — your feedback is still needed.`
      : "Candidate has moved on to the next stage — your feedback is still needed.";
  }
  switch (row.state) {
    case "needs_scheduling":
      return "Assigned — no interview scheduled yet.";
    case "scheduled":
      return "Interview scheduled — awaiting your scorecard.";
    case "overdue":
      return "Interview completed — your scorecard is overdue.";
  }
}

export function InterviewerQueuePage() {
  const { user } = useAuth();
  // scheduled_at and scorecard_due_at both render in the interviewer's own
  // profile timezone, not wherever their browser currently is — these can
  // diverge while traveling. See ticket #29.
  const timezone = user?.timezone ?? browserTimezone();
  const [rows, setRows] = useState<InterviewerQueueRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listMyCandidates()
      .then(setRows)
      .catch((err) => setError(err instanceof Error ? err.message : "Something went wrong."))
      .finally(() => setLoading(false));
  }, []);

  return (
    <main className="page">
      <div className="page-header">
        <h1>My candidates</h1>
        <span className="page-header-count">{rows.length} assigned to you</span>
      </div>
      {error && <p role="alert">{error}</p>}
      {loading ? (
        <p>Loading…</p>
      ) : rows.length === 0 ? (
        <p className="detail-meta">You have no assigned candidates right now.</p>
      ) : (
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Name</th>
                <th>Stage</th>
                <th>Brief</th>
                <th>Scheduled</th>
                <th>Status</th>
                <th>Scorecard due</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.round_id} data-state={row.state} className={`queue-row queue-row-${row.state}`}>
                  <td>
                    <Link to={`/my-candidates/${row.candidate_id}`}>{row.candidate_full_name}</Link>
                  </td>
                  <td>{row.stage_name}</td>
                  <td>{row.brief ?? "—"}</td>
                  <td>
                    {row.scheduled_at ? formatDateTimeInZone(row.scheduled_at, timezone) : "Not yet scheduled"}
                  </td>
                  <td>
                    <span className={`status-pill status-pill-${row.state}`}>{STATE_LABEL[row.state]}</span>
                    <div className="detail-meta">{rowCopy(row)}</div>
                  </td>
                  <td>
                    {row.scorecard_due_at ? formatDateTimeInZone(row.scorecard_due_at, timezone) : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </main>
  );
}

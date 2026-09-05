import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { listMyCandidates } from "../api/interviewer";
import type { Candidate } from "../api/candidates";

export function InterviewerQueuePage() {
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listMyCandidates()
      .then(setCandidates)
      .catch((err) => setError(err instanceof Error ? err.message : "Something went wrong."))
      .finally(() => setLoading(false));
  }, []);

  return (
    <main className="page">
      <div className="page-header">
        <h1>My candidates</h1>
        <span className="page-header-count">{candidates.length} assigned to you</span>
      </div>
      {error && <p role="alert">{error}</p>}
      {loading ? (
        <p>Loading…</p>
      ) : candidates.length === 0 ? (
        <p className="detail-meta">You have no assigned candidates right now.</p>
      ) : (
        <div className="card-grid">
          {candidates.map((candidate) => (
            <Link key={candidate.id} to={`/my-candidates/${candidate.id}`} className="record-card">
              <span className="record-card-title">{candidate.full_name}</span>
              <span className={`status-pill ${candidate.status === "completed" ? "status-active" : ""}`}>
                {candidate.status === "completed" ? "Scored" : "Awaiting your scorecard"}
              </span>
            </Link>
          ))}
        </div>
      )}
    </main>
  );
}

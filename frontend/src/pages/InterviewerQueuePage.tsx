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
    <main>
      <h1>My candidates</h1>
      {error && <p role="alert">{error}</p>}
      {loading ? (
        <p>Loading…</p>
      ) : candidates.length === 0 ? (
        <p>You have no assigned candidates right now.</p>
      ) : (
        <ul>
          {candidates.map((candidate) => (
            <li key={candidate.id}>
              <Link to={`/my-candidates/${candidate.id}`}>{candidate.full_name}</Link>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}

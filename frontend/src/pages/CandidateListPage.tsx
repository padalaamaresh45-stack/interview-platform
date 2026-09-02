import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { createCandidate, listActiveInterviewers, listCandidates, type Candidate, type Interviewer } from "../api/candidates";
import { listPositions, type Position } from "../api/positions";

export function CandidateListPage() {
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [positions, setPositions] = useState<Position[]>([]);
  const [interviewers, setInterviewers] = useState<Interviewer[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const [newName, setNewName] = useState("");
  const [newEmail, setNewEmail] = useState("");
  const [newPhone, setNewPhone] = useState("");
  const [newPositionId, setNewPositionId] = useState("");
  const [newInterviewerId, setNewInterviewerId] = useState("");
  const [creating, setCreating] = useState(false);

  async function refresh() {
    setLoading(true);
    try {
      const [candidateList, positionList, interviewerList] = await Promise.all([
        listCandidates(),
        listPositions(),
        listActiveInterviewers(),
      ]);
      setCandidates(candidateList);
      setPositions(positionList);
      setInterviewers(interviewerList);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  async function handleCreate(e: FormEvent) {
    e.preventDefault();
    setCreating(true);
    try {
      await createCandidate(newName, Number(newPositionId), Number(newInterviewerId), newEmail, newPhone);
      setNewName("");
      setNewEmail("");
      setNewPhone("");
      setNewPositionId("");
      setNewInterviewerId("");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setCreating(false);
    }
  }

  const positionTitle = (id: number) => positions.find((p) => p.id === id)?.title ?? `#${id}`;
  const interviewerName = (id: number) => interviewers.find((i) => i.id === id)?.full_name ?? `#${id}`;

  return (
    <main>
      <h1>Candidates</h1>
      {error && <p role="alert">{error}</p>}

      <form onSubmit={handleCreate}>
        <label htmlFor="new-candidate-name">Full name</label>
        <input id="new-candidate-name" value={newName} onChange={(e) => setNewName(e.target.value)} required />
        <label htmlFor="new-candidate-email">Email (optional)</label>
        <input id="new-candidate-email" type="email" value={newEmail} onChange={(e) => setNewEmail(e.target.value)} />
        <label htmlFor="new-candidate-phone">Phone (optional)</label>
        <input id="new-candidate-phone" value={newPhone} onChange={(e) => setNewPhone(e.target.value)} />
        <label htmlFor="new-candidate-position">Position</label>
        <select
          id="new-candidate-position"
          value={newPositionId}
          onChange={(e) => setNewPositionId(e.target.value)}
          required
        >
          <option value="" disabled>
            Select a position
          </option>
          {positions.map((position) => (
            <option key={position.id} value={position.id}>
              {position.title} ({position.question_count} questions)
            </option>
          ))}
        </select>
        <label htmlFor="new-candidate-interviewer">Interviewer</label>
        <select
          id="new-candidate-interviewer"
          value={newInterviewerId}
          onChange={(e) => setNewInterviewerId(e.target.value)}
          required
        >
          <option value="" disabled>
            Select an interviewer
          </option>
          {interviewers.map((interviewer) => (
            <option key={interviewer.id} value={interviewer.id}>
              {interviewer.full_name}
            </option>
          ))}
        </select>
        <button type="submit" disabled={creating}>
          {creating ? "Creating…" : "Create candidate"}
        </button>
      </form>

      {loading ? (
        <p>Loading…</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Position</th>
              <th>Interviewer</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {candidates.map((candidate) => (
              <tr key={candidate.id}>
                <td>
                  <Link to={`/candidates/${candidate.id}`}>{candidate.full_name}</Link>
                </td>
                <td>{positionTitle(candidate.position_id)}</td>
                <td>{interviewerName(candidate.interviewer_id)}</td>
                <td>{candidate.status}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </main>
  );
}

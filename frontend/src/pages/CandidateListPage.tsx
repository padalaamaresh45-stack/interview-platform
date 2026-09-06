import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { createCandidate, listActiveInterviewers, listCandidates, type Candidate, type Interviewer } from "../api/candidates";
import { listPositions, type Position } from "../api/positions";
import { listUsers, type AdminUser } from "../api/users";
import { Modal } from "../components/Modal";
import { StatusPill } from "../components/StatusPill";

export function CandidateListPage() {
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [positions, setPositions] = useState<Position[]>([]);
  // Active-only — used for the create-candidate picker, which must exclude
  // deactivated interviewers from new assignments.
  const [interviewers, setInterviewers] = useState<Interviewer[]>([]);
  // Every interviewer, active or not — used only to render a real name instead
  // of "#id" for candidates already assigned to a since-deactivated interviewer.
  const [allInterviewers, setAllInterviewers] = useState<AdminUser[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const [newName, setNewName] = useState("");
  const [newEmail, setNewEmail] = useState("");
  const [newPhone, setNewPhone] = useState("");
  const [newPositionId, setNewPositionId] = useState("");
  const [newInterviewerId, setNewInterviewerId] = useState("");
  const [creating, setCreating] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);

  async function refresh() {
    setLoading(true);
    try {
      const [candidateList, positionList, interviewerList, userList] = await Promise.all([
        listCandidates(),
        listPositions(),
        listActiveInterviewers(),
        listUsers(),
      ]);
      setCandidates(candidateList);
      setPositions(positionList);
      setInterviewers(interviewerList);
      setAllInterviewers(userList.filter((u) => u.role === "interviewer"));
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
      setModalOpen(false);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setCreating(false);
    }
  }

  const positionTitle = (id: number) => positions.find((p) => p.id === id)?.title ?? `#${id}`;
  const interviewerName = (id: number | null) => {
    if (id === null) return "Unassigned";
    const interviewer = allInterviewers.find((i) => i.id === id);
    if (interviewer === undefined) return `#${id}`;
    return interviewer.is_active ? interviewer.full_name : `${interviewer.full_name} (deactivated)`;
  };

  return (
    <main className="page">
      <div className="page-header">
        <h1>Candidates</h1>
        <span className="page-header-count">{candidates.length} total</span>
        <button type="button" className="btn-primary" onClick={() => setModalOpen(true)}>
          + New Candidate
        </button>
      </div>
      {error && <p role="alert">{error}</p>}

      {modalOpen && (
        <Modal title="New candidate" onClose={() => setModalOpen(false)}>
          <form onSubmit={handleCreate}>
            <div className="field">
              <label htmlFor="new-candidate-name">Full name</label>
              <input id="new-candidate-name" value={newName} onChange={(e) => setNewName(e.target.value)} required />
            </div>
            <div className="field">
              <label htmlFor="new-candidate-email">Email (optional)</label>
              <input
                id="new-candidate-email"
                type="email"
                value={newEmail}
                onChange={(e) => setNewEmail(e.target.value)}
              />
            </div>
            <div className="field">
              <label htmlFor="new-candidate-phone">Phone (optional)</label>
              <input id="new-candidate-phone" value={newPhone} onChange={(e) => setNewPhone(e.target.value)} />
            </div>
            <div className="field">
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
            </div>
            <div className="field">
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
            </div>
            <button type="submit" disabled={creating}>
              {creating ? "Creating…" : "Create candidate"}
            </button>
          </form>
        </Modal>
      )}

      {loading ? (
        <p>Loading…</p>
      ) : candidates.length === 0 ? (
        <p>No candidates yet — create one above to get started.</p>
      ) : (
        <div className="table-scroll"><table>
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
                <td>{interviewerName(candidate.owner_id)}</td>
                <td>
                  <StatusPill tone="neutral">
                    {candidate.status === "completed" ? "Completed" : "Not started"}
                  </StatusPill>
                </td>
              </tr>
            ))}
          </tbody>
        </table></div>
      )}
    </main>
  );
}

import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { deleteCandidate, getCandidate, updateCandidate, type Candidate } from "../api/candidates";
import { listPositions, type Position } from "../api/positions";
import { listUsers, type AdminUser } from "../api/users";

export function CandidateDetailPage() {
  const { candidateId } = useParams<{ candidateId: string }>();
  const id = Number(candidateId);
  const navigate = useNavigate();

  const [candidate, setCandidate] = useState<Candidate | null>(null);
  const [positions, setPositions] = useState<Position[]>([]);
  // All interviewers (active and deactivated), not just the active-only picker
  // list — the currently assigned interviewer must always have a real <option>
  // to bind to, even if they've since been deactivated, or the <select> falls
  // back to whatever option happens to be first and a Save with no intended
  // change would silently reassign the candidate to the wrong person.
  const [interviewers, setInterviewers] = useState<AdminUser[]>([]);
  const [error, setError] = useState<string | null>(null);

  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [interviewerId, setInterviewerId] = useState("");

  async function refresh() {
    try {
      const [candidateData, positionList, userList] = await Promise.all([
        getCandidate(id),
        listPositions(),
        listUsers(),
      ]);
      setCandidate(candidateData);
      setPositions(positionList);
      setInterviewers(userList.filter((u) => u.role === "interviewer"));
      setFullName(candidateData.full_name);
      setEmail(candidateData.email ?? "");
      setPhone(candidateData.phone ?? "");
      setInterviewerId(String(candidateData.interviewer_id));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    }
  }

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  async function handleSave(e: FormEvent) {
    e.preventDefault();
    if (candidate === null) return;
    try {
      const updates: Parameters<typeof updateCandidate>[1] = {
        full_name: fullName,
        email: email || null,
        phone: phone || null,
      };
      if (Number(interviewerId) !== candidate.interviewer_id) {
        updates.interviewer_id = Number(interviewerId);
      }
      await updateCandidate(id, updates);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    }
  }

  async function handleDelete() {
    try {
      await deleteCandidate(id);
      navigate("/candidates");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    }
  }

  if (candidate === null) {
    return (
      <main>
        {error ? <p role="alert">{error}</p> : <p>Loading…</p>}
      </main>
    );
  }

  const canChangeAssignment = candidate.status === "not_started";
  const position = positions.find((p) => p.id === candidate.position_id);

  return (
    <main>
      <p>
        <Link to="/candidates">← Back to candidates</Link>
      </p>
      {error && <p role="alert">{error}</p>}

      <h1>{candidate.full_name}</h1>
      <p>
        Position: {position?.title ?? `#${candidate.position_id}`} — Status: {candidate.status}
      </p>

      <form onSubmit={handleSave}>
        <label htmlFor="candidate-full-name">Full name</label>
        <input id="candidate-full-name" value={fullName} onChange={(e) => setFullName(e.target.value)} required />
        <label htmlFor="candidate-email">Email</label>
        <input id="candidate-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
        <label htmlFor="candidate-phone">Phone</label>
        <input id="candidate-phone" value={phone} onChange={(e) => setPhone(e.target.value)} />
        <label htmlFor="candidate-interviewer">Interviewer</label>
        <select
          id="candidate-interviewer"
          value={interviewerId}
          onChange={(e) => setInterviewerId(e.target.value)}
          disabled={!canChangeAssignment}
        >
          {interviewers.map((interviewer) => (
            <option
              key={interviewer.id}
              value={interviewer.id}
              disabled={!interviewer.is_active && interviewer.id !== candidate.interviewer_id}
            >
              {interviewer.full_name}
              {!interviewer.is_active && " (deactivated)"}
            </option>
          ))}
        </select>
        {!canChangeAssignment && <p>Interviewer can only be reassigned while the candidate is not started.</p>}
        <button type="submit">Save</button>
      </form>

      {canChangeAssignment ? (
        <button onClick={handleDelete}>Delete candidate</button>
      ) : (
        <p>A completed candidate cannot be deleted.</p>
      )}
    </main>
  );
}

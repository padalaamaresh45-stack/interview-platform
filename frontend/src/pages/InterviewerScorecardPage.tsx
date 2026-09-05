import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { getMyCandidate, submitScores, type CandidateDetail } from "../api/interviewer";

interface DraftEntry {
  score: string;
  comment: string;
}

type Draft = Record<number, DraftEntry>;

function draftKey(candidateId: number) {
  return `interview-draft-${candidateId}`;
}

function loadDraft(candidateId: number): Draft {
  try {
    const raw = window.localStorage.getItem(draftKey(candidateId));
    return raw ? (JSON.parse(raw) as Draft) : {};
  } catch {
    return {};
  }
}

function saveDraft(candidateId: number, draft: Draft) {
  try {
    window.localStorage.setItem(draftKey(candidateId), JSON.stringify(draft));
  } catch {
    // localStorage unavailable — draft autosave is a convenience, not a hard requirement.
  }
}

function clearDraft(candidateId: number) {
  try {
    window.localStorage.removeItem(draftKey(candidateId));
  } catch {
    // ignore
  }
}

export function InterviewerScorecardPage() {
  const { candidateId } = useParams<{ candidateId: string }>();
  const id = Number(candidateId);
  const navigate = useNavigate();

  const [candidate, setCandidate] = useState<CandidateDetail | null>(null);
  const [draft, setDraft] = useState<Draft>({});
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    getMyCandidate(id)
      .then((data) => {
        setCandidate(data);
        if (data.status === "not_started") {
          setDraft(loadDraft(id));
        }
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Something went wrong."));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  function updateField(questionId: number, field: keyof DraftEntry, value: string) {
    setDraft((prev) => {
      const next = { ...prev, [questionId]: { ...prev[questionId], [field]: value } };
      saveDraft(id, next);
      return next;
    });
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (candidate === null) return;
    setError(null);
    setSubmitting(true);
    try {
      const scores = candidate.questions.map((q) => ({
        question_id: q.id,
        score: Number(draft[q.id]?.score ?? 0),
        comment: draft[q.id]?.comment || null,
      }));
      await submitScores(id, scores);
      clearDraft(id);
      navigate("/my-candidates");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setSubmitting(false);
    }
  }

  if (candidate === null) {
    return (
      <main className="page">
        {error ? <p role="alert">{error}</p> : <p>Loading…</p>}
      </main>
    );
  }

  if (candidate.status === "completed") {
    return (
      <main className="page">
        <p>
          <Link to="/my-candidates">← Back to my candidates</Link>
        </p>
        <h1>{candidate.full_name}</h1>
        <p>This candidate has already been scored. Scores are final and cannot be edited.</p>
        <ol>
          {candidate.questions.map((q) => {
            const existing = candidate.scores.find((s) => s.question_id === q.id);
            return (
              <li key={q.id}>
                {q.question_text} — score: {existing?.score ?? "—"}
                {existing?.comment && <p>{existing.comment}</p>}
              </li>
            );
          })}
        </ol>
      </main>
    );
  }

  const allScored = candidate.questions.every((q) => {
    const value = Number(draft[q.id]?.score ?? 0);
    return value >= 1 && value <= 5;
  });

  return (
    <main className="page">
      <p>
        <Link to="/my-candidates">← Back to my candidates</Link>
      </p>
      {error && <p role="alert">{error}</p>}
      <h1>{candidate.full_name}</h1>

      <form onSubmit={handleSubmit}>
        <ol>
          {candidate.questions.map((q) => (
            <li key={q.id}>
              <p>{q.question_text}</p>
              <div className="field">
                <label htmlFor={`score-${q.id}`}>Score (1-5)</label>
                <input
                  id={`score-${q.id}`}
                  type="number"
                  min={1}
                  max={5}
                  value={draft[q.id]?.score ?? ""}
                  onChange={(e) => updateField(q.id, "score", e.target.value)}
                  required
                />
              </div>
              <div className="field">
                <label htmlFor={`comment-${q.id}`}>Comment (optional)</label>
                <textarea
                  id={`comment-${q.id}`}
                  value={draft[q.id]?.comment ?? ""}
                  onChange={(e) => updateField(q.id, "comment", e.target.value)}
                />
              </div>
            </li>
          ))}
        </ol>
        <button type="submit" disabled={submitting || !allScored}>
          {submitting ? "Submitting…" : "Submit scores"}
        </button>
      </form>
    </main>
  );
}

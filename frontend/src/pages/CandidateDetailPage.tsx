import { Fragment, useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  deleteCandidate,
  getCandidate,
  holdCandidate,
  reassignRound,
  updateCandidate,
  type Candidate,
} from "../api/candidates";
import { listPositions, type Position } from "../api/positions";
import { listUsers, type AdminUser } from "../api/users";
import {
  getCandidateHistory,
  getConsolidation,
  listStages,
  moveCandidate,
  TerminalStageMoveError,
  type CandidateHistory,
  type Consolidation,
  type Stage,
} from "../api/pipeline";
import { listAllInterviews, type Interview } from "../api/interviews";

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

  // The pipeline history (stage moves, scores) is a separate concern from the
  // edit form above — it loads and fails independently so a pipeline-service
  // hiccup never blocks editing the candidate's own fields.
  const [history, setHistory] = useState<CandidateHistory | null>(null);
  const [stages, setStages] = useState<Stage[]>([]);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [moveTargetStageId, setMoveTargetStageId] = useState("");

  // The consolidation view (every round, in order, with the shared
  // variance/split-decision calculation) is admin-only and separate from the
  // single-round-per-interviewer scorecard flow — fetched independently so a
  // hiccup here doesn't block the rest of the page either.
  const [consolidation, setConsolidation] = useState<Consolidation | null>(null);
  const [consolidationError, setConsolidationError] = useState<string | null>(null);

  // Scheduled interviews for this candidate — a separate, independently-
  // failing fetch for the same reason history is: a calendar hiccup
  // shouldn't block the rest of the profile from rendering.
  const [interviews, setInterviews] = useState<Interview[] | null>(null);

  const [reassignTargetId, setReassignTargetId] = useState("");
  const [reassignError, setReassignError] = useState<string | null>(null);

  const [holdReason, setHoldReason] = useState("");
  const [holdReviewBy, setHoldReviewBy] = useState("");
  const [holdInterviewAction, setHoldInterviewAction] = useState<"keep" | "cancel" | "">("");
  const [holdError, setHoldError] = useState<string | null>(null);

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
      setReassignTargetId(candidateData.owner_id ? String(candidateData.owner_id) : "");
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    }
  }

  async function refreshHistory() {
    try {
      const historyData = await getCandidateHistory(id);
      setHistory(historyData);
      const stageList = await listStages(historyData.position_id);
      setStages(stageList);
      setMoveTargetStageId(String(historyData.current_stage_id));
      setHistoryError(null);
    } catch (err) {
      setHistoryError(err instanceof Error ? err.message : "Could not load pipeline history.");
    }
  }

  async function refreshInterviews() {
    try {
      const all = await listAllInterviews();
      setInterviews(all.filter((i) => i.candidate_id === id));
    } catch {
      setInterviews([]);
    }
  }

  useEffect(() => {
    refresh();
    refreshHistory();
    refreshInterviews();
    getConsolidation(id)
      .then((data) => {
        setConsolidation(data);
        setConsolidationError(null);
      })
      .catch((err) => setConsolidationError(err instanceof Error ? err.message : "Could not load round history."));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  async function handleMove(e: FormEvent) {
    e.preventDefault();
    if (history === null) return;
    const toStageId = Number(moveTargetStageId);
    if (toStageId === history.current_stage_id) return;
    try {
      await moveCandidate(id, toStageId);
      await refreshHistory();
    } catch (err) {
      if (err instanceof TerminalStageMoveError) {
        if (window.confirm(`${err.message} Move anyway?`)) {
          try {
            await moveCandidate(id, toStageId, true);
            await refreshHistory();
          } catch (err2) {
            setHistoryError(err2 instanceof Error ? err2.message : "Something went wrong.");
          }
        }
        return;
      }
      setHistoryError(err instanceof Error ? err.message : "Something went wrong.");
    }
  }

  async function handleSave(e: FormEvent) {
    e.preventDefault();
    if (candidate === null) return;
    try {
      const updates: Parameters<typeof updateCandidate>[1] = {
        full_name: fullName,
        email: email || null,
        phone: phone || null,
      };
      await updateCandidate(id, updates);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    }
  }

  async function handleReassign(e: FormEvent) {
    e.preventDefault();
    if (candidate === null || !reassignTargetId) return;
    try {
      await reassignRound(id, Number(reassignTargetId));
      setReassignError(null);
      await refresh();
    } catch (err) {
      setReassignError(err instanceof Error ? err.message : "Something went wrong.");
    }
  }

  async function handleHold(e: FormEvent) {
    e.preventDefault();
    if (candidate === null) return;
    try {
      await holdCandidate(id, {
        reason: holdReason,
        review_by: holdReviewBy || null,
        interview_action: holdInterviewAction || undefined,
      });
      setHoldError(null);
      setHoldReason("");
      setHoldReviewBy("");
      setHoldInterviewAction("");
      await refresh();
      await refreshHistory();
      await refreshInterviews();
    } catch (err) {
      setHoldError(err instanceof Error ? err.message : "Something went wrong.");
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
      <main className="page">
        {error ? <p role="alert">{error}</p> : <p>Loading…</p>}
      </main>
    );
  }

  const canChangeAssignment = candidate.status === "not_started";
  const position = positions.find((p) => p.id === candidate.position_id);
  const hasScheduledInterview =
    candidate.open_round_id !== null &&
    (interviews ?? []).some((iv) => iv.round_id === candidate.open_round_id);

  return (
    <main className="page">
      <section className="detail-header">
        <p>
          <Link to="/candidates">← Back to candidates</Link>
        </p>
        {error && <p role="alert">{error}</p>}
        <h1>{candidate.full_name}</h1>
        <p className="detail-meta">
          {position?.title ?? `#${candidate.position_id}`} ·{" "}
          <span className={`status-pill ${candidate.status === "completed" ? "status-active" : ""}`}>
            {candidate.status === "completed" ? "Completed" : "Not started"}
          </span>
        </p>
      </section>

      <section>
        <h2>Details</h2>
        <div className="panel">
          <form onSubmit={handleSave}>
            <div className="field">
              <label htmlFor="candidate-full-name">Full name</label>
              <input id="candidate-full-name" value={fullName} onChange={(e) => setFullName(e.target.value)} required />
            </div>
            <div className="field">
              <label htmlFor="candidate-email">Email</label>
              <input id="candidate-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
            </div>
            <div className="field">
              <label htmlFor="candidate-phone">Phone</label>
              <input id="candidate-phone" value={phone} onChange={(e) => setPhone(e.target.value)} />
            </div>
            <div className="field">
              <label>Interviewer</label>
              <p className="detail-meta">
                {interviewers.find((iv) => iv.id === candidate.owner_id)?.full_name ??
                  (candidate.owner_id ? `#${candidate.owner_id}` : "Unassigned")}
              </p>
            </div>
            <button type="submit">Save</button>
          </form>
          {candidate.open_round_id !== null ? (
            <form onSubmit={handleReassign}>
              <div className="field">
                <label htmlFor="reassign-interviewer">Reassign interviewer</label>
                <select
                  id="reassign-interviewer"
                  value={reassignTargetId}
                  onChange={(e) => setReassignTargetId(e.target.value)}
                >
                  {interviewers.map((iv) => (
                    <option key={iv.id} value={iv.id}>
                      {iv.full_name}
                    </option>
                  ))}
                </select>
              </div>
              <button type="submit" disabled={Number(reassignTargetId) === candidate.owner_id}>
                Reassign
              </button>
            </form>
          ) : (
            <p className="detail-meta">No open round to reassign.</p>
          )}
          {reassignError && <p role="alert">{reassignError}</p>}

          <div className="panel-danger-zone">
            {canChangeAssignment ? (
              <button className="btn-danger" onClick={handleDelete}>
                Delete candidate
              </button>
            ) : (
              <p className="detail-meta">A completed candidate cannot be deleted.</p>
            )}
          </div>
        </div>
      </section>

      <section>
        <h2>Hold</h2>
        <div className="panel">
          {candidate.hold_reason ? (
            <p className="detail-meta">
              On hold: {candidate.hold_reason}
              {candidate.hold_review_by && ` (review by ${candidate.hold_review_by})`}
            </p>
          ) : (
            <form onSubmit={handleHold}>
              <div className="field">
                <label htmlFor="hold-reason">Reason</label>
                <input
                  id="hold-reason"
                  value={holdReason}
                  onChange={(e) => setHoldReason(e.target.value)}
                  required
                />
              </div>
              <div className="field">
                <label htmlFor="hold-review-by">Review by</label>
                <input
                  id="hold-review-by"
                  type="date"
                  value={holdReviewBy}
                  onChange={(e) => setHoldReviewBy(e.target.value)}
                />
              </div>
              {hasScheduledInterview && (
                <div className="field">
                  <label>Scheduled interview</label>
                  <label>
                    <input
                      type="radio"
                      name="hold-interview-action"
                      value="keep"
                      checked={holdInterviewAction === "keep"}
                      onChange={() => setHoldInterviewAction("keep")}
                    />{" "}
                    Keep it
                  </label>
                  <label>
                    <input
                      type="radio"
                      name="hold-interview-action"
                      value="cancel"
                      checked={holdInterviewAction === "cancel"}
                      onChange={() => setHoldInterviewAction("cancel")}
                    />{" "}
                    Cancel it
                  </label>
                </div>
              )}
              <button type="submit" disabled={hasScheduledInterview && !holdInterviewAction}>
                Place on hold
              </button>
            </form>
          )}
          {holdError && <p role="alert">{holdError}</p>}
        </div>
      </section>

      <section>
        <h2>Pipeline</h2>
        {historyError && <p role="alert">{historyError}</p>}
        {history === null ? (
          !historyError && <p className="detail-meta">Loading pipeline history…</p>
        ) : (
          <div className="panel">
            <div className="stage-progress">
              {stages
                .filter((stage) => !stage.is_terminal)
                .map((stage, i, nonTerminalStages) => {
                  const currentIndex = nonTerminalStages.findIndex((s) => s.id === history.current_stage_id);
                  const status = i < currentIndex ? "done" : i === currentIndex ? "current" : "";
                  return (
                    <Fragment key={stage.id}>
                      {i > 0 && <div className={`stage-progress-line ${i <= currentIndex ? "done" : ""}`} />}
                      <div className={`stage-progress-step ${status}`}>
                        <span className="stage-progress-dot" />
                        <span className="stage-progress-label">{stage.name}</span>
                      </div>
                    </Fragment>
                  );
                })}
            </div>

            <div className="stat-row">
              <div className="stat">
                <span className="stat-label">Stage</span>
                <span className="stat-value">{history.current_stage_name}</span>
              </div>
              <div className="stat">
                <span className="stat-label">Days in stage</span>
                <span className="stat-value">{history.days_in_stage}</span>
              </div>
              {history.health && (
                <div className="stat">
                  <span className="stat-label">Health</span>
                  <span className={`stat-value ${history.health === "stalled" ? "danger" : ""}`}>
                    {history.health === "stalled" ? "Stalled" : "On track"}
                  </span>
                </div>
              )}
              <div className="stat">
                <span className="stat-label">Next action</span>
                <span className="stat-value">{history.next_action}</span>
              </div>
              <div className="stat">
                <span className="stat-label">Score</span>
                <span className="stat-value">
                  {history.score.average !== null
                    ? `${history.score.average} avg`
                    : "—"}{" "}
                  <span className="muted">
                    ({history.score.submitted_count}/{history.score.total_count})
                  </span>
                </span>
              </div>
            </div>

            <form onSubmit={handleMove}>
              <div className="field">
                <label htmlFor="move-stage">Move to stage</label>
                <select
                  id="move-stage"
                  value={moveTargetStageId}
                  onChange={(e) => setMoveTargetStageId(e.target.value)}
                >
                  {stages.map((stage) => (
                    <option key={stage.id} value={stage.id}>
                      {stage.name}
                    </option>
                  ))}
                </select>
              </div>
              <button type="submit">Move</button>
            </form>
          </div>
        )}
      </section>

      {interviews && (
        <section>
          <h2>Interviews</h2>
          {interviews.length === 0 ? (
            <p className="detail-meta">No interviews scheduled yet.</p>
          ) : (
            <ul className="history-list interview-history-list">
              {interviews.map((iv) => (
                <li key={iv.id}>
                  {new Date(iv.scheduled_at).toLocaleString(undefined, {
                    weekday: "short",
                    month: "short",
                    day: "numeric",
                    hour: "numeric",
                    minute: "2-digit",
                  })}{" "}
                  ({iv.duration_minutes} min) with {iv.interviewer_name}
                  {iv.notes && (
                    <>
                      <br />
                      <span className="history-when">{iv.notes}</span>
                    </>
                  )}
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      {history && (
        <section>
          <h2>Stage history</h2>
          <ul className="history-list stage-history-list">
            {history.stage_history.map((t) => (
              <li key={t.id}>
                {t.from_stage_name ? `${t.from_stage_name} → ${t.to_stage_name}` : `Entered ${t.to_stage_name}`} by{" "}
                {t.actor_name}
                <br />
                <span className="history-when">{new Date(t.created_at).toLocaleString()}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section>
        <h2>Rounds</h2>
        {consolidationError && <p role="alert">{consolidationError}</p>}
        {consolidation === null ? (
          !consolidationError && <p className="detail-meta">Loading rounds…</p>
        ) : consolidation.rounds.length === 0 ? (
          <p className="detail-meta">No rounds yet.</p>
        ) : (
          <div className="panel">
            <div className="stat-row">
              <div className="stat">
                <span className="stat-label">Average across scored rounds</span>
                <span className="stat-value">
                  {consolidation.average_score !== null ? consolidation.average_score : "—"}
                </span>
              </div>
              <div className="stat">
                <span className="stat-label">Variance</span>
                <span className="stat-value">
                  {consolidation.variance !== null ? consolidation.variance : "—"}
                  {consolidation.split_decision && <span className="status-pill danger"> Split decision</span>}
                </span>
              </div>
            </div>
            <ul className="history-list round-consolidation-list">
              {consolidation.rounds.map((r) => (
                <li key={r.id}>
                  <strong>{r.stage_name}</strong> — {r.assignee_name} ·{" "}
                  <span className="muted">{r.status.replace("_", " ")}</span>
                  <br />
                  <span className="history-when">
                    {new Date(r.created_at).toLocaleDateString()}
                    {r.closed_at ? ` – ${new Date(r.closed_at).toLocaleDateString()}` : ""}
                  </span>
                  {" · "}
                  {r.average_score !== null ? `${r.average_score} avg` : "no score"}
                  {r.scores.length > 0 && (
                    <ul className="history-list score-history-list">
                      {r.scores.map((s) => (
                        <li key={s.id}>
                          Question #{s.question_id}: {s.score}/5{s.comment ? ` — ${s.comment}` : ""}
                        </li>
                      ))}
                    </ul>
                  )}
                </li>
              ))}
            </ul>
          </div>
        )}
      </section>
    </main>
  );
}

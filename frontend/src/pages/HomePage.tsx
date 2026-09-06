import { useEffect, useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import { getBoard, moveCandidate, TerminalStageMoveError, type Board, type BoardCandidate } from "../api/pipeline";
import { listPositions, type Position } from "../api/positions";

export function HomePage() {
  const { user } = useAuth();

  if (user?.role === "interviewer") {
    return <Navigate to="/my-candidates" replace />;
  }

  return <PipelineBoard />;
}

function initials(fullName: string): string {
  const parts = fullName.trim().split(/\s+/);
  const first = parts[0]?.[0] ?? "";
  const last = parts.length > 1 ? parts[parts.length - 1][0] : "";
  return (first + last).toUpperCase();
}

// A candidate never leaves a terminal stage (Hired/Rejected), so those columns
// only ever grow — left full-height by default they'd eventually dwarf the
// in-flight stages that actually need daily attention. Collapsed to a count
// chip by default; click to expand. Driven by stage.is_terminal from the API,
// not a hardcoded name set.

function PipelineBoard() {
  const navigate = useNavigate();
  const [board, setBoard] = useState<Board | null>(null);
  const [positions, setPositions] = useState<Position[]>([]);
  // Empty string = "not yet chosen a default". Each Position owns its own Stage
  // rows (stages are per-position, not shared) — there is deliberately no "all
  // positions" option: with N positions each contributing their own Applied/
  // Screening/... columns, that view is N unrelated boards concatenated, not
  // one merged pipeline, and reads as broken (every column shows 0 while the
  // header count is correct). One pipeline at a time, like a real recruiter's
  // view — default to the first real position as soon as the list loads.
  const [positionFilter, setPositionFilter] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [draggingId, setDraggingId] = useState<number | null>(null);
  // Explicit expand/collapse per stage id, seeded from each stage's
  // is_terminal flag the first time each board loads (see expandedStages initialization
  // below) — once a user expands a terminal column it stays expanded for
  // the rest of the session, it doesn't re-collapse on the next refresh.
  const [expandedStages, setExpandedStages] = useState<Record<number, boolean>>({});

  async function refresh(positionId: number) {
    try {
      const data = await getBoard(positionId);
      setBoard(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    }
  }

  // Bootstrap: there is no board to fetch until we know which position to
  // scope it to, so this only ever lists positions and picks a default — it
  // never calls getBoard(undefined) for an "all positions" view that the UI
  // no longer offers. Defaults to the position with the most candidates
  // (falling back to the first) so a fresh login never lands on an empty
  // scaffold position with nothing to show.
  useEffect(() => {
    listPositions()
      .then((positionList) => {
        setPositions(positionList);
        if (positionList.length > 0) {
          const busiest = positionList.reduce((best, p) =>
            p.candidate_count > best.candidate_count ? p : best,
          );
          setPositionFilter(String(busiest.id));
        }
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Something went wrong."));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (positionFilter === "") return;
    refresh(Number(positionFilter));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [positionFilter]);

  async function handleDrop(candidateId: number, toStageId: number) {
    if (board === null) return;
    const previousBoard = board;

    // Optimistic move: relocate the card in local state immediately, then fire
    // the mutation. On failure, roll back to the snapshot taken before the move
    // and surface the error — never leave the board showing a move that didn't
    // actually persist.
    const nextColumns = board.columns.map((column) => ({
      ...column,
      candidates: column.candidates.filter((c) => c.id !== candidateId),
    }));
    let movedCandidate: BoardCandidate | undefined;
    for (const column of board.columns) {
      const found = column.candidates.find((c) => c.id === candidateId);
      if (found) movedCandidate = found;
    }
    const targetColumn = nextColumns.find((c) => c.stage.id === toStageId);
    if (movedCandidate && targetColumn) {
      targetColumn.candidates = [...targetColumn.candidates, { ...movedCandidate, current_stage_id: toStageId }];
    }
    setBoard({ columns: nextColumns });
    setError(null);

    try {
      await moveCandidate(candidateId, toStageId);
      await refresh(Number(positionFilter));
    } catch (err) {
      if (err instanceof TerminalStageMoveError) {
        if (window.confirm(`${err.message} Move anyway?`)) {
          try {
            await moveCandidate(candidateId, toStageId, true);
            await refresh(Number(positionFilter));
            return;
          } catch (err2) {
            setBoard(previousBoard);
            setError(err2 instanceof Error ? err2.message : "Something went wrong.");
            return;
          }
        }
        setBoard(previousBoard);
        return;
      }
      setBoard(previousBoard);
      setError(err instanceof Error ? err.message : "Something went wrong.");
    }
  }

  if (board === null) {
    return (
      <main>
        {error ? <p role="alert">{error}</p> : <p>Loading…</p>}
      </main>
    );
  }

  const totalCandidates = board.columns.reduce((sum, c) => sum + c.candidates.length, 0);
  const stalledCount = board.columns.reduce(
    (sum, c) => sum + c.candidates.filter((cand) => cand.health === "stalled").length,
    0,
  );

  return (
    <main>
      <div className="board-header">
        <h1>Candidate pipeline</h1>
        <span className="muted">
          {totalCandidates} candidates · {stalledCount} stalled
        </span>
      </div>

      <div className="board-toolbar">
        <select
          className="btn-secondary"
          value={positionFilter}
          onChange={(e) => setPositionFilter(e.target.value)}
          aria-label="Filter by position"
        >
          {positions.map((p) => (
            <option key={p.id} value={p.id}>
              {p.title}
            </option>
          ))}
        </select>
        <div className="board-toolbar-spacer" />
        <button className="btn-primary" onClick={() => navigate("/candidates")}>
          + Add candidate
        </button>
      </div>

      {error && <p role="alert">{error}</p>}

      <div className="pipeline-board">
        {board.columns.map((column) => {
          const avgDays = column.candidates.length
            ? Math.round(
                column.candidates.reduce((sum, c) => sum + c.days_in_stage, 0) / column.candidates.length,
              )
            : null;
          const isTerminal = column.stage.is_terminal;
          const isExpanded = expandedStages[column.stage.id] ?? !isTerminal;

          if (isTerminal && !isExpanded) {
            return (
              <button
                key={column.stage.id}
                className="pipeline-column pipeline-column-collapsed"
                onClick={() => setExpandedStages((prev) => ({ ...prev, [column.stage.id]: true }))}
              >
                <span>{column.stage.name}</span>
                <span className="muted">{column.candidates.length}</span>
              </button>
            );
          }

          return (
            <div
              key={column.stage.id}
              className="pipeline-column"
              onDragOver={(e) => e.preventDefault()}
              onDrop={(e) => {
                e.preventDefault();
                if (draggingId !== null) {
                  handleDrop(draggingId, column.stage.id);
                  setDraggingId(null);
                }
              }}
            >
              <div className="pipeline-column-header">
                <span>
                  {column.stage.name}
                  {isTerminal && (
                    <button
                      className="pipeline-column-collapse-toggle"
                      onClick={() => setExpandedStages((prev) => ({ ...prev, [column.stage.id]: false }))}
                      aria-label={`Collapse ${column.stage.name}`}
                      title="Collapse"
                    >
                      ×
                    </button>
                  )}
                </span>
                <span className="muted">
                  {column.candidates.length}
                  {avgDays !== null ? ` · avg ${avgDays}d` : ""}
                </span>
              </div>

              {column.candidates.length === 0 ? (
                <div className="pipeline-column-empty">Nobody here.</div>
              ) : (
                column.candidates.map((candidate) => (
                  <div
                    key={candidate.id}
                    className={`pipeline-card${candidate.health ? ` health-${candidate.health}` : ""}`}
                    draggable
                    onDragStart={() => setDraggingId(candidate.id)}
                    onClick={() => navigate(`/candidates/${candidate.id}`)}
                    role="button"
                    tabIndex={0}
                  >
                    <div className="pipeline-card-top">
                      <span className="pipeline-card-avatar">{initials(candidate.full_name)}</span>
                      {candidate.health && (
                        <span className={`health-pill ${candidate.health}`}>
                          {candidate.health === "stalled" ? "Stalled" : "On track"}
                        </span>
                      )}
                      <span className={`pipeline-card-days ${candidate.health === "stalled" ? "danger" : "muted"}`}>
                        {candidate.days_in_stage}d
                      </span>
                    </div>
                    <div className="pipeline-card-name">{candidate.full_name}</div>
                    <div className="muted">{candidate.position_title}</div>
                    <div className={`pipeline-card-next-action ${candidate.health === "stalled" ? "danger" : ""}`}>
                      <span>→</span>
                      <span>{candidate.next_action}</span>
                    </div>
                    <div className="muted">
                      Score: {candidate.score.average !== null ? candidate.score.average : "—"} (
                      {candidate.score.submitted_count}/{candidate.score.total_count})
                    </div>
                  </div>
                ))
              )}
            </div>
          );
        })}
      </div>
    </main>
  );
}

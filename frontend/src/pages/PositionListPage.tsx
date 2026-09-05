import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { createPosition, listPositions, type Position } from "../api/positions";

export function PositionListPage() {
  const [positions, setPositions] = useState<Position[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [newTitle, setNewTitle] = useState("");
  const [creating, setCreating] = useState(false);

  async function refresh() {
    setLoading(true);
    try {
      setPositions(await listPositions());
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
      await createPosition(newTitle);
      setNewTitle("");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setCreating(false);
    }
  }

  return (
    <main className="page">
      <div className="page-header">
        <h1>Positions</h1>
        <span className="page-header-count">{positions.length} total</span>
      </div>
      {error && <p role="alert">{error}</p>}

      <form onSubmit={handleCreate}>
        <div className="field">
          <label htmlFor="new-position-title">New position title</label>
          <input
            id="new-position-title"
            value={newTitle}
            onChange={(e) => setNewTitle(e.target.value)}
            required
          />
        </div>
        <button type="submit" disabled={creating}>
          {creating ? "Creating…" : "Create position"}
        </button>
      </form>

      {loading ? (
        <p>Loading…</p>
      ) : positions.length === 0 ? (
        <p>No positions yet — create one above to get started.</p>
      ) : (
        <div className="card-grid">
          {positions.map((position) => (
            <Link key={position.id} to={`/positions/${position.id}`} className="record-card">
              <span className="record-card-title">{position.title}</span>
              <span className="record-card-meta">
                {position.question_count} question{position.question_count === 1 ? "" : "s"}
              </span>
            </Link>
          ))}
        </div>
      )}
    </main>
  );
}

import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { createPosition, listPositions, type Position } from "../api/positions";
import { Modal } from "../components/Modal";

export function PositionListPage() {
  const [positions, setPositions] = useState<Position[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [newTitle, setNewTitle] = useState("");
  const [creating, setCreating] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);

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
      setModalOpen(false);
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
        <button type="button" className="btn-primary" onClick={() => setModalOpen(true)}>
          + New Position
        </button>
      </div>
      {error && <p role="alert">{error}</p>}

      {modalOpen && (
        <Modal title="New position" onClose={() => setModalOpen(false)}>
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
        </Modal>
      )}

      {loading ? (
        <p>Loading…</p>
      ) : positions.length === 0 ? (
        <p>No positions yet — create one above to get started.</p>
      ) : (
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Title</th>
                <th>Questions</th>
              </tr>
            </thead>
            <tbody>
              {positions.map((position) => (
                <tr key={position.id}>
                  <td>
                    <Link to={`/positions/${position.id}`}>{position.title}</Link>
                  </td>
                  <td>
                    {position.question_count} question{position.question_count === 1 ? "" : "s"}
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

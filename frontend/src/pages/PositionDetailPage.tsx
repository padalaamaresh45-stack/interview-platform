import { useEffect, useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";
import {
  createQuestion,
  deleteQuestion,
  getPosition,
  listQuestions,
  updatePosition,
  updateQuestion,
  type Position,
  type Question,
} from "../api/positions";

export function PositionDetailPage() {
  const { positionId } = useParams<{ positionId: string }>();
  const id = Number(positionId);

  const [position, setPosition] = useState<Position | null>(null);
  const [questions, setQuestions] = useState<Question[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [titleDraft, setTitleDraft] = useState("");
  const [editingTitle, setEditingTitle] = useState(false);

  const [newQuestionText, setNewQuestionText] = useState("");
  const [newQuestionOrder, setNewQuestionOrder] = useState("");
  const [editingQuestionId, setEditingQuestionId] = useState<number | null>(null);
  const [editingQuestionText, setEditingQuestionText] = useState("");

  function nextSequenceOrder(questionList: Question[]): number {
    return questionList.length === 0 ? 1 : Math.max(...questionList.map((q) => q.sequence_order)) + 1;
  }

  async function refresh() {
    try {
      const [found, questionList] = await Promise.all([getPosition(id), listQuestions(id)]);
      setPosition(found ?? null);
      setTitleDraft(found?.title ?? "");
      setQuestions(questionList);
      setNewQuestionOrder(String(nextSequenceOrder(questionList)));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    }
  }

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  async function handleTitleSave(e: FormEvent) {
    e.preventDefault();
    try {
      await updatePosition(id, titleDraft);
      setEditingTitle(false);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    }
  }

  async function handleAddQuestion(e: FormEvent) {
    e.preventDefault();
    try {
      await createQuestion(id, newQuestionText, Number(newQuestionOrder));
      setNewQuestionText("");
      await refresh(); // also resets newQuestionOrder to the next suggested value
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    }
  }

  async function handleSaveQuestion(questionId: number) {
    try {
      await updateQuestion(questionId, editingQuestionText);
      setEditingQuestionId(null);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    }
  }

  async function handleDeleteQuestion(questionId: number) {
    try {
      await deleteQuestion(questionId);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    }
  }

  if (position === null) {
    return (
      <main className="page">
        {error ? <p role="alert">{error}</p> : <p>Loading…</p>}
      </main>
    );
  }

  return (
    <main className="page">
      <p>
        <Link to="/positions">← Back to positions</Link>
      </p>
      {error && <p role="alert">{error}</p>}

      <section className="detail-header">
        {editingTitle ? (
          <form onSubmit={handleTitleSave}>
            <div className="field">
              <label htmlFor="position-title">Title</label>
              <input
                id="position-title"
                value={titleDraft}
                onChange={(e) => setTitleDraft(e.target.value)}
                required
              />
            </div>
            <button type="submit">Save</button>
            <button type="button" onClick={() => setEditingTitle(false)}>
              Cancel
            </button>
          </form>
        ) : (
          <div className="page-header">
            <h1>{position.title}</h1>
            <button onClick={() => setEditingTitle(true)}>Edit</button>
          </div>
        )}
      </section>

      <section>
        <h2>Questions{questions.length === 0 && " — 0 questions"}</h2>
        {questions.length > 0 && (
          <ul className="history-list">
            {questions.map((question) => (
              <li key={question.id} className="question-row">
                {editingQuestionId === question.id ? (
                  <>
                    <input
                      value={editingQuestionText}
                      onChange={(e) => setEditingQuestionText(e.target.value)}
                      autoFocus
                    />
                    <div className="actions-cell">
                      <button onClick={() => handleSaveQuestion(question.id)}>Save</button>
                      <button onClick={() => setEditingQuestionId(null)}>Cancel</button>
                    </div>
                  </>
                ) : (
                  <>
                    <span>
                      {question.sequence_order}. {question.question_text}
                    </span>
                    <div className="actions-cell">
                      <button
                        onClick={() => {
                          setEditingQuestionId(question.id);
                          setEditingQuestionText(question.question_text);
                        }}
                      >
                        Edit
                      </button>
                      <button className="btn-danger" onClick={() => handleDeleteQuestion(question.id)}>
                        Delete
                      </button>
                    </div>
                  </>
                )}
              </li>
            ))}
          </ul>
        )}

        <form onSubmit={handleAddQuestion}>
          <div className="field">
            <label htmlFor="new-question-text">Question text</label>
            <input
              id="new-question-text"
              value={newQuestionText}
              onChange={(e) => setNewQuestionText(e.target.value)}
              required
            />
          </div>
          <div className="field">
            <label htmlFor="new-question-order">Sequence order</label>
            <input
              id="new-question-order"
              type="number"
              min={0}
              value={newQuestionOrder}
              onChange={(e) => setNewQuestionOrder(e.target.value)}
              required
            />
          </div>
          <button type="submit">Add question</button>
        </form>
      </section>
    </main>
  );
}

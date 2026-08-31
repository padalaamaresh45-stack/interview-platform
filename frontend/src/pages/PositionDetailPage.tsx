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

  async function refresh() {
    try {
      const [found, questionList] = await Promise.all([getPosition(id), listQuestions(id)]);
      setPosition(found ?? null);
      setTitleDraft(found?.title ?? "");
      setQuestions(questionList);
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
      setNewQuestionOrder("");
      await refresh();
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
      <main>
        <p>{error ?? "Loading…"}</p>
      </main>
    );
  }

  return (
    <main>
      <p>
        <Link to="/positions">← Back to positions</Link>
      </p>
      {error && <p role="alert">{error}</p>}

      {editingTitle ? (
        <form onSubmit={handleTitleSave}>
          <input value={titleDraft} onChange={(e) => setTitleDraft(e.target.value)} required />
          <button type="submit">Save</button>
          <button type="button" onClick={() => setEditingTitle(false)}>
            Cancel
          </button>
        </form>
      ) : (
        <h1>
          {position.title} <button onClick={() => setEditingTitle(true)}>Edit</button>
        </h1>
      )}

      <h2>Questions {questions.length === 0 && "— 0 questions"}</h2>
      <ol>
        {questions.map((question) => (
          <li key={question.id}>
            {editingQuestionId === question.id ? (
              <>
                <input
                  value={editingQuestionText}
                  onChange={(e) => setEditingQuestionText(e.target.value)}
                />
                <button onClick={() => handleSaveQuestion(question.id)}>Save</button>
                <button onClick={() => setEditingQuestionId(null)}>Cancel</button>
              </>
            ) : (
              <>
                {question.question_text}
                <button
                  onClick={() => {
                    setEditingQuestionId(question.id);
                    setEditingQuestionText(question.question_text);
                  }}
                >
                  Edit
                </button>
                <button onClick={() => handleDeleteQuestion(question.id)}>Delete</button>
              </>
            )}
          </li>
        ))}
      </ol>

      <form onSubmit={handleAddQuestion}>
        <label htmlFor="new-question-text">Question text</label>
        <input
          id="new-question-text"
          value={newQuestionText}
          onChange={(e) => setNewQuestionText(e.target.value)}
          required
        />
        <label htmlFor="new-question-order">Sequence order</label>
        <input
          id="new-question-order"
          type="number"
          value={newQuestionOrder}
          onChange={(e) => setNewQuestionOrder(e.target.value)}
          required
        />
        <button type="submit">Add question</button>
      </form>
    </main>
  );
}

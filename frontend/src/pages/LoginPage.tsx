import { useState, type FormEvent } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import { AppMark } from "../components/AppMark";

export function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const { user, initializing, login } = useAuth();
  const navigate = useNavigate();

  if (!initializing && user !== null) {
    return <Navigate to="/" replace />;
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login(email, password);
      navigate("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="login-shell">
      <div className="login-card">
        <AppMark className="login-mark" />
        <h1>Sign in</h1>
        <p className="login-subtitle">Interview Management Portal</p>
        <form onSubmit={handleSubmit}>
          <div className="field">
            <label htmlFor="email">Email</label>
            <input
              id="email"
              name="email"
              type="email"
              autoComplete="email"
              required
              disabled={submitting}
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>
          <div className="field">
            <div className="field-label-row">
              <label htmlFor="password">Password</label>
              <a className="login-forgot" href="#">
                Forgot?
              </a>
            </div>
            <input
              id="password"
              name="password"
              type="password"
              autoComplete="current-password"
              required
              disabled={submitting}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>
          <div className="login-error" aria-live="polite">
            {error && (
              <>
                <ErrorIcon />
                <span>{error}</span>
              </>
            )}
          </div>
          <button type="submit" disabled={submitting}>
            {submitting && <span className="login-spinner" aria-hidden="true" />}
            {submitting ? "Signing in…" : "Sign in"}
          </button>
        </form>
        <p className="login-footer">Trouble signing in? Contact your admin.</p>
      </div>
    </main>
  );
}

function ErrorIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <circle cx="8" cy="8" r="7" stroke="currentColor" strokeWidth="1.5" />
      <path d="M8 4.5V9" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      <circle cx="8" cy="11.25" r="0.9" fill="currentColor" />
    </svg>
  );
}

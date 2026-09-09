import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, ApiError } from "../api/client";
import { useAuth } from "../context/AuthContext";
import type { DesignSession } from "../api/types";

export function DashboardPage() {
  const { user, logout } = useAuth();
  const [sessions, setSessions] = useState<DesignSession[] | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.get<{ sessions: DesignSession[] }>("/api/sessions").then((res) => setSessions(res.sessions));
  }, []);

  async function handleDelete(session: DesignSession) {
    const label = session.title ?? session.room_type ?? `Design #${session.id}`;
    if (!window.confirm(`Delete "${label}" permanently? This cannot be undone.`)) return;
    setError(null);
    setDeletingId(session.id);
    try {
      await api.delete(`/api/sessions/${session.id}`);
      setSessions((prev) => prev?.filter((s) => s.id !== session.id) ?? null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not delete this design.");
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <div className="dashboard-page">
      <header className="dashboard-page__header">
        <h1>VisionDecor</h1>
        <div>
          <span>{user?.name}</span>
          <button onClick={() => logout()}>Log out</button>
        </div>
      </header>

      <Link to="/designs/new" className="button-primary">
        + New Design
      </Link>

      <h2>Your designs</h2>
      {error && <div className="auth-form__error">{error}</div>}
      {sessions === null && <p>Loading…</p>}
      {sessions?.length === 0 && (
        <p className="dashboard-page__empty">
          No designs yet. Start your first one above — upload a room photo and tell us your style,
          colours, and budget.
        </p>
      )}
      <ul className="session-list">
        {sessions?.map((s) => (
          <li key={s.id} className="session-list__item">
            <Link to={`/designs/${s.id}`}>
              {s.title ?? s.room_type ?? `Design #${s.id}`} — <em>{s.status}</em>
            </Link>
            <button
              type="button"
              className="session-list__delete"
              onClick={() => handleDelete(s)}
              disabled={deletingId === s.id}
            >
              {deletingId === s.id ? "Deleting…" : "Delete"}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

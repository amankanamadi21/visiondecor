import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { useAuth } from "../context/AuthContext";
import type { DesignSession } from "../api/types";

export function DashboardPage() {
  const { user, logout } = useAuth();
  const [sessions, setSessions] = useState<DesignSession[] | null>(null);

  useEffect(() => {
    api.get<{ sessions: DesignSession[] }>("/api/sessions").then((res) => setSessions(res.sessions));
  }, []);

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
      {sessions === null && <p>Loading…</p>}
      {sessions?.length === 0 && (
        <p className="dashboard-page__empty">
          No designs yet. Start your first one above — upload a room photo and tell us your style,
          colours, and budget.
        </p>
      )}
      <ul className="session-list">
        {sessions?.map((s) => (
          <li key={s.id}>
            <Link to={`/designs/${s.id}`}>
              {s.title ?? s.room_type ?? `Design #${s.id}`} — <em>{s.status}</em>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}

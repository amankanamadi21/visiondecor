import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import { RecommendationCard } from "../components/RecommendationCard";
import { FloorPlanView } from "../components/FloorPlanView";
import { FeedbackBox } from "../components/FeedbackBox";
import type { DesignSession, Layout, Recommendation } from "../api/types";

type LayoutScoreKey = "space_utilization" | "accessibility" | "movement_flow" | "visual_balance" | "functionality";
const LAYOUT_SCORE_ITEMS: { key: LayoutScoreKey; label: string }[] = [
  { key: "space_utilization", label: "Space utilization" },
  { key: "accessibility", label: "Accessibility" },
  { key: "movement_flow", label: "Movement flow" },
  { key: "visual_balance", label: "Visual balance" },
  { key: "functionality", label: "Functionality" },
];

export function DesignDetailPage() {
  const { id } = useParams();
  const sessionId = Number(id);
  const [session, setSession] = useState<DesignSession | null>(null);
  const [recommendation, setRecommendation] = useState<Recommendation | null>(null);
  const [layout, setLayout] = useState<Layout | null>(null);
  const [notFound, setNotFound] = useState(false);

  const load = useCallback(async () => {
    try {
      const sessionRes = await api.get<{ session: DesignSession }>(`/api/sessions/${sessionId}`);
      setSession(sessionRes.session);

      if (sessionRes.session.status === "ready") {
        const [recRes, layoutRes] = await Promise.all([
          api.get<{ recommendation: Recommendation }>(`/api/sessions/${sessionId}/recommendation`),
          api.get<{ layout: Layout }>(`/api/sessions/${sessionId}/layout`),
        ]);
        setRecommendation(recRes.recommendation);
        setLayout(layoutRes.layout);
      }
    } catch {
      setNotFound(true);
    }
  }, [sessionId]);

  useEffect(() => {
    load();
  }, [load]);

  if (notFound) {
    return (
      <div className="design-detail-page">
        <p>This design could not be found.</p>
        <Link to="/dashboard">Back to dashboard</Link>
      </div>
    );
  }

  if (!session) return <div className="design-detail-page">Loading…</div>;

  const isSampleRoom = recommendation?.is_sample_room ?? layout?.is_sample_room ?? false;

  return (
    <div className="design-detail-page">
      <Link to="/dashboard">&larr; Back to dashboard</Link>
      <h1>{session.title ?? session.room_type ?? `Design #${session.id}`}</h1>
      <p>
        Status: <strong>{session.status}</strong>
        {session.preferred_style && <> · Style: {session.preferred_style}</>}
        {session.budget != null && (
          <>
            {" "}
            · Budget: {session.currency} {session.budget.toLocaleString()}
          </>
        )}
      </p>

      {isSampleRoom && (
        <div className="sample-room-badge">
          Sample room — this design used demo analysis data, not a real analyzed photo (see decision D022).
        </div>
      )}

      {!isSampleRoom && recommendation && (
        <div className="sample-room-badge">
          Real photo, user-provided dimensions (decision D004) — style recognition is real, but since
          existing-furniture detection isn't implemented yet, this design assumes the room is empty.
        </div>
      )}

      {session.status !== "ready" && (
        <p className="wizard-step__honesty-note">
          No design has been generated for this session yet.{" "}
          <Link to="/designs/new">Start a new design</Link> to see the full pipeline.
        </p>
      )}

      {recommendation && (
        <section>
          <h2>Recommendations</h2>
          <p>
            Total: {recommendation.budget ? session.currency : ""} {recommendation.total_cost.toLocaleString()}{" "}
            of {session.currency} {recommendation.budget.toLocaleString()} budget —{" "}
            <strong className={recommendation.within_budget ? "within-budget" : "over-budget"}>
              {recommendation.within_budget ? "within budget" : "over budget"}
            </strong>
            {" · iteration "}
            {recommendation.iteration}
            {recommendation.iteration > 1 && (
              <>
                {" · "}
                <Link to={`/designs/${sessionId}/compare`}>Compare with a previous iteration</Link>
              </>
            )}
          </p>
          <div className="recommendation-list">
            {recommendation.items.map((item) => (
              <RecommendationCard key={item.id} item={item} />
            ))}
          </div>
        </section>
      )}

      {layout && (
        <section>
          <h2>Layout</h2>
          <p>
            Layout score: <strong>{layout.layout_score.toFixed(3)}</strong> ({layout.algorithm},{" "}
            {layout.iterations} iterations)
          </p>
          <div className="layout-score-breakdown">
            {LAYOUT_SCORE_ITEMS.map(({ key, label }) => (
              <div key={key} className="score-bar">
                <span>{label}</span>
                <div className="score-bar__track">
                  <div
                    className="score-bar__fill"
                    style={{ width: `${(layout.score_breakdown[key] ?? 0) * 100}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
          <div className="constraints-list">
            {Object.entries(layout.constraints_satisfied).map(([key, ok]) => (
              <span key={key} className={ok ? "constraint-ok" : "constraint-fail"}>
                {ok ? "✓" : "✗"} {key.replace(/_/g, " ")}
              </span>
            ))}
          </div>

          {layout.floorplan_svg && <FloorPlanView svg={layout.floorplan_svg} />}

          {layout.visualization ? (
            <div className="visualization-view">
              <img src={layout.visualization.image_url} alt="Generated visualization" />
              <p className="wizard-step__honesty-note">
                {layout.visualization.structure_preserving
                  ? "This image was generated by editing your actual room photo, so its structure (walls, windows, doors) is preserved by construction. It is still an artistic impression guided by the layout above, not a guaranteed pixel-accurate depiction — the floor plan remains the authoritative record."
                  : `This image was generated by ${layout.visualization.provider}, which does not perform structure-preserving editing — it may not accurately reflect this room's real walls, windows, or doors. The floor plan above is the authoritative layout.`}
              </p>
            </div>
          ) : (
            <p className="wizard-step__honesty-note">
              No photorealistic visualization is available for this design (no image-generation provider is
              currently configured). The floor plan above is the precise, always-available record of the
              computed layout.
            </p>
          )}
        </section>
      )}

      {session.status === "ready" && <FeedbackBox sessionId={sessionId} onRefined={load} />}
    </div>
  );
}

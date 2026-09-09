import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, API_BASE } from "../api/client";
import { RecommendationCard } from "../components/RecommendationCard";
import { FloorPlanView } from "../components/FloorPlanView";
import { FeedbackBox } from "../components/FeedbackBox";
import { DetectedObjectsPanel } from "../components/DetectedObjectsPanel";
import { JobProgress } from "../components/JobProgress";
import type { DesignSession, Job, Layout, Recommendation, StyleResult } from "../api/types";

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
  const [styleResult, setStyleResult] = useState<StyleResult | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [regeneratingJobId, setRegeneratingJobId] = useState<number | null>(null);

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
      try {
        setStyleResult(await api.get<StyleResult>(`/api/sessions/${sessionId}/style`));
      } catch {
        // No style/detection result yet (e.g. an older session) — not fatal.
      }
    } catch {
      setNotFound(true);
    }
  }, [sessionId]);

  useEffect(() => {
    load();
  }, [load]);

  /** A confirmed detection genuinely changes the room model (a real
   * positioned existing object, or a recomputed free_space_ratio) — so it's
   * regenerated the same way a feedback-driven refinement is, just without
   * needing the user to type anything. */
  async function handleGeometryConfirmed() {
    const res = await api.post<{ job_id: number }>(`/api/sessions/${sessionId}/generate`);
    setRegeneratingJobId(res.job_id);
  }

  function handleRegenerateDone(_job: Job) {
    setRegeneratingJobId(null);
    load();
  }

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
  // /samples/... is a frontend-relative static asset (same origin, no
  // prefix needed); /api/... is backend-relative and needs API_BASE — same
  // origin-mismatch reasoning as the visualization image above.
  const originalPhotoUrl = styleResult?.original_photo_url;
  const originalPhotoSrc = originalPhotoUrl
    ? originalPhotoUrl.startsWith("/api/")
      ? `${API_BASE}${originalPhotoUrl}`
      : originalPhotoUrl
    : null;

  return (
    <div className="design-detail-page">
      <div className="design-detail-page__toolbar design-detail-page__no-print">
        <Link to="/dashboard">&larr; Back to dashboard</Link>
        {session.status === "ready" && (
          <button type="button" onClick={() => window.print()}>
            Export as PDF
          </button>
        )}
      </div>
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
          Real photo, user-provided dimensions (decision D004) — style recognition and furniture/
          architectural detection are both real (see below). Confident furniture detections reduced the
          estimated free space used for these recommendations, but nothing detected is placed at a specific
          spot in the layout — a single photo can't measure exact positions.
        </div>
      )}

      {styleResult && (
        <DetectedObjectsPanel
          detected={styleResult.detected_objects}
          sessionId={sessionId}
          roomWidthCm={styleResult.room_width_cm}
          roomLengthCm={styleResult.room_length_cm}
          onGeometryConfirmed={handleGeometryConfirmed}
        />
      )}

      {regeneratingJobId !== null && (
        <div className="wizard-step__honesty-note">
          <p>Regenerating this design around the confirmed item…</p>
          <JobProgress jobId={regeneratingJobId} onDone={handleRegenerateDone} />
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
              <span className="design-detail-page__no-print">
                {" · "}
                <Link to={`/designs/${sessionId}/compare`}>Compare with a previous iteration</Link>
              </span>
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

          {(originalPhotoSrc || layout.visualization) && (
            <div className="before-after">
              {originalPhotoSrc && (
                <div className="before-after__panel">
                  <h3>{isSampleRoom ? "Sample room photo" : "Your uploaded photo"}</h3>
                  <img src={originalPhotoSrc} alt="Uploaded room" />
                </div>
              )}
              {layout.visualization && (
                <div className="before-after__panel">
                  <h3>Generated visualization</h3>
                  {/* image_url is backend-relative (e.g. /api/sessions/.../image) —
                      needs API_BASE since the frontend dev server (5173) and the
                      Flask backend (5000) are different origins; a bare <img>
                      src would resolve against 5173 and 404. Found via a real
                      browser walkthrough (2026-09-08), not caught by any prior
                      API-level test, since curl always targeted the backend
                      directly. */}
                  <img src={`${API_BASE}${layout.visualization.image_url}`} alt="Generated visualization" />
                </div>
              )}
            </div>
          )}
          {layout.visualization ? (
            <p className="wizard-step__honesty-note">
              {layout.visualization.structure_preserving
                ? "This image was generated by editing your actual room photo, so its structure (walls, windows, doors) is preserved by construction. It is still an artistic impression guided by the layout above, not a guaranteed pixel-accurate depiction — the floor plan remains the authoritative record."
                : `This image was generated by ${layout.visualization.provider}, which does not perform structure-preserving editing — it may not accurately reflect this room's real walls, windows, or doors. The floor plan above is the authoritative layout.`}
            </p>
          ) : (
            <p className="wizard-step__honesty-note">
              No photorealistic visualization is available for this design (no image-generation provider is
              currently configured). The floor plan above is the precise, always-available record of the
              computed layout.
            </p>
          )}
        </section>
      )}

      {session.status === "ready" && recommendation && (
        <div className="design-detail-page__no-print">
          <FeedbackBox
            sessionId={sessionId}
            onRefined={load}
            items={recommendation.items}
            currency={session.currency}
          />
        </div>
      )}
    </div>
  );
}

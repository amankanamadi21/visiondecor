import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import { FloorPlanView } from "../components/FloorPlanView";
import type { DesignSession, IterationSummary, Layout, Recommendation } from "../api/types";

interface Side {
  iteration: number | null;
  recommendation: Recommendation | null;
  layout: Layout | null;
}

const EMPTY_SIDE: Side = { iteration: null, recommendation: null, layout: null };

/**
 * FR-9 (design comparison, brief PART 2/PART 36): each feedback-driven
 * refinement (FeedbackBox -> a new generate run) already creates a new
 * Recommendation/Layout row under an incrementing `iteration` — this page
 * doesn't add any new generation logic, it just lets the user pick two
 * existing iterations and see them side by side.
 */
export function CompareDesignsPage() {
  const { id } = useParams();
  const sessionId = Number(id);

  const [session, setSession] = useState<DesignSession | null>(null);
  const [iterations, setIterations] = useState<IterationSummary[] | null>(null);
  const [left, setLeft] = useState<Side>(EMPTY_SIDE);
  const [right, setRight] = useState<Side>(EMPTY_SIDE);
  const [notFound, setNotFound] = useState(false);

  const loadSide = useCallback(
    async (iteration: number, setSide: (s: Side) => void) => {
      const [recRes, layoutRes] = await Promise.all([
        api.get<{ recommendation: Recommendation }>(
          `/api/sessions/${sessionId}/recommendation?iteration=${iteration}`
        ),
        api.get<{ layout: Layout }>(`/api/sessions/${sessionId}/layout?iteration=${iteration}`),
      ]);
      setSide({ iteration, recommendation: recRes.recommendation, layout: layoutRes.layout });
    },
    [sessionId]
  );

  useEffect(() => {
    async function init() {
      try {
        const sessionRes = await api.get<{ session: DesignSession }>(`/api/sessions/${sessionId}`);
        setSession(sessionRes.session);

        const iterRes = await api.get<{ iterations: IterationSummary[] }>(
          `/api/sessions/${sessionId}/iterations`
        );
        setIterations(iterRes.iterations);

        if (iterRes.iterations.length >= 1) {
          const last = iterRes.iterations[iterRes.iterations.length - 1];
          loadSide(last.iteration, setLeft);
        }
        if (iterRes.iterations.length >= 2) {
          const secondLast = iterRes.iterations[iterRes.iterations.length - 2];
          loadSide(secondLast.iteration, setRight);
        }
      } catch {
        setNotFound(true);
      }
    }
    init();
  }, [sessionId, loadSide]);

  if (notFound) {
    return (
      <div className="design-detail-page">
        <p>This design could not be found.</p>
        <Link to="/dashboard">Back to dashboard</Link>
      </div>
    );
  }

  if (!session || iterations === null) return <div className="design-detail-page">Loading…</div>;

  if (iterations.length < 2) {
    return (
      <div className="design-detail-page">
        <Link to={`/designs/${sessionId}`}>&larr; Back to design</Link>
        <h1>Compare designs</h1>
        <p className="wizard-step__honesty-note">
          This design only has {iterations.length} iteration{iterations.length === 1 ? "" : "s"} so far —
          comparison needs at least two. Submit feedback on the design to create a refined second iteration,
          then come back here.
        </p>
      </div>
    );
  }

  return (
    <div className="design-detail-page compare-designs-page">
      <Link to={`/designs/${sessionId}`}>&larr; Back to design</Link>
      <h1>Compare designs — {session.title ?? session.room_type ?? `Design #${session.id}`}</h1>

      <div className="compare-columns">
        <CompareColumn
          label="A"
          side={left}
          iterations={iterations}
          currency={session.currency}
          onSelect={(iter) => loadSide(iter, setLeft)}
        />
        <CompareColumn
          label="B"
          side={right}
          iterations={iterations}
          currency={session.currency}
          onSelect={(iter) => loadSide(iter, setRight)}
        />
      </div>
    </div>
  );
}

function CompareColumn({
  label,
  side,
  iterations,
  currency,
  onSelect,
}: {
  label: string;
  side: Side;
  iterations: IterationSummary[];
  currency: string;
  onSelect: (iteration: number) => void;
}) {
  return (
    <div className="compare-column">
      <div className="compare-column__header">
        <strong>Design {label}</strong>
        <select
          value={side.iteration ?? ""}
          onChange={(e) => onSelect(Number(e.target.value))}
        >
          {iterations.map((it) => (
            <option key={it.iteration} value={it.iteration}>
              Iteration {it.iteration} — {currency} {it.total_cost.toLocaleString()}
              {it.layout_score != null ? ` — score ${it.layout_score.toFixed(2)}` : ""}
            </option>
          ))}
        </select>
      </div>

      {side.recommendation && side.layout ? (
        <>
          <p>
            {currency} {side.recommendation.total_cost.toLocaleString()} of{" "}
            {currency} {side.recommendation.budget.toLocaleString()} —{" "}
            <strong className={side.recommendation.within_budget ? "within-budget" : "over-budget"}>
              {side.recommendation.within_budget ? "within budget" : "over budget"}
            </strong>
          </p>
          <p>
            Layout score: <strong>{side.layout.layout_score.toFixed(3)}</strong>
          </p>

          <ul className="compare-item-list">
            {side.recommendation.items.map((item) => (
              <li key={item.id}>
                <span>{item.catalog_item.name}</span>
                <span>
                  {item.catalog_item.currency} {item.catalog_item.price.toLocaleString()}
                </span>
              </li>
            ))}
          </ul>

          {side.layout.floorplan_svg && <FloorPlanView svg={side.layout.floorplan_svg} />}
        </>
      ) : (
        <p>Loading…</p>
      )}
    </div>
  );
}

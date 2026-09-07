import type { RecommendationItem } from "../api/types";

type ScoreKey = "style_match" | "color_match" | "budget_fit" | "space_fit";
const SCORE_ITEMS: { key: ScoreKey; label: string }[] = [
  { key: "style_match", label: "Style match" },
  { key: "color_match", label: "Color match" },
  { key: "budget_fit", label: "Budget fit" },
  { key: "space_fit", label: "Space fit" },
];

export function RecommendationCard({ item }: { item: RecommendationItem }) {
  const c = item.catalog_item;
  return (
    <div className="recommendation-card">
      <img src={c.image_url} alt={c.name} />
      <div className="recommendation-card__body">
        <div className="recommendation-card__header">
          <strong>{c.name}</strong>
          <span className="recommendation-card__action">{item.action}</span>
        </div>
        <div className="recommendation-card__price">
          {c.currency} {c.price.toLocaleString()}
          <span className="mock-badge" title="This is placeholder demo data, not a real product or price.">
            MOCK DATA
          </span>
        </div>
        <div className="recommendation-card__scores">
          {SCORE_ITEMS.map(({ key, label }) => (
            <div key={key} className="score-bar">
              <span>{label}</span>
              <div className="score-bar__track">
                <div
                  className="score-bar__fill"
                  style={{ width: `${(item.score_breakdown[key] ?? 0) * 100}%` }}
                />
              </div>
            </div>
          ))}
        </div>
        <p className="recommendation-card__rationale">{item.rationale}</p>
      </div>
    </div>
  );
}

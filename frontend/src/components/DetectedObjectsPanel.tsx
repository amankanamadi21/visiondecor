import type { DetectedObjects } from "../api/types";

/**
 * Display for FR-2/Report Issue R-07's real CV output (2026-09-08 batch):
 * pretrained YOLO furniture detection + pretrained ADE20K architectural
 * segmentation for a genuine photo, or a sample room's labeled fixture
 * ground truth — both already unified into one shape by the backend
 * (backend/api/design.py's `_detected_objects_dict`). Confident furniture
 * detections reduce the room's estimated free space for recommendations
 * ("area-only reservation", PLAN.md) — but no detected item is ever placed
 * at a specific position, since a single photo can't honestly provide one.
 */
export function DetectedObjectsPanel({ detected }: { detected: DetectedObjects }) {
  if (detected.furniture.length === 0 && detected.architectural.length === 0) {
    return (
      <div className="detected-objects-panel">
        <h3>What we found in your photo</h3>
        <p className="wizard-step__hint">Nothing was detected with enough confidence to report.</p>
      </div>
    );
  }

  return (
    <div className="detected-objects-panel">
      <h3>What we found in your photo</h3>
      {detected.source === "fixture_ground_truth" && (
        <p className="wizard-step__hint">Sample room — these are the fixture's labeled contents, not a live detection.</p>
      )}
      {detected.furniture.length > 0 && (
        <div>
          <strong>Furniture:</strong>{" "}
          {detected.furniture.map((item, i) => (
            <span key={i} className="detected-objects-panel__tag">
              {item.label} ({Math.round(item.confidence * 100)}%)
            </span>
          ))}
        </div>
      )}
      {detected.architectural.length > 0 && (
        <div>
          <strong>Architectural:</strong>{" "}
          {detected.architectural.map((item, i) => (
            <span key={i} className="detected-objects-panel__tag">
              {item.label} ({Math.round(item.confidence * 100)}%)
            </span>
          ))}
        </div>
      )}
      <p className="wizard-step__hint">
        Confident furniture detections reduce the estimated free space used when choosing what to recommend —
        but nothing here is placed at a specific spot in your layout, since a single photo can't measure that.
      </p>
    </div>
  );
}

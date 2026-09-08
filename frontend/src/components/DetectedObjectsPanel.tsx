import { useState } from "react";
import type { DetectedObjects } from "../api/types";
import { ConfirmGeometryForm } from "./ConfirmGeometryForm";

interface DetectedObjectsPanelProps {
  detected: DetectedObjects;
  // Only provided from the results page (DesignDetailPage) — the
  // 2026-09-08 "optional, from the results page" decision deliberately
  // keeps this out of the upload wizard, where there's no generated design
  // yet to regenerate around a confirmed item.
  sessionId?: number;
  roomWidthCm?: number | null;
  roomLengthCm?: number | null;
  onGeometryConfirmed?: () => void;
}

/**
 * Display for FR-2/Report Issue R-07's real CV output (2026-09-08 batch):
 * pretrained YOLO furniture detection + pretrained ADE20K architectural
 * segmentation for a genuine photo, or a sample room's labeled fixture
 * ground truth — both already unified into one shape by the backend
 * (backend/api/design.py's `_detected_objects_dict`). Confident furniture
 * detections reduce the room's estimated free space for recommendations
 * ("area-only reservation", PLAN.md); a user can additionally CONFIRM a
 * detection's real geometry (width/depth/height + a clicked position) to
 * turn it into an actually positioned existing object — the one path by
 * which this ever happens, since nothing is fabricated from the pixel bbox.
 */
export function DetectedObjectsPanel({
  detected, sessionId, roomWidthCm, roomLengthCm, onGeometryConfirmed,
}: DetectedObjectsPanelProps) {
  const [confirmingId, setConfirmingId] = useState<number | null>(null);
  const canConfirmGeometry = Boolean(sessionId && roomWidthCm && roomLengthCm && onGeometryConfirmed);

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
          {detected.furniture.map((item) => (
            <span key={item.id} className="detected-objects-panel__tag">
              {item.label} ({Math.round(item.confidence * 100)}%)
              {item.confirmed && " ✓ placed"}
              {canConfirmGeometry && item.can_confirm_geometry && !item.confirmed && (
                <button
                  type="button"
                  className="detected-objects-panel__confirm-button"
                  onClick={() => setConfirmingId(item.id)}
                >
                  Add real dimensions
                </button>
              )}
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
        Confident furniture detections reduce the estimated free space used when choosing what to recommend.
        {canConfirmGeometry
          ? " Confirm an item's real size and position above to place it in the layout for real."
          : " Nothing here is placed at a specific spot in your layout, since a single photo can't measure that."}
      </p>

      {canConfirmGeometry && confirmingId !== null && (
        <ConfirmGeometryForm
          sessionId={sessionId!}
          item={detected.furniture.find((f) => f.id === confirmingId)!}
          roomWidthCm={roomWidthCm!}
          roomLengthCm={roomLengthCm!}
          onCancel={() => setConfirmingId(null)}
          onConfirmed={() => {
            setConfirmingId(null);
            onGeometryConfirmed!();
          }}
        />
      )}
    </div>
  );
}

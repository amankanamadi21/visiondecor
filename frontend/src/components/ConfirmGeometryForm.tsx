import { useState } from "react";
import { api, ApiError } from "../api/client";
import type { DetectedFurnitureItem } from "../api/types";

interface ConfirmGeometryFormProps {
  sessionId: number;
  item: DetectedFurnitureItem;
  roomWidthCm: number;
  roomLengthCm: number;
  onConfirmed: () => void;
  onCancel: () => void;
}

const ROTATIONS = [0, 90, 180, 270] as const;
const DEFAULT_DIMENSION_CM = 80;

/**
 * The one UI that collects genuinely user-provided geometry for a detected
 * item (2026-09-08, "optional from the results page" decision) — width,
 * depth, height, and a click-to-place position on a to-scale room outline.
 * Nothing here is derived from the pixel detection; that's what makes the
 * result honest enough to place in the layout (see
 * ai/room_analysis/db_adapter.py's confirm_detected_object_geometry).
 */
export function ConfirmGeometryForm({
  sessionId,
  item,
  roomWidthCm,
  roomLengthCm,
  onConfirmed,
  onCancel,
}: ConfirmGeometryFormProps) {
  const [widthCm, setWidthCm] = useState(DEFAULT_DIMENSION_CM);
  const [depthCm, setDepthCm] = useState(DEFAULT_DIMENSION_CM);
  const [heightCm, setHeightCm] = useState(DEFAULT_DIMENSION_CM);
  const [rotationDeg, setRotationDeg] = useState<(typeof ROTATIONS)[number]>(0);
  const [position, setPosition] = useState<{ x: number; y: number } | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [footprintW, footprintD] = rotationDeg === 90 || rotationDeg === 270 ? [depthCm, widthCm] : [widthCm, depthCm];

  function handleSvgClick(e: React.MouseEvent<SVGSVGElement>) {
    const svg = e.currentTarget;
    const rect = svg.getBoundingClientRect();
    const x = ((e.clientX - rect.left) / rect.width) * roomWidthCm;
    const y = ((e.clientY - rect.top) / rect.height) * roomLengthCm;
    setPosition({ x: Math.round(x), y: Math.round(y) });
  }

  async function handleConfirm() {
    if (!position) return;
    setSubmitting(true);
    setError(null);
    try {
      await api.patch(`/api/sessions/${sessionId}/detected-objects/${item.id}/geometry`, {
        width_cm: widthCm, depth_cm: depthCm, height_cm: heightCm,
        x_cm: position.x, y_cm: position.y, rotation_deg: rotationDeg,
      });
      onConfirmed();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save this item's geometry.");
    } finally {
      setSubmitting(false);
    }
  }

  const clampedX = position ? Math.min(Math.max(position.x, footprintW / 2), roomWidthCm - footprintW / 2) : null;
  const clampedY = position ? Math.min(Math.max(position.y, footprintD / 2), roomLengthCm - footprintD / 2) : null;

  return (
    <div className="confirm-geometry-form">
      <p className="wizard-step__hint">
        Enter {item.label}'s real width/depth/height, then click where it sits in the room below.
      </p>
      {error && <div className="auth-form__error">{error}</div>}
      <div className="confirm-geometry-form__dimensions">
        <label>
          Width (cm)
          <input type="number" min={5} max={400} value={widthCm} onChange={(e) => setWidthCm(Number(e.target.value))} />
        </label>
        <label>
          Depth (cm)
          <input type="number" min={5} max={400} value={depthCm} onChange={(e) => setDepthCm(Number(e.target.value))} />
        </label>
        <label>
          Height (cm)
          <input type="number" min={5} max={400} value={heightCm} onChange={(e) => setHeightCm(Number(e.target.value))} />
        </label>
        <button type="button" onClick={() => setRotationDeg(ROTATIONS[(ROTATIONS.indexOf(rotationDeg) + 1) % 4])}>
          Rotate ({rotationDeg}°)
        </button>
      </div>

      <svg
        className="confirm-geometry-form__room"
        style={{ aspectRatio: roomWidthCm / roomLengthCm }}
        viewBox={`0 0 ${roomWidthCm} ${roomLengthCm}`}
        onClick={handleSvgClick}
        role="img"
        aria-label="Click to place this item in the room"
      >
        <rect x={0} y={0} width={roomWidthCm} height={roomLengthCm} className="confirm-geometry-form__room-outline" />
        {clampedX !== null && clampedY !== null && (
          <rect
            x={clampedX - footprintW / 2}
            y={clampedY - footprintD / 2}
            width={footprintW}
            height={footprintD}
            className="confirm-geometry-form__item-preview"
          />
        )}
      </svg>

      <div className="confirm-geometry-form__actions">
        <button type="button" onClick={onCancel} disabled={submitting}>
          Cancel
        </button>
        <button type="button" onClick={handleConfirm} disabled={!position || submitting}>
          {submitting ? "Saving…" : "Confirm placement"}
        </button>
      </div>
    </div>
  );
}

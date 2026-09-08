import { useState, type FormEvent } from "react";
import { api, ApiError } from "../api/client";
import { JobProgress } from "./JobProgress";
import type { Job, RecommendationItem, StructuredDeltas } from "../api/types";

interface FeedbackBoxProps {
  sessionId: number;
  onRefined: () => void;
  items: RecommendationItem[];
  currency: string;
}

/** Turns the raw structured_deltas the feedback parser produced (D024) into
 * a sentence a user can actually read — catalog_item ids and field names
 * like `crowding_shift` mean nothing to them. Found missing during a real
 * browser walkthrough (2026-09-08): the box was showing raw JSON. */
function describeDeltas(deltas: StructuredDeltas, items: RecommendationItem[], currency: string): string {
  const nameById = new Map(items.map((item) => [item.catalog_item.id, item.catalog_item.name]));
  const parts: string[] = [];

  if (deltas.budget_delta) {
    const verb = deltas.budget_delta < 0 ? "Reducing" : "Increasing";
    parts.push(`${verb} budget by ${currency} ${Math.abs(deltas.budget_delta).toLocaleString()}`);
  }
  if (deltas.style_shift) {
    parts.push(`Shifting style toward ${deltas.style_shift}`);
  }
  if (deltas.crowding_shift === "less") {
    parts.push("Making the room feel less crowded");
  } else if (deltas.crowding_shift === "more") {
    parts.push("Filling the room with more furniture");
  }
  if (deltas.keep_item_ids.length > 0) {
    const names = deltas.keep_item_ids.map((id) => nameById.get(id) ?? `item #${id}`);
    parts.push(`Keeping: ${names.join(", ")}`);
  }
  if (deltas.remove_item_ids.length > 0) {
    const names = deltas.remove_item_ids.map((id) => nameById.get(id) ?? `item #${id}`);
    parts.push(`Removing: ${names.join(", ")}`);
  }
  if (deltas.notes) {
    parts.push(deltas.notes);
  }

  return parts.length > 0
    ? parts.join(". ") + "."
    : "No specific change was detected in your feedback — regenerating with your current preferences.";
}

/**
 * FR-7 feedback loop (decision D024). Submitting triggers a new generation
 * iteration automatically — see backend/api/feedback.py — so the user sees
 * a refined design without a separate manual "regenerate" step.
 */
export function FeedbackBox({ sessionId, onRefined, items, currency }: FeedbackBoxProps) {
  const [text, setText] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [jobId, setJobId] = useState<number | null>(null);
  const [appliedDeltas, setAppliedDeltas] = useState<StructuredDeltas | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!text.trim()) return;
    setError(null);
    setSubmitting(true);
    try {
      const res = await api.post<{ feedback: { structured_deltas: StructuredDeltas }; job_id: number }>(
        `/api/sessions/${sessionId}/feedback`,
        { raw_text: text }
      );
      setAppliedDeltas(res.feedback.structured_deltas);
      setJobId(res.job_id);
      setText("");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not submit feedback.");
    } finally {
      setSubmitting(false);
    }
  }

  function handleDone(_job: Job) {
    setJobId(null);
    setAppliedDeltas(null);
    onRefined();
  }

  return (
    <div className="feedback-box">
      <h3>Feedback</h3>
      <p className="wizard-step__hint">
        Try: "keep the bed but remove the lamp", "make it more industrial", "reduce cost",
        "make the room less crowded".
      </p>
      {error && <div className="auth-form__error">{error}</div>}
      {jobId !== null ? (
        <JobProgress jobId={jobId} onDone={handleDone} />
      ) : (
        <form onSubmit={handleSubmit}>
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="What would you change about this design?"
            rows={3}
          />
          <button type="submit" disabled={!text.trim() || submitting}>
            {submitting ? "Submitting…" : "Refine design"}
          </button>
        </form>
      )}
      {appliedDeltas && (
        <div className="feedback-box__applied">
          Understood: {describeDeltas(appliedDeltas, items, currency)}
        </div>
      )}
    </div>
  );
}

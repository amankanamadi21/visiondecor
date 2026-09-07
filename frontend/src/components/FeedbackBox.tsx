import { useState, type FormEvent } from "react";
import { api, ApiError } from "../api/client";
import { JobProgress } from "./JobProgress";
import type { Job } from "../api/types";

interface FeedbackBoxProps {
  sessionId: number;
  onRefined: () => void;
}

/**
 * FR-7 feedback loop (decision D024). Submitting triggers a new generation
 * iteration automatically — see backend/api/feedback.py — so the user sees
 * a refined design without a separate manual "regenerate" step.
 */
export function FeedbackBox({ sessionId, onRefined }: FeedbackBoxProps) {
  const [text, setText] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [jobId, setJobId] = useState<number | null>(null);
  const [appliedDeltas, setAppliedDeltas] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!text.trim()) return;
    setError(null);
    setSubmitting(true);
    try {
      const res = await api.post<{ feedback: { structured_deltas: Record<string, unknown> }; job_id: number }>(
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
          Understood: {JSON.stringify(appliedDeltas)}
        </div>
      )}
    </div>
  );
}

import { useRef, useState, type FormEvent } from "react";
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

interface ChatMessage {
  role: "user" | "assistant";
  text: string;
}

/**
 * FR-7 feedback loop (decision D024). Submitting triggers a new generation
 * iteration automatically — see backend/api/feedback.py — so the user sees
 * a refined design without a separate manual "regenerate" step. Presented as
 * a chat thread: each message you send and each "Understood: ..." response
 * stays visible as history, rather than a single-shot form that resets —
 * the underlying mechanism (one real refinement job per message, a genuinely
 * new iteration each time) is unchanged, only the presentation is.
 */
export function FeedbackBox({ sessionId, onRefined, items, currency }: FeedbackBoxProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([
    { role: "assistant", text: "What would you like to change about this design?" },
  ]);
  const [text, setText] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [jobId, setJobId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  // Stashed in a ref rather than state, so the "Understood: ..." bubble
  // appears only once the refined design is actually ready — matching the
  // real state, not just the request sent.
  const pendingDeltas = useRef<StructuredDeltas | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const message = text.trim();
    if (!message) return;
    setError(null);
    setSubmitting(true);
    setMessages((prev) => [...prev, { role: "user", text: message }]);
    setText("");
    try {
      const res = await api.post<{ feedback: { structured_deltas: StructuredDeltas }; job_id: number }>(
        `/api/sessions/${sessionId}/feedback`,
        { raw_text: message }
      );
      setJobId(res.job_id);
      pendingDeltas.current = res.feedback.structured_deltas;
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not submit feedback.");
    } finally {
      setSubmitting(false);
    }
  }

  function handleDone(_job: Job) {
    setJobId(null);
    if (pendingDeltas.current) {
      // Compute the text eagerly, right here, using the current ref value —
      // setMessages's updater function is a closure React calls lazily, not
      // at this call site, so reading pendingDeltas.current inside it would
      // instead see whatever the ref holds by the time React gets around to
      // invoking it — null, since the very next line resets it. That's the
      // exact "Cannot read properties of null (reading 'budget_delta')"
      // crash found live (2026-09-18): the reset was racing the lazy read.
      const text = `Understood: ${describeDeltas(pendingDeltas.current, items, currency)}`;
      pendingDeltas.current = null;
      setMessages((prev) => [...prev, { role: "assistant", text }]);
    }
    onRefined();
  }

  return (
    <div className="feedback-box feedback-box--chat">
      <h3>Feedback</h3>
      <p className="wizard-step__hint">
        Try: "keep the bed but remove the lamp", "make it more industrial", "reduce cost",
        "make the room less crowded".
      </p>
      {error && <div className="auth-form__error">{error}</div>}
      <div className="feedback-chat__thread">
        {messages.map((m, i) => (
          <div key={i} className={`feedback-chat__bubble feedback-chat__bubble--${m.role}`}>
            {m.text}
          </div>
        ))}
        {jobId !== null && (
          <div className="feedback-chat__bubble feedback-chat__bubble--assistant feedback-chat__bubble--pending">
            <JobProgress jobId={jobId} onDone={handleDone} />
          </div>
        )}
      </div>
      <form onSubmit={handleSubmit} className="feedback-chat__composer">
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="What would you change about this design?"
          rows={2}
          disabled={jobId !== null}
        />
        <button type="submit" disabled={!text.trim() || submitting || jobId !== null}>
          {submitting ? "Sending…" : "Send"}
        </button>
      </form>
    </div>
  );
}

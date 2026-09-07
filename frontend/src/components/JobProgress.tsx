import { useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import type { Job } from "../api/types";

const POLL_INTERVAL_MS = 800;

const STAGE_LABELS: Record<string, string> = {
  preprocess: "Preparing your image",
  room_analysis: "Analyzing the room",
  style_recognition: "Recognizing interior style",
  recommendation: "Generating recommendations",
  layout_optimization: "Optimizing furniture layout",
  visualization: "Rendering visualization",
};

interface JobProgressProps {
  jobId: number;
  onDone?: (job: Job) => void;
  onError?: (job: Job) => void;
}

/**
 * Polls GET /api/jobs/:id until it reaches a terminal state (Batch 1
 * thread-based JobRunner has no push/websocket channel — see PLAN.md
 * decision log — so polling is the correct, deliberate choice here, not a
 * placeholder for something better).
 */
export function JobProgress({ jobId, onDone, onError }: JobProgressProps) {
  const [job, setJob] = useState<Job | null>(null);
  const intervalRef = useRef<number | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function poll() {
      try {
        const res = await api.get<{ job: Job }>(`/api/jobs/${jobId}`);
        if (cancelled) return;
        setJob(res.job);
        if (res.job.status === "done") {
          if (intervalRef.current) window.clearInterval(intervalRef.current);
          onDone?.(res.job);
        } else if (res.job.status === "failed") {
          if (intervalRef.current) window.clearInterval(intervalRef.current);
          onError?.(res.job);
        }
      } catch {
        // A transient network hiccup shouldn't kill the poll loop; it will
        // simply try again on the next interval tick.
      }
    }

    poll();
    intervalRef.current = window.setInterval(poll, POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      if (intervalRef.current) window.clearInterval(intervalRef.current);
    };
  }, [jobId, onDone, onError]);

  if (!job) return <div className="job-progress">Starting…</div>;

  return (
    <div className="job-progress">
      <div className="job-progress__label">
        {STAGE_LABELS[job.stage] ?? job.stage}
        {job.status === "failed" && " — failed"}
      </div>
      <div className="job-progress__bar-track">
        <div
          className="job-progress__bar-fill"
          style={{ width: `${job.progress}%` }}
          data-status={job.status}
        />
      </div>
      {job.status === "failed" && (
        <p className="job-progress__error">
          {job.error_message ?? "Something went wrong during this step."}
        </p>
      )}
    </div>
  );
}

import { useState, type ChangeEvent, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { api, ApiError } from "../api/client";
import { JobProgress } from "../components/JobProgress";
import { DetectedObjectsPanel } from "../components/DetectedObjectsPanel";
import type { DesignSession, Job, RoomImage, RoomType, Style, StyleResult } from "../api/types";

type Step = "room_type" | "image_source" | "preferences" | "processing" | "generating";

const ROOM_TYPES: { value: RoomType; label: string }[] = [
  { value: "living_room", label: "Living room" },
  { value: "bedroom", label: "Bedroom" },
  { value: "office", label: "Home office" },
  { value: "study_room", label: "Study room" },
  { value: "other", label: "Other" },
];

const STYLES: Style[] = ["Modern", "Minimalist", "Contemporary", "Traditional", "Industrial", "Scandinavian"];

// D022 — sample rooms are recognized by the backend via content hash once
// "uploaded" through the normal endpoint; the mapping to a labeled fixture
// name is display-only here, matching ai/room_analysis/fixtures.py.
const SAMPLE_ROOMS: { file: string; label: string; description: string; matchesRoomType: RoomType }[] = [
  {
    file: "bedroom_small_scandinavian",
    label: "Small Scandinavian Bedroom",
    description: "A small, mostly empty bedroom with one old wardrobe.",
    matchesRoomType: "bedroom",
  },
  {
    file: "living_room_modern_cluttered",
    label: "Living Room With Dated Furniture",
    description: "An old sofa and a CRT-era TV stand, awkwardly placed.",
    matchesRoomType: "living_room",
  },
  {
    file: "study_room_industrial",
    label: "Industrial-Style Study",
    description: "A compact study with one existing desk.",
    matchesRoomType: "study_room",
  },
  {
    file: "office_contemporary_empty",
    label: "Empty Contemporary Office",
    description: "A nearly empty home office — needs almost everything.",
    matchesRoomType: "office",
  },
];

/** FR-1/FR-2/FR-4 wizard: room type -> image (sample or real upload) ->
 * preferences -> generate. Sample rooms are a documented, disclosed stand-in
 * for real CV (decision D022) — never presented as if a real photo was
 * analyzed; the results page repeats this disclosure from the API's own
 * `is_sample_room` flag, not just here. */
export function NewDesignPage() {
  const navigate = useNavigate();
  const [step, setStep] = useState<Step>("room_type");
  const [roomType, setRoomType] = useState<RoomType | "">("");
  const [session, setSession] = useState<DesignSession | null>(null);
  const [isSampleRoom, setIsSampleRoom] = useState(false);
  const [hasKnownDimensions, setHasKnownDimensions] = useState(false);
  const [roomWidthCm, setRoomWidthCm] = useState("");
  const [roomLengthCm, setRoomLengthCm] = useState("");
  const [jobId, setJobId] = useState<number | null>(null);
  const [styleJobId, setStyleJobId] = useState<number | null>(null);
  const [styleResult, setStyleResult] = useState<StyleResult | null>(null);
  const [preferredStyle, setPreferredStyle] = useState<Style | "">("");
  const [colorsText, setColorsText] = useState("");
  const [budget, setBudget] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleCreateSession(e: FormEvent) {
    e.preventDefault();
    if (!roomType) return;
    setError(null);
    setSubmitting(true);
    try {
      const res = await api.post<{ session: DesignSession }>("/api/sessions", { room_type: roomType });
      setSession(res.session);
      setStep("image_source");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not create the design session.");
    } finally {
      setSubmitting(false);
    }
  }

  async function uploadImage(fileToUpload: File, dimensions?: { width: string; length: string }) {
    if (!session) return;
    setError(null);
    setSubmitting(true);
    try {
      const formData = new FormData();
      formData.append("image", fileToUpload);
      // D004 (locked 2026-09-08): both-or-neither — a single dimension can't
      // be used, and the backend rejects a lone one anyway.
      if (dimensions?.width && dimensions?.length) {
        formData.append("room_width_cm", dimensions.width);
        formData.append("room_length_cm", dimensions.length);
      }
      const res = await api.postForm<{
        room_image: RoomImage;
        is_sample_room: boolean;
        job_id: number;
        style_job_id: number | null;
      }>(`/api/sessions/${session.id}/image`, formData);
      setIsSampleRoom(res.is_sample_room);
      setHasKnownDimensions(res.is_sample_room || Boolean(dimensions?.width && dimensions?.length));
      setJobId(res.job_id);
      setStyleJobId(res.style_job_id);
      setStep("processing");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not upload the image.");
    } finally {
      setSubmitting(false);
    }
  }

  function handleFileChange(e: ChangeEvent<HTMLInputElement>) {
    const chosen = e.target.files?.[0] ?? null;
    if (chosen) uploadImage(chosen, { width: roomWidthCm, length: roomLengthCm });
  }

  async function handleUseSample(sampleFile: string) {
    const res = await fetch(`/samples/${sampleFile}.jpg`);
    const blob = await res.blob();
    const sampleAsFile = new File([blob], `${sampleFile}.jpg`, { type: "image/jpeg" });
    uploadImage(sampleAsFile); // dimensions never sent for samples — the fixture's own always win
  }

  /** The style/detection job (style_job_id) runs independently of the
   * preprocess job we're actually polling in the UI, and can still be in
   * progress when preprocess finishes — waiting for it here (not just
   * preprocess) is what makes fetching /style below reliable rather than
   * racing a 404. Found via a real browser walkthrough, not assumed. */
  async function waitForJobDone(id: number, timeoutMs = 30000): Promise<void> {
    const deadline = Date.now() + timeoutMs;
    while (Date.now() < deadline) {
      const res = await api.get<{ job: Job }>(`/api/jobs/${id}`);
      if (res.job.status === "done" || res.job.status === "failed") return;
      await new Promise((resolve) => setTimeout(resolve, 500));
    }
  }

  async function handlePreprocessDone(_job: Job) {
    if (styleJobId !== null) {
      await waitForJobDone(styleJobId);
    }
    if (session) {
      try {
        const res = await api.get<StyleResult>(`/api/sessions/${session.id}/style`);
        setStyleResult(res);
      } catch {
        // Style/detection results are informational only — a fetch failure
        // here shouldn't block the wizard from continuing.
      }
    }
    setStep("preferences");
  }

  async function handleGenerate(e: FormEvent) {
    e.preventDefault();
    if (!session || !preferredStyle || !budget) return;
    setError(null);
    setSubmitting(true);
    try {
      const colors = colorsText
        .split(",")
        .map((c) => c.trim())
        .filter(Boolean);
      await api.patch(`/api/sessions/${session.id}`, {
        preferred_style: preferredStyle,
        preferred_colors: colors,
        budget: Number(budget),
      });
      const genRes = await api.post<{ job_id: number }>(`/api/sessions/${session.id}/generate`);
      setJobId(genRes.job_id);
      setStep("generating");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not start generating your design.");
      setSubmitting(false);
    }
  }

  function handleGenerateDone(_job: Job) {
    if (session) navigate(`/designs/${session.id}`);
  }

  function handleGenerateError(job: Job) {
    setError(job.error_message ?? "Something went wrong while generating your design.");
    setStep("preferences");
  }

  const relevantSamples = roomType
    ? SAMPLE_ROOMS.filter((s) => s.matchesRoomType === roomType)
    : SAMPLE_ROOMS;

  return (
    <div className="new-design-page">
      <h1>New Design</h1>
      {error && <div className="auth-form__error">{error}</div>}

      {step === "room_type" && (
        <form onSubmit={handleCreateSession} className="wizard-step">
          <h2>Step 1 — What room is this?</h2>
          <div className="room-type-grid">
            {ROOM_TYPES.map((rt) => (
              <label key={rt.value} className={roomType === rt.value ? "selected" : ""}>
                <input
                  type="radio"
                  name="room_type"
                  value={rt.value}
                  checked={roomType === rt.value}
                  onChange={() => setRoomType(rt.value)}
                />
                {rt.label}
              </label>
            ))}
          </div>
          <button type="submit" disabled={!roomType || submitting}>
            Continue
          </button>
        </form>
      )}

      {step === "image_source" && (
        <div className="wizard-step">
          <h2>Step 2 — Choose a room photo</h2>

          <div className="wizard-step__honesty-note">
            If you upload your own photo, we run real style recognition and real furniture/architectural
            detection on it (shown after upload). Detections aren't used to plan around what's already there
            yet, though — tell us your room's size and we'll still recommend furniture for the whole room as
            if starting fresh. Sample rooms below use labeled demo data instead of live detection.
          </div>

          <h3>Sample rooms</h3>
          <div className="sample-room-grid">
            {relevantSamples.map((s) => (
              <button
                key={s.file}
                type="button"
                className="sample-room-card"
                onClick={() => handleUseSample(s.file)}
                disabled={submitting}
              >
                <img src={`/samples/${s.file}.jpg`} alt={s.label} />
                <strong>{s.label}</strong>
                <span>{s.description}</span>
              </button>
            ))}
          </div>

          <h3>Or upload your own photo</h3>
          <div className="room-dimensions-input">
            <label>
              Room width (cm)
              <input
                type="number"
                min={50}
                max={3000}
                value={roomWidthCm}
                onChange={(e) => setRoomWidthCm(e.target.value)}
                placeholder="e.g. 400"
              />
            </label>
            <label>
              Room length (cm)
              <input
                type="number"
                min={50}
                max={3000}
                value={roomLengthCm}
                onChange={(e) => setRoomLengthCm(e.target.value)}
                placeholder="e.g. 500"
              />
            </label>
          </div>
          <p className="wizard-step__hint">
            Optional — but without both, you'll get a real style prediction and nothing else, since a layout
            can't be computed without knowing the room's size.
          </p>
          <input type="file" accept="image/jpeg,image/png,image/webp" onChange={handleFileChange} />
        </div>
      )}

      {step === "processing" && jobId !== null && (
        <div className="wizard-step">
          <h2>Preparing your image</h2>
          {isSampleRoom && (
            <p className="sample-room-badge">Sample room — using demo analysis data.</p>
          )}
          <JobProgress jobId={jobId} onDone={handlePreprocessDone} />
        </div>
      )}

      {step === "preferences" && (
        <form onSubmit={handleGenerate} className="wizard-step">
          <h2>Step 3 — Your preferences</h2>
          {!isSampleRoom && !hasKnownDimensions && (
            <div className="wizard-step__honesty-note">
              No room dimensions were provided, so generating a design will fail with a clear message —
              you'll still see a real style prediction on the results page. Go back and enter dimensions, or
              pick a sample room, to see the full pipeline.
            </div>
          )}
          {!isSampleRoom && hasKnownDimensions && (
            <div className="wizard-step__honesty-note">
              Detections aren't used to plan around existing furniture yet, so this design will assume the
              room is empty and recommend furniture for everything it needs.
            </div>
          )}
          {styleResult && <DetectedObjectsPanel detected={styleResult.detected_objects} />}
          <label>
            Preferred style
            <select value={preferredStyle} onChange={(e) => setPreferredStyle(e.target.value as Style)} required>
              <option value="">Select a style…</option>
              {STYLES.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </label>
          <label>
            Preferred colors (comma-separated)
            <input
              type="text"
              value={colorsText}
              onChange={(e) => setColorsText(e.target.value)}
              placeholder="e.g. white, natural wood"
            />
          </label>
          <label>
            Total budget (INR)
            <input
              type="number"
              min={0}
              value={budget}
              onChange={(e) => setBudget(e.target.value)}
              placeholder="e.g. 60000"
              required
            />
          </label>
          <p className="wizard-step__hint">
            Recommendations may occasionally exceed this budget for a category if no cheaper option fits —
            we'll always show you by how much.
          </p>
          <button type="submit" disabled={!preferredStyle || !budget || submitting}>
            {submitting ? "Starting…" : "Generate my design"}
          </button>
        </form>
      )}

      {step === "generating" && jobId !== null && (
        <div className="wizard-step">
          <h2>Generating your design</h2>
          <JobProgress jobId={jobId} onDone={handleGenerateDone} onError={handleGenerateError} />
        </div>
      )}
    </div>
  );
}

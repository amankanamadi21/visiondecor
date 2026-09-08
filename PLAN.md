# VisionDecor — Master Project Plan & Decision Log

**Status:** Phase 0 — Requirements & Decisions (no code written yet)
**Last updated:** 2026-09-06
**Sources of truth:** `Updated_VisionDecor_7-21-26.docx` (IEEE paper), `visiondecorreportfinalprint.pdf` (Phase-I report, 45 pp.)

---

## Context

The team (Om Shukla, Nishant Yadav, Aman Kanamadi, Abhinav Dixit — CSE-DS, NHCE, guide Mrs. Swati Sehgal)
submitted a Phase-I report proposing **VisionDecor — Context-Aware AI Interior Design Recommendation
System with Layout Optimization**. Phase I is design-only: there is *no implementation yet*, no dataset
selected, no measured results. This plan converts the conceptual five-layer proposal into a buildable,
demonstrable, academically defensible system — built **one approved decision at a time**.

Hard rules for this project (user-imposed):
- No major architectural/product decision is made without explicit approval.
- No fabricated metrics. Anything unmeasured is labelled **"Not yet measured."**
- No scope creep beyond the report's stated scope.
- Mocked components must be labelled MOCK, with a stated replacement path.
- Report terminology is preserved even where implementation differs; differences are documented.

---

## A. Executive understanding

VisionDecor is a **decision-support** web application. A user uploads one photo of a real room, states
room type / preferred style / colour preference / budget, and the system returns a *context-aware*
redesign proposal: what the room currently contains, what style it currently is, what furniture and décor
to add or keep within budget, where to physically place it (computed, not guessed), a photorealistic
preview, and an explanation of *why*. The user then gives feedback and the system refines.

The differentiator vs. RoomGPT / Planner5D / Homestyler is **not** image beauty — it is the closed loop:
`real room → measured context → constrained optimisation → visualisation → feedback`. The demo must make
that loop visible, or the project reduces to "a nice prompt for Stable Diffusion".

---

## B. Complete system workflow (canonical, report-aligned)

```
USER INPUT (image + room type + style + colours + budget)
  → IMAGE PREPROCESSING            (validate, EXIF-strip, resize, normalise, quality gate)
  → ROOM ANALYSIS / COMPUTER VISION (furniture instances + architectural surfaces + free space + scale)
  → INTERIOR STYLE RECOGNITION      (style + confidence + alternative)
  → PREFERENCE + BUDGET ANALYSIS    (reconcile detected style vs desired style; allocate budget)
  → PERSONALIZED RECOMMENDATION     (catalog retrieval + constraint scoring + rationale)
  → LAYOUT OPTIMIZATION             (2D spatial model, hard constraints, weighted objective)
  → GENERATIVE VISUALIZATION        (structure-preserving diffusion, layout-conditioned)
  → FINAL DESIGN OUTPUT             (items + palette + budget breakdown + floor plan + render + score)
  → USER FEEDBACK                   (structured + free text)
  → DESIGN REFINEMENT               (preference deltas + constraint locks → re-run from Recommendation)
```

---

## C. Functional requirements (FR-1 … FR-7, from report §3.1) — implementation reading

| ID | Report requirement | What it actually means to build |
|----|---|---|
| FR-1 | Registration + preference collection | Auth, profile, preference form, persisted per-user |
| FR-2 | Room image analysis (YOLO) | Detection + segmentation + free-space + scale; structured JSON |
| FR-3 | Interior style recognition (CNN) | 6-class classifier + calibrated confidence + abstain path |
| FR-4 | Personalized recommendation | Catalog retrieval scored on style/colour/budget/space fit |
| FR-5 | Layout optimization | Real optimiser over a 2D room model with constraints + score |
| FR-6 | AI-based visualization | Structure-preserving generative render of the optimised design |
| FR-7 | Feedback & refinement | Structured feedback → preference/constraint deltas → re-run |

Implied-but-unstated FRs that must be added: **FR-8 design session persistence/history**,
**FR-9 design comparison (A/B)**, **FR-10 export/share of a design**. These are visible in the report's
narrative ("compare multiple design alternatives", "maintaining user histories") but missing from §3.1.

---

## D. Non-functional requirements (NFR-1 … NFR-8) — with the numbers the report omits

The report states NFRs qualitatively ("a few seconds", "reasonable timeframe"). To be testable these need
targets. **Proposed** (to be approved, not yet committed):

| NFR | Target to agree |
|---|---|
| Performance | Preprocess < 1 s; detection+segmentation < 5 s; style < 1 s; recommendation < 2 s; layout optimisation < 10 s; generative render — *depends entirely on D001 hardware* |
| Security | bcrypt/argon2 password hashing, httpOnly session or JWT, per-user object authorization, MIME+magic-byte image validation, size cap, env-var secrets, CORS allowlist |
| Privacy | Uploads private to owner; deletion cascades; EXIF/GPS stripped on ingest |
| Reliability | Every AI stage has an explicit failure mode + user-facing message; no silent fallback that misleads |
| Scalability | Long jobs run as queued background tasks, not blocking HTTP requests |
| Maintainability | Five report layers ↔ five code packages; each independently runnable and testable |
| Usability | Responsive; every AI output shows confidence and provenance |
| Compatibility | Modern browsers, desktop + mobile |

---

## E. Five-layer architecture (report §4.2) → code mapping

| Report layer | Report name(s) | Code package | Responsibility |
|---|---|---|---|
| 1 | Presentation / Data Acquisition | `frontend/` + `backend/api/` | Input, display, feedback |
| 2 | Image Analysis | `ai/room_analysis/` | Preprocess, detect, segment, free space, scale |
| 3 | Intelligence & Recommendation | `ai/style_recognition/`, `ai/recommendation/` | Style + recommendation |
| 4 | Layout Optimization | `ai/layout_optimization/` | Spatial model, constraints, optimiser, score |
| 5 | Visualization & Data Management | `ai/visualization/`, `database/` | Render + persistence |

Note: the report names Layer 1 inconsistently ("Data Acquisition Layer" in §1.1, "Presentation Layer" in
§4.2). See Report Issue R-08.

---

## F. AI/ML components — decision surface

1. **Object detection** — pretrained-COCO vs fine-tuned interior YOLO vs detection+segmentation hybrid.
2. **Architectural surfaces (wall/floor/window/door)** — *cannot* come from COCO YOLO; needs segmentation.
3. **Scale / room dimensions** — user-provided vs monocular-depth-estimated vs reference-object anchored.
4. **Style recognition** — scratch CNN vs transfer-learned CNN vs CLIP linear probe vs hybrid.
5. **Recommendation** — rule/constraint vs ML vs LLM vs hybrid retrieval+rules(+LLM for prose only).
6. **Layout optimization** — CP/exact vs GA vs Simulated Annealing vs grid search vs PSO vs heuristic.
7. **Generative visualization** — SD img2img vs ControlNet (depth / seg / MLSD) vs inpainting; local vs hosted.
8. **Feedback loop** — session-scoped vs profile-scoped vs weight-updating vs prompt-modifying.

---

## G. Data requirements

Needed, none yet selected:
- **Detection training/eval set** with interior classes incl. window, door, cabinet, shelf, lamp, curtain, rug.
- **Architectural segmentation** — an ADE20K-class model gives wall/floor/ceiling/window/door directly.
- **Style-labelled set** — 6 classes (Modern, Minimalist, Contemporary, Traditional, Industrial, Scandinavian).
- **Furniture catalog** with *category, dimensions (W×D×H), style tag, colour, price* — required by both
  the recommender and the optimiser. Dimensions are non-optional: without them layout optimisation is fiction.
- **Held-out demo room photos** (real photos of the team's own rooms) — the demo must not run on training data.

All dataset statistics, licences and counts to be recorded here **only after actually downloading them**.

---

## H. Frontend requirements
Landing → Auth → Dashboard → New Design (upload → room type → preferences → budget) → Analysis progress →
Room Analysis result → Style result → Recommendations → Layout → Visualization → Compare → Feedback →
Refine → History. Every AI panel shows confidence + provenance (`measured` / `estimated` / `user-provided`).

## I. Backend requirements
Auth, upload+validation, design-session lifecycle, background job execution for the AI pipeline,
per-stage result persistence, per-user authorization, structured error taxonomy, model loading/caching.

## J. Database requirements
Normalised relational schema; entity list to be approved (see PART 11 of the brief). Detection payloads
and layout geometry are natural JSON columns; the rest is relational.

## K. Evaluation requirements
Detection: Precision / Recall / F1 / mAP@50. Style: Accuracy / Precision / Recall / F1 / confusion matrix.
Layout: space utilisation, overlap violations = 0, clearance satisfaction, path connectivity, layout score,
**vs a random / greedy baseline**. Recommendation: budget compliance rate, style-match rate, space-fit rate.
Visualization: structural consistency (does the render keep windows/doors?) + user rating.
**Current status of every metric above: Not yet measured.**

## L. Known limitations (must appear in the final report, per report §VI)
Limited dataset diversity; subjectivity of design; no structural/electrical/ventilation awareness; degraded
performance on cluttered/dark/wide-angle photos; complex room geometry unsupported; generative renders may
show wrong proportions or hallucinated objects; **single-image metric scale is an estimate, not a measurement**;
decision-support only — not a replacement for designers or structural engineers.

---

## M. REPORT ISSUES REQUIRING DECISION

> Recorded, not silently corrected.

**R-01 — Table 2.1 columns are from an unrelated (fitness) project.**
Report says: comparison columns are *"AI Planning | Pose Detection | Nutrition Tracking | Adaptive Replan | RAG Coach"* for Planner5D / Homestyler / RoomGPT / DecoMind / VisionDecor.
Problem: Pose Detection and Nutrition Tracking belong to a workout/diet application. The table is a copy-paste from another domain and is indefensible in viva.
Correction: replace with *Room Image Analysis | Style Recognition | Budget-Aware Recommendation | Layout Optimization | Generative Visualization | Feedback Refinement*.
Impact: report edit only. **Decision required: YES.**

**R-02 — Table 4.1 contains a fitness formula.**
Report says: *"Personalized Recommendation | AI Recommendation | CR = Workout days logged / Planned workout days | CR (0–1)"*.
Problem: entirely unrelated to interior design. This is the single most damaging error in the report.
Correction: replace with the actual recommendation score (e.g. a weighted style/colour/budget/space-fit score) and the layout objective function, once approved.
Impact: report edit + it defines what we must actually implement. **Decision required: YES.**

**R-03 — Figure 2.1 is titled "Two-Stage Adaptive Replanning Pipeline".**
Problem: same unrelated-domain leakage; the caption does not describe a VisionDecor pipeline.
Correction: retitle to "VisionDecor Processing Pipeline" and redraw to match the approved workflow (§B).
Impact: figure redraw. **Decision required: YES.**

**R-04 — Frontend contradiction between the two documents.**
Paper (§Module 8) says the interface is **Streamlit**; the Phase-I report §3.3 and §4.3 say **HTML5/CSS3/JS/React.js + Flask**.
Problem: two different official answers to "what is the frontend?".
Correction: pick one and align both documents.
Impact: affects all frontend work. **Decision required: YES.**

**R-05 — AR is claimed as a VisionDecor capability in the paper but is out of scope in the report.**
Paper says VisionDecor overcomes prior work *"through context-aware optimization, adaptive feedback, augmented reality visualization…"*; report §1.3 lists AR as out of scope / future work.
Problem: claiming an unimplemented feature. **Decision required: YES** (recommend: delete the AR claim from the paper).

**R-06 — Paper §V "Results and Discussion" reports outcomes with no measurements.**
Paper says the style module *"demonstrates excellent performance"*, detection *"works satisfactorily"*, 80:20 split with fixed seed.
Problem: no dataset named, no numbers, nothing measured. This is the highest-risk section in a viva.
Correction: relabel as *"Planned Evaluation Methodology"* until real numbers exist, then replace with measured results.
Impact: paper rewrite. **Decision required: YES.**

**R-07 — YOLO is claimed to detect walls, windows, doors and free space.**
Report §2.4/§3.1/§4.3 all state the YOLO model identifies *"furniture items, room structures, walls, windows, doors, and available free space"*.
Problem: standard COCO-pretrained YOLO has **no** wall / window / door / floor / free-space classes, and free space is an area, not a bounding box — a detector cannot produce it. As written this requirement cannot be met by the stated method.
Correction: keep YOLO for furniture instances and add a **semantic segmentation** stage for architectural surfaces + floor-area/free-space; document as a method refinement.
Impact: core CV architecture. **Decision required: YES.**

**R-08 — Layer-1 and Layer-3/5 names differ between chapters.**
§1.1: "Data Acquisition Layer", "Recommendation Layer", "Visualization Layer".
§4.2/§4.3: "Presentation Layer", "Intelligence and Recommendation Layer", "Visualization and Data Management Layer".
Correction: adopt one canonical set throughout. **Decision required: YES (low stakes).**

**R-09 — No DFD and no Use Case diagram exist, despite §4.3 being titled "Data Flow Diagram / Use Case Diagram".**
Section 4.3 only re-narrates the architecture. The List of Figures contains only two figures. No ER diagram either.
Impact: a likely viva question and a Phase-II deliverable gap. **Decision required: YES.**

**R-10 — Room dimensions are assumed but never obtained.**
§2.5 and §4.3 state optimisation considers *"room dimensions, furniture sizes, and available floor space"*; nothing in the report explains how dimensions are derived from a single 2D photo.
Correction: define an explicit scale strategy and label every value `measured` / `estimated` / `user-provided`.
Impact: layout optimisation validity. **Decision required: YES.**

**R-11 — "Continuous improvement / continuous learning" vs. scope exclusion.**
§2.4, DG-13 and NFR-5 promise continuous refinement; §1.3 explicitly excludes *"continuous machine learning from live user data"*.
Correction: state precisely that refinement is **preference-state updating**, not model retraining.
**Decision required: YES.**

**R-12 — Undecided technology choices left as "or".**
"MySQL or PostgreSQL"; "TensorFlow, Keras, and PyTorch"; "AWS, Azure, or GCP"; "Stable Diffusion … with the additional help of the GAN model when necessary" (paper). Each needs one answer. **Decision required: YES.**

**R-13 — Citation and text integrity defects (paper).**
The literature review introduces a system as *"[7]"* and concludes *"…addresses all of these issues [12]"*; the abstract sentence *"…diffusion models proved to generate photorealistic visualizations of indoor spaces while recommendation."* is incomplete; several report paragraphs have dropped words (*"The findings classification through layout optimization"*, *"The findings support-based style recognition module"*, *"did not recommendation engine by demonstrating"*). Reference [15] is dated 2026 with arXiv ID 2602.10054 and [1] as *IEEE Access 2026* — both need verification before submission.
**Decision required: NO** (editorial), but must be fixed.

**R-14 — Certificate page appears to be missing the project title** (*"entitled Context- is the bona fide work"*). May be a PDF text-extraction artifact; verify against the printed copy. **Decision required: NO**, verify.

---

## N. Recommended MVP (proposal — not yet approved)
End-to-end, demoable, honest:
auth → upload+validate → room type/style/colour/budget → preprocessing → **COCO-YOLO furniture detection +
ADE20K segmentation for wall/floor/window/door + free-space mask** → **style classifier with confidence and
abstain** → **mock but schema-complete furniture catalog with real dimensions** → constraint-scored
recommendation with rationale + budget breakdown → **2D layout optimisation with a printed score breakdown
and a deterministic floor-plan render** → **one generative visualisation** → structured feedback → one
refined variant → **A/B compare** → history.

## O. Recommended final version (Phase-II complete)
MVP + fine-tuned interior-class YOLO with measured mAP + monocular-depth scale estimation with stated error
band + multi-variant generation + full evaluation suite (confusion matrix, mAP, layout-vs-baseline study,
budget-compliance study) + deployment + corrected report/paper + DFD/use-case/ER diagrams.

---

## P. Major decisions queue

| # | Decision | Status |
|---|---|---|
| D001 | Compute & deployment target (gates every AI choice) | **ASKED** |
| D002 | Report-issue resolutions R-01…R-14 | queued |
| D003 | CV strategy: detection vs detection+segmentation; pretrained vs fine-tuned; class list | queued |
| D004 | Room scale / dimension strategy | queued |
| D005 | Style recognition approach + dataset | queued |
| D006 | Furniture catalog strategy, schema, currency, price provenance | queued |
| D007 | Recommendation engine architecture; LLM usage boundary (if any) | queued |
| D008 | Layout optimisation algorithm | queued |
| D009 | Layout scoring model + weights | queued |
| D010 | Generative visualisation conditioning strategy | queued |
| D011 | Feedback architecture | queued |
| D012 | Backend framework, API architecture, job execution | queued |
| D013 | Database engine + schema approval | queued |
| D014 | Auth/session model | queued |
| D015 | Frontend stack + user journey approval | queued |
| D016 | Project structure approval | queued |
| D017 | Evaluation methodology + dataset strategy | queued |

---

## PROJECT DECISION LOG

### D001 — Compute & Deployment Target — **LOCKED 2026-09-06**
**Decision:** Option C — **Hybrid**. All layers except generative visualisation execute locally on CPU;
generative visualisation is delegated to an external GPU worker with a local render cache.
**Stated constraints:** team hardware is **CPU-only** (no NVIDIA GPU, no Apple Silicon).
Time to Phase-II demo: **under 1 month** (≈4 weeks from 2026-09-06, i.e. ~2026-10-04).
**Reason:** keeps every component that constitutes the academic contribution local, free, deterministic and
re-runnable in front of an examiner; offloads only the one expensive component that is not our contribution.
**Alternatives rejected:** A (local-only) — rejected because CPU-only makes local diffusion 3–10 min/image,
unusable in a live demo. B (cloud-hosted) — rejected on cost, credit-card requirement, and demo fragility.

**Consequences forced by D001 (must be honoured by all later decisions):**
1. **No model training beyond a classifier head.** CPU-only + 4 weeks rules out YOLO fine-tuning entirely.
2. **Detection must use pretrained weights.** This makes Report Issue R-07 unavoidable rather than optional —
   architectural surfaces must come from a pretrained segmentation model, not from a trained detector.
3. **Stable Diffusion cannot run in the request path.** It must be a queued background job served by the
   remote worker, with a cache, or the demo stalls.
4. **The deterministic floor-plan render must be a first-class output**, not a debug view — it is the only
   visualisation guaranteed to be available instantly and offline.

**⚠ Conflicts with the submitted documents created by D001 — must be documented, not hidden:**
- Report §3.3 recommends GPU-equipped systems for training. We will not train detection models. The report's
  claim of a trained YOLO model must be restated as *pretrained / transfer-learned*.
- Paper §V "Results and Discussion" claims measured detection and style performance (see R-06). With CPU-only
  in 4 weeks, only some of those numbers can be genuinely produced. Everything else stays "Not yet measured."
- Paper §Module 1 "Data Collection" implies training on a large curated corpus. Not achievable; must be
  restated to describe the evaluation set and the pretrained models actually used.

### D002 — 4-Week Scope Contract — **LOCKED 2026-09-06** (as **S2′**)
**Decision:** Full pipeline built first; evaluation added last and kept cuttable; detection metrics come from
**pre-annotated public datasets, with zero hand-labelling**.
**Reason:** user correctly identified that hand-annotation was the only manual-labour item; public annotated
datasets remove it, so S2 now costs roughly what S1 did.
**Team constraint:** solo developer.
**Alternatives rejected:** S1 (leaves detection unmeasured for no saving); S3 (depth estimation + multi-variant
generation not achievable solo on CPU in 4 weeks, and not cleanly cuttable).

### D003 — Generative Render Provider Strategy — **LOCKED 2026-09-06**
**Decision:** Provider-agnostic `RenderProvider` interface with automatic failover:
`Gemini 2.5 Flash Image → Cloudflare Workers AI → Hugging Face → local cache → deterministic floor plan`.
**Reason:** free tiers have daily caps; a demo has one chance. ~1 extra day of work.
**⚠ Attached condition (non-negotiable, per brief PART 15):** only Gemini performs true *image editing*.
The fallbacks are text-to-image and therefore **degrade structural fidelity** — a fallback render may not
preserve the user's actual windows and doors. The UI **must** label which provider produced each image and
warn when the structure-preserving path was unavailable. This must never be hidden.
**Alternatives rejected:** single-provider (fragile); local CPU Stable Diffusion (3–10 min/image).

### D004 — Dataset Strategy — **LOCKED 2026-09-06** (detection + classes; style set pending)
**Detection evaluation:** SUN RGB-D **and** COCO val2017 indoor subset, **both reported**.
*Reason:* same eval code run twice; the gap between home-benchmark and real-indoor performance is the most
interesting finding in the evaluation and quantifies Report Issue R-07 as a measured result rather than a
criticism. *Constraint:* a COCO-pretrained detector can only be scored on the intersecting label space
(≈ chair, sofa/couch, bed, table, tv, sink) — this must be stated plainly in the report.
**Style classes:** keep **all six** FR-3 classes. Modern/Contemporary confusion is expected and will be
**reported as a measured finding**, and is the justification for the confidence-and-abstain mechanism.
*Alternatives rejected:* dropping Contemporary (buys accuracy by changing the question; contradicts FR-3).

### D006a — Design-Principle RAG — **LOCKED 2026-09-06**
**Decision:** **Constrained RAG** over a curated interior-design-principles corpus, embeddings in
**pgvector** inside the existing PostgreSQL instance.
**Mechanism:** retrieval supplies the *principles*; computation supplies *all numbers*; the LLM only
**phrases** them; retrieved sources are **displayed in the UI** so grounding is verifiable.
**Reason:** report §4.3 already claims *"the recommendation layer also incorporates design knowledge and
interior design principles"* — a claim that was otherwise **unimplemented**. This closes an existing gap
rather than opening a new one, and makes rationales citable (*"90 cm walkway maintained — clearance
principle CP-04"*), which strengthens the explainability requirement in brief PART 16.
**Alternatives rejected:** retrieval-only (more reproducible, but could not honestly be called RAG in the
report); no RAG (leaves §4.3's claim unimplemented).
**Infrastructure note:** pgvector needs only a different Postgres image + `CREATE EXTENSION vector`.
**Embedding model (implementation choice, swappable):** local `all-MiniLM-L6-v2` sentence-transformer
(~80 MB, CPU-fast, 384-dim) — chosen over a hosted embedding API for offline reproducibility.

**⚠ Amends D007a:** the LLM now also phrases rationale prose. The hard boundary is **unchanged** — it still
never selects furniture, sets prices, or decides positions, and every number it renders is computed upstream.

**⚠ Amends D002 and D004 — scope traded:** detection **mAP evaluation is CUT** to fund the ~1–2 days.
Scope reverts from S2′ to **S1′ + RAG**.
**Real cost of that cut, stated plainly:** Report Issue R-07 ("YOLO cannot detect walls/windows/doors") will
**no longer be quantified**. It reverts from a measured finding to a documented limitation.
**Cheap mitigation (~1 hour, do it):** run the detector over the ~20 demo room photos and report per-class
detection counts plus observed failure modes as a **qualitative** appendix. Explicitly **not** mAP, and
must never be labelled as such.

### D007a / D011a — LLM Usage Boundary — **LOCKED 2026-09-06** *(amended by D006a)*
**Decision:** Recommendation rationale is generated by **deterministic templates populated from the actual
score components**. A free text LLM is used **only** to parse free-text user feedback into structured,
schema-validated preference deltas.
**Hard boundary:** the LLM never selects furniture, never sets or alters prices, never decides positions.
**Reason:** brief PART 7 prioritises explainability and reproducibility; a template citing real score values
is provable in viva, LLM prose is not.

### D005 — Style Recognition Approach — **LOCKED 2026-09-06**
**Decision:** **CLIP-RN50 zero-shot** classification over the six FR-3 style labels, with a documented
upgrade path (logistic-regression head over the same frozen features, ~30 s compute) if measured accuracy
is unacceptable. Evaluated against the **Kaggle Houzz interior-design-styles set used purely as a test set**.
**Reason:** satisfies the "no training" constraint; CLIP-RN50's image encoder *is* a convolutional network,
so FR-3's "CNN-based" wording remains truthful; softmax over the label space yields the exact
confidence + alternative output specified in brief PART 4; zero training means zero train/test contamination.
**Alternatives rejected:** zero-shot with no upgrade path (no remedy if accuracy is poor);
frozen-features + head now (better expected accuracy, but adds split management the user does not want).
**⚠ Not yet measured:** zero-shot accuracy on six confusable interior styles is unknown until run.
No number is to be quoted anywhere until produced.

### D-CADENCE — Decision Pacing — **LOCKED 2026-09-06**
**Decision:** Batch remaining decisions by module, approved immediately before each module is built.
**Batches:** ① Backend foundation (D012 backend, jobs, D013 database, D014 auth, D016 structure)
② Intelligence (D006 catalog, D007 recommendation, D008 optimiser, D009 scoring weights)
③ Interface & proof (D010 render conditioning, D011 feedback, D015 frontend/journey, D017 evaluation)
**Reason:** solo developer, 4 weeks; front-loading all thirteen decisions would consume build time and force
downstream choices before upstream results exist.

## CURRENT ARCHITECTURE

```
Frontend        : React + TS + Vite — full journey: auth → new design →     [Batch 1-3, live-verified]
                  sample-room gallery/upload → preferences → results →
                  feedback loop, all wired to the real API
Backend         : Flask, app factory, thread-based JobRunner                [LOCKED, Batch 1]
Database        : PostgreSQL 16 + pgvector, 16 tables + prefs columns       [LOCKED, Batch 1, extended Batch 2]
Auth            : JWT in httpOnly cookie + CSRF double-submit               [LOCKED, Batch 1]
AI runtime      : LOCAL, CPU-only                                           [LOCKED by D001]
Computer Vision : Pretrained detection + segmentation — NOT WIRED           [deferred by D018/D022; real
                  (existing-furniture detection only — room dimensions       photos always treated as empty,
                  are now solved for real photos, see D004 below)            disclosed honestly in the UI]
Style           : CLIP-RN50-quickgelu zero-shot — LIVE-WIRED, measured      [LOCKED D005; runs for real on
                  40.2% accuracy (5/6 classes; no Minimalist ground truth     every genuine photo upload, not
                  exists in the eval dataset). Live classifier stays         just a standalone module]
                  zero-shot (a trained head measured 59.8% but can't
                  predict Minimalist at all, so isn't deployed)
Room dimensions : User-provided (D004, LOCKED 2026-09-08) — width/length     [Unlocks full recommendation +
                  form fields for a real photo, scale_source=USER_PROVIDED.  layout for real photos, not just
                  Live-verified end-to-end: real photo -> real style ->      style — see D004 resolution notes]
                  real recommendation -> real layout, all constraints met
Recommendation  : Deterministic scoring + constrained RAG rationale        [IMPLEMENTED, live-verified]
Knowledge base  : 40 design principles in pgvector, cited in the UI         [LOCKED D006a, seeded + verified]
Optimization    : Simulated Annealing, hard constraints + 5-term score     [IMPLEMENTED, live-verified,
                                                                              beats both baselines — see D025]
Feedback loop   : Rule-based parser (Gemini-primary, untested) + re-run    [IMPLEMENTED, live-verified]
Visualization   : Floor plan (SVG) always on; Gemini image editing          [floor plan LIVE-VERIFIED; Gemini
                  behind a provider chain, degrades to none gracefully      IMPLEMENTED BUT NOT LIVE-TESTED —
                                                                              no API key yet, see D003/D023]
Deployment      : Hybrid — local app, hosted image API                     [LOCKED by D001/D003]
Training        : NONE (pretrained + zero-shot only)                       [user constraint 2026-09-06]
```

**What "IMPLEMENTED" / "live-verified" means as of Batch ③:** the full user-facing loop — register through
feedback-driven re-generation — was driven through the real running frontend+backend (not a dev script) and
produced correct results at every step, with 74/74 automated tests passing. The one component that exists in
code but has never actually been exercised against a live API is the Gemini image-editing call itself; this
is stated plainly here and in the code, not implied to be verified.

## EMERGING PROJECT THESIS (for the report and viva)

> VisionDecor's contribution is **not a new model**. It is the context-aware integration of pretrained
> perception with a **constrained layout optimiser**, plus honest provenance labelling of every value the
> system reports. Pretrained and zero-shot components were chosen deliberately to avoid overfitting small
> style datasets and to keep results reproducible.

This is a coherent and defensible position. It also correctly locates the original algorithmic work in the
**layout optimisation engine (D008/D009)**, which remains built from scratch — and which therefore deserves
the largest share of the 4 weeks.

## CPU FEASIBILITY AUDIT (evidence behind the D001 consequences)

| Stage | CPU viability | Note |
|---|---|---|
| Preprocessing (OpenCV) | ✅ trivial | milliseconds |
| YOLO (small, COCO, inference) | ✅ viable | sub-second to ~1.5 s/image |
| Semantic segmentation (small ADE20K model) | ✅ viable | a few seconds/image |
| Style classifier — frozen CNN features + trained head | ✅ viable | head trains in seconds; feature pass is the only cost |
| Style classifier — full CNN fine-tune | ⚠ marginal | possible but eats days of the 4 weeks; not recommended |
| Monocular depth (small model) | ⚠ viable but slow | adds seconds per image; optional |
| Layout optimisation (Simulated Annealing, numpy) | ✅ ideal | pure CPU, sub-second to seconds |
| Recommendation scoring | ✅ trivial | |
| Floor-plan render (SVG/matplotlib) | ✅ trivial | |
| **Stable Diffusion + ControlNet** | ❌ **not viable in-request** | minutes per image on CPU → must be offloaded/cached |
| **YOLO fine-tuning** | ❌ **not viable** | days on CPU |

*Timings above are order-of-magnitude engineering expectations, not measurements. To be measured on the
team's actual machines in Phase 1 and recorded here.*

## RENDER-PATH RESEARCH (verified 2026-09-06, for D002)

**Terminology correction for the report/viva:** an *LLM* is a text model and cannot generate images. The
correct term for this component is a **hosted image generation / image editing model**. Some are multimodal.

Genuinely-free options confirmed (verify limits again before submission — free tiers move):

| Provider / model | Free allowance | Card? | Fit for VisionDecor |
|---|---|---|---|
| **Gemini 2.5 Flash Image** ("Nano Banana") | ~500 req/day, 1024×1024 | **No** | **Best.** Does *image editing* — original room photo in, edited photo out. Structure preserved by construction rather than by ControlNet. |
| Cloudflare Workers AI (FLUX / SDXL) | 10,000 neurons/day | **No** | Mostly text-to-image; weak img2img, no ControlNet on the free serverless path → weaker structure preservation |
| Hugging Face Inference | monthly credit allotment | No (token) | Viable fallback; rate-limited |

Sources: aifreeapi.com (Gemini free-tier limits + image tier), toolfreebie.com (Workers AI neurons),
runflow.io (caveat: most "free image API" listings are trials/wrappers).

**Architectural consequence:** using an image-editing model replaces `SD + ControlNet` and removes the
Colab-GPU-worker component entirely (~3–4 days of solo build time). The render path becomes an HTTP call
plus a permanent local cache.

**Three costs of this choice, to be recorded in the report if adopted:**
1. **Report deviation** — report specifies Stable Diffusion. Must be documented per PART 12/25, not glossed.
2. **Privacy conflict with NFR-3** — report states user data is not shared with unauthorized parties;
   sending room photos to a third-party API contradicts this unless disclosed in-UI and NFR-3 is amended.
3. **Reproducibility** — a hosted model can change or be deprecated; a pinned local checkpoint cannot.
   The render cache partially mitigates this.

**Separate, approved-in-principle use of a free *text* LLM (belongs to D007/D011, not D002):** parsing
free-text feedback into structured preference deltas, and generating rationale prose. Hard boundary — the
LLM must never select furniture, set prices, or decide positions. Those stay with the optimiser.

---

---

# ▶ WHAT WE BUILD NOW — Batch ① : Backend Foundation (Week 1)

### Batch ① decisions — **LOCKED 2026-09-06**
| ID | Decision | Rejected |
|---|---|---|
| **D012** | **Flask** backend | FastAPI — better ergonomics but a report §3.3 deviation; pipeline is CPU-bound so async buys little |
| **Jobs** | **Background thread + `jobs` table**, frontend polls | RQ+Redis (a day of setup, another process to keep alive during viva); synchronous+SSE (a 30 s held request reads as a hang) |
| **D013** | **PostgreSQL** (SQLite retained as SQLAlchemy fallback) | SQLite-only (contradicts §3.3); MySQL (weaker JSON, and our payloads are JSON-shaped) |
| **D014** | **JWT in an httpOnly cookie** + CSRF token | JWT in localStorage (XSS-readable); server session (report leans JWT) |

> **Stated limitation, to be written into the report against NFR-5:** the thread-based job runner is
> single-process and does not scale to concurrent users. This is a deliberate trade for demo reliability.
> Migration path: swap the runner for RQ+Redis behind the same `JobRunner` interface. Not fabricated as scalable.

### Database schema (16 tables) — approve with this plan

**Identity & session**
- `users` — id PK · email UNIQUE(idx) · password_hash · name · created_at
- `user_preferences` — id PK · user_id FK→users(idx) · default_style · default_colors JSONB · default_budget · currency · updated_at
- `design_sessions` — id PK · user_id FK→users(idx) · room_type · title · status · created_at · updated_at
- `jobs` — id PK · session_id FK(idx) · stage · status · progress · error_code · error_message · started_at · finished_at

**Layer 2 — Room analysis**
- `room_images` — id PK · session_id FK(idx) · original_path · processed_path · width · height · file_hash(idx) · quality_flags JSONB · created_at
- `room_analyses` — id PK · image_id FK(idx) · floor_polygon JSONB · free_space_ratio · room_width_cm · room_length_cm · **`scale_source` ENUM(user_provided | estimated | unknown)** · model_versions JSONB · created_at
- `detected_objects` — id PK · analysis_id FK(idx) · class_label · confidence · bbox JSONB · `source` ENUM(detection | segmentation) · area_px

**Layer 3 — Intelligence**
- `style_predictions` — id PK · analysis_id FK(idx) · predicted_style · confidence · alternatives JSONB · model_name · abstained BOOL
- `furniture_catalog` — id PK · name · category(idx) · style_tags JSONB · color · price · currency · **width_cm · depth_cm · height_cm** · image_url · **`data_source` (= 'MOCK')** · created_at
- `recommendations` — id PK · session_id FK(idx) · iteration · total_cost · budget · within_budget BOOL · palette JSONB · created_at
- `recommendation_items` — id PK · recommendation_id FK(idx) · catalog_item_id FK · `action` ENUM(add|keep|remove|replace) · score_breakdown JSONB · rationale · quantity

**Layer 4 — Layout**
- `layouts` — id PK · recommendation_id FK(idx) · layout_score · score_breakdown JSONB · constraints_satisfied JSONB · algorithm · iterations · created_at
- `layout_objects` — id PK · layout_id FK(idx) · catalog_item_id FK NULL · label · x_cm · y_cm · width_cm · depth_cm · rotation_deg · is_existing BOOL

**Design knowledge (D006a)**
- `design_principles` — id PK · `code` UNIQUE(idx) e.g. 'CP-04' · category ENUM(clearance|style|color|lighting|room_type) · title · body TEXT · applies_to_room_types JSONB · applies_to_styles JSONB · source_note · **`embedding vector(384)`** · created_at

**Layer 5 — Visualization & feedback**
- `visualizations` — id PK · layout_id FK(idx) · provider · image_path · prompt_used · **structure_preserving BOOL** · cache_hit BOOL · created_at
- `feedback` — id PK · session_id FK(idx) · recommendation_id FK NULL · raw_text · structured_deltas JSONB · rating · created_at

Three columns exist purely to keep the system honest and are **not optional**: `room_analyses.scale_source`
(brief PART 3 — never present an estimate as a measurement), `furniture_catalog.data_source` (brief PART 6 —
prices are mock, never implied real), `visualizations.structure_preserving` (D003 — the UI must disclose when
a fallback provider produced a render that may not preserve the real windows and doors).

### Week 1 build order
1. Repo scaffold per the structure above · `.env.example` · `docker-compose.yml` using the
   **`pgvector/pgvector:pg16`** image (D006a) · `CREATE EXTENSION vector` in the first migration
2. SQLAlchemy models + Alembic migration for all 16 tables (incl. `design_principles.embedding vector(384)`)
3. Flask app factory — env-driven config, CORS allowlist, central error taxonomy (brief PART 15)
4. Auth — register / login / logout / me; argon2 hashing; JWT in httpOnly cookie + CSRF; per-user authorization helper
5. Upload — MIME **and magic-byte** validation, size cap, EXIF/GPS strip, hash dedupe, per-user storage paths
6. `JobRunner` — thread pool writing to `jobs`, plus `GET /api/jobs/<id>` for polling
7. React + Vite + TS scaffold — auth pages, protected routes, upload screen, job-progress component
8. Seed script for `furniture_catalog`, every row stamped `data_source='MOCK'`
9. Tests — auth flow, upload rejection cases, job lifecycle
10. README with run + verify instructions

**Then STOP for Batch ② decisions** (catalog design, recommendation engine, optimiser, scoring weights).
No Layer 3/4/5 code is written before those are locked.

### Verification for Batch ①
```bash
docker compose up -d db && alembic upgrade head     # schema applies cleanly
pytest                                              # auth, upload validation, job lifecycle
python scripts/seed_catalog.py                      # catalog populated, all rows data_source='MOCK'
flask run  &  npm run dev                           # then, in the browser:
```
Manual checks: register → login → confirm the JWT cookie is `HttpOnly` in devtools and unreadable from the JS
console · upload a valid JPEG and see a `design_session` + `room_image` row · upload a `.txt` renamed to
`.jpg` and get a clean rejection, not a stack trace · upload a 50 MB file and get a size error · confirm
a second user cannot fetch the first user's session by ID · start a stub job and watch progress poll to done.

**Nothing in Batch ① is AI.** No accuracy claims arise from it, and none will be made.

**Batch ① status: COMPLETE 2026-09-06.** All 16 tables migrated (verified via `\dt`/`\dx`), 21/21 tests
passing (3 consecutive runs), 30 catalog rows seeded (`data_source='MOCK'` verified), full live curl E2E
pass (register → session → upload → job poll → done, plus all rejection/authorization paths), frontend
`tsc` clean, CORS credentialed cross-origin confirmed. One race condition found and fixed: background jobs
outliving a test's cleanup (fixed by draining `JobRunner` before table truncation — see `tests/conftest.py`).

---

### D018 — Build Sequencing: Optimizer/Recommendation Core vs. Real CV First — **LOCKED 2026-09-06**
**Decision:** Option A. Build the recommendation engine and layout optimiser now, against **fixture**
`RoomAnalysis`/`StylePrediction` data conforming exactly to the Batch 1 schema. Real CV integration
(detector + segmentation model selection/wiring) is deferred to a later, isolated task.
**Reason:** the optimiser is the project's one from-scratch algorithmic contribution and the piece most
likely to be scrutinised in viva; it should get the most iteration time and can be built/tested without any
external model risk. Real CV later only has to populate the same rows — zero rework.
**Alternatives rejected:** B (CV first — burns days before the riskiest component is even started);
C (2-day timebox — an artificial deadline invites rushing the CV integration either way).
**⚠ Guardrail (brief PART 34.14/15 — never fake AI functionality):** fixture room-analysis data lives ONLY
in a clearly separate, clearly labeled dev path (`ai/room_analysis/fixtures.py` + a dev-only seeding script).
The production recommendation-trigger endpoint reads whatever real `RoomAnalysis`/`StylePrediction` rows
exist for a session and raises an explicit "room analysis not available yet" error if none exist — it never
silently substitutes fixture data into a real user's pipeline.

### D019 — Budget Model — **LOCKED 2026-09-06**
**Decision:** Option A. Single total budget per design; the recommendation engine allocates internally
across furniture/decor/lighting categories and shows the breakdown afterward. An item may be shown even if
it exceeds budget, **always clearly flagged** (e.g. "₹1,200 over budget"), never silently hidden.
**Currency: INR**, confirmed (this had been set as an undiscussed Batch 1 code default — flagged and now
explicitly approved rather than left silent, per the no-silent-decisions rule).
**Alternatives rejected:** B (hard-capped — a required category with no in-budget item shows nothing, reads
as broken in a live demo); C (per-category sub-budgets — real UX cost not justified for a 4-week solo MVP).

### D020 — Layout Optimization Algorithm — **LOCKED 2026-09-06**
**Decision:** Option A. **Simulated Annealing**, fixed random seed (reproducibility, matching the report's
own "fixed random seed" ethos), rotation restricted to {0°, 90°, 180°, 270°}.
**Reason:** handles the mixed continuous(x,y)/discrete(rotation) space naturally, fast on CPU for 5–15
objects, easy to explain in viva, and produces a convergence curve as evaluation evidence for free.
**Alternatives rejected:** B (GA — population overhead unjustified at this problem size); C (grid search —
rotation makes the grid combinatorially expensive; quality capped by grid coarseness); D (OR-Tools CP-SAT —
academically attractive and free, but the soft multi-term objective is awkward to encode in a CP formulation).
**Refinement over the brief's example formula:** hard constraints (no overlap, in-bounds, door/window
clearance, minimum walkway width) are enforced structurally — the optimiser rejects any candidate violating
them outright, they are never "weighed against" the soft objective. Overlap is never a matter of degree.

### D021 — Layout Scoring Weights — **LOCKED 2026-09-06** (per brief: required explicit user approval)
**Formula (over constraint-satisfying candidates only):**
`LayoutScore = w1·SpaceUtilization + w2·Accessibility + w3·MovementFlow + w4·VisualBalance + w5·Functionality`
**Weights approved: Balanced** — `w1=0.25 (space_utilization), w2=0.25 (accessibility), w3=0.20 (movement_flow),
w4=0.15 (visual_balance), w5=0.15 (functionality)`.
**Reason:** no single factor dominates — the safest default across the room types VisionDecor supports.
**Alternatives available but not chosen:** Space-maximizing (0.40/0.15/0.15/0.15/0.15), Walkability-first
(0.15/0.30/0.30/0.10/0.15) — both recorded here in case a later demo room type warrants revisiting this.

---

# ▶ WHAT WE BUILD NOW — Batch ② : Intelligence (Recommendation + Layout Optimization)

**New dependency:** `sentence-transformers` (local `all-MiniLM-L6-v2`, CPU, ~80MB) for D006a RAG embeddings —
pulls in a CPU-only PyTorch wheel. No training occurs; this is inference-only, consistent with D001/D005.

### Design principles corpus (D006a)
A curated ~40-principle knowledge base (`ai/recommendation/principles_data.py`), categories: clearance,
style, color, lighting, room_type. Embedded once via a seed script (`scripts/seed_principles.py`) into
`design_principles.embedding` (pgvector). Retrieval is cosine similarity over these vectors, filtered by
`applies_to_room_types`/`applies_to_styles` where set. Every citation in a rationale references a real
`code` (e.g. "CL-04") that resolves to an actual stored principle — never an invented one.

### Recommendation engine (`ai/recommendation/`)
For each furniture category the room needs, catalog items are scored on: style match (tag overlap with
detected + preferred style), color match, budget fit (against the category's internal allocation), and a
coarse space-fit check (item footprint vs. available free space; fine-grained placement is the optimiser's
job, not this stage's). `score_breakdown` stores every component; `rationale` is a **deterministic template**
built from those components plus any cited principles — an LLM phrasing pass is optional and only engages if
`FEEDBACK_LLM_PROVIDER`/`FEEDBACK_LLM_API_KEY` are set (empty by default), so the system works correctly
with zero external keys and zero cost, per brief PART 26.

### Layout optimization (`ai/layout_optimization/`)
Room + furniture represented as a simple 2D model (dataclasses, cm units). Simulated Annealing per D020,
weights per D021. Hard constraints checked on every candidate move; a violating move is always rejected
regardless of temperature. `layouts.score_breakdown` stores only the five soft terms + their weighted sum;
`layouts.constraints_satisfied` stores the hard-constraint pass/fail map separately (brief PART 16 wants
these shown as distinct things, not conflated into one number).

### Verification for Batch ②
- `pytest` — optimiser: no overlap in any accepted state (property test across many random rooms), all
  furniture stays in-bounds, score is non-decreasing across the accepted-move sequence, same seed → same
  result. Recommendation: every item within (or honestly flagged over) budget, every rationale cites at
  least one real `design_principles.code` where a relevant principle exists.
- A CLI entry point (`python -m ai.layout_optimization.cli <fixture-name>`) that runs the optimiser on a
  named fixture room and prints the final layout + score breakdown — so a real run can be shown, not just
  asserted by a test.

### Batch ② status: COMPLETE 2026-09-07
Recommendation engine, RAG retrieval, Simulated Annealing optimiser, hard constraints, and the CLI runner
are implemented and verified against real fixture data (all four room fixtures produce fully
constraint-satisfying layouts). 21/21 new tests pass (10 layout, 5 recommendation, 6 design API), full
suite 42/42 (stable across repeated runs, ~14s). Full live HTTP walkthrough also performed against the real
running server (not just the test client): register → session → set preferences → attach fixture → POST
generate → poll job (10%→55%→100%) → GET recommendation (all items correctly stamped `data_source: MOCK`)
→ GET layout (all 5 hard constraints satisfied). Both honest failure modes confirmed live: generating with
incomplete preferences yields `error_code: preferences_incomplete`; generating with no room analysis yields
`error_code: room_analysis_missing` — neither a generic 500 nor a silent fixture fallback.
DB wiring completed: `design_sessions` gained `preferred_style`/`preferred_colors`/`budget`/`currency`
columns (an omission from Batch 1 — these are needed to trigger a recommendation and had nowhere to live;
not a new architectural decision, just completing FR-1/FR-4's data model). `JobStage.GENERATE_DESIGN` added
(recommendation + layout run as one combined job, not two chained ones — a documented simplification, see
`backend/models/session.py`). New API: `PATCH /api/sessions/<id>` (preferences), `POST
/api/sessions/<id>/generate`, `GET /api/sessions/<id>/recommendation`, `GET /api/sessions/<id>/layout`.

**⚠ Operational incident, resolved:** two consecutive full test-suite runs stalled for ~61 minutes each
(36/36 still passed — correctness was never in question) while wall-clock time vastly exceeded actual CPU
time used (~25s CPU across a 61-minute run). Root cause: `SentenceTransformer(...)` contacts huggingface.co
to check for updates on every load even when the model is already cached locally, and a degraded connection
at that moment caused a very long stall. Fix: `ai/recommendation/embeddings.py` now sets
`HF_HUB_OFFLINE=1`/`TRANSFORMERS_OFFLINE=1` before first load, forcing fully offline loading from cache —
consistent with D001/D006a's "runs offline, no network dependency" intent, which this had accidentally
violated. Confirmed stable across 3 subsequent runs (~14s each). No further action needed, but if a fresh
machine has never downloaded the model, that one-time download still needs network access first.

---

### D022 — Frontend Demo Path (real CV deferral) — **LOCKED 2026-09-07**
**Decision:** Sample rooms, delivered through the **real upload mechanism** — the user picks a sample room
image and it goes through the exact same multipart upload endpoint a real photo would. The backend
recognizes known sample images by content hash and auto-attaches the matching fixture's `RoomAnalysis`.
Real CV integration remains a stretch goal only if time allows after this batch, not a commitment.
**Reason:** makes the demo interaction indistinguishable from real use (no separate "pick a fixture"
selector), while keeping D018's CV deferral intact so the newly-proven optimiser core isn't put at risk.
**Guardrail carried forward:** every place the UI shows analysis-derived content must display that it came
from a sample room (sourced from `RoomAnalysis.model_versions.source == "fixture"`, already in the schema) —
never presented as if the system analyzed the user's own photo.

### D023 — Generative Render Conditioning — **LOCKED 2026-09-07**
**Decision:** A deterministic translator turns the optimiser's actual `LayoutObject` rows into a natural-
language edit instruction (e.g. *"a glass coffee table centered in front of the sofa..."*), sent to the
image-editing provider (D003) together with the original photo.
**Reason:** keeps the generated image honestly downstream of the computed layout rather than a vibe-only
prompt; respects brief PART 9's "layout is source of truth, image is impression" separation.
**Disclosure requirement (restates an existing brief §VI limitation, not a new one):** UI must state the
photorealistic render is an artistic impression guided by the layout, not a guaranteed pixel-accurate
depiction — the floor-plan view remains authoritative.

### D024 — Feedback Text-Parsing Backend — **LOCKED 2026-09-07**
**Decision:** Gemini (text), reusing the same API key as D003's image generation, as the primary parser.
**Implementation addition (not re-opening D024, a resilience detail):** when no Gemini key is configured
(the default — `.env.example` ships it blank), fall back to a local rule-based parser (keyword/pattern
matching against the current recommendation's item names and a small set of intents) rather than the
feature silently doing nothing. This mirrors the D003 provider-failover philosophy: degrade gracefully,
never fail silently, disclose which path produced the result.

### D025 — Evaluation Scope — **LOCKED 2026-09-07**
**Decision:** Layout-vs-baseline study (optimiser vs. random-placement and greedy/first-fit baselines,
across all 4 fixtures) + recommendation compliance study (budget compliance rate, style-match rate across
many synthetic preference combinations). Both genuinely measurable with code that already exists.
**Still "Not yet measured" after this batch:** style/detection accuracy (real CV not in scope this batch,
per D022) — stated honestly, not implied.

---

# ▶ WHAT WE BUILD NOW — Batch ③ : Interface & Proof

Build order (each depends on the last except where noted independent):
1. **Sample-room registry** (`ai/room_analysis/sample_rooms.py`) + 4 placeholder images + upload-endpoint
   auto-attach. *Unblocks everything else being demoable through the real UI.*
2. **Deterministic floor-plan renderer** (`ai/visualization/floorplan.py`) — pure Python, no API key, always
   available; this is the D003 fallback of last resort and a real deliverable in its own right.
3. **RenderProvider abstraction + Gemini implementation + cache** (`ai/visualization/`) — D003/D023. Degrades
   to floor-plan-only when no `GEMINI_API_KEY` is configured (the default); this must not block the rest of
   the demo, only the photorealistic layer of it.
4. **Feedback service** (`backend/services/feedback_service.py`) — D024, Gemini-primary + rule-based fallback,
   producing `structured_deltas` that adjust the session's preferences/budget for the next `generate` run.
   **Never retrains or fine-tunes anything** (restates R-11: this is preference-state updating, not learning).
5. **Evaluation scripts** (`evaluation/`) — D025, pure Python, no new dependency.
6. **Frontend**: sample-room gallery step, a results page (recommendation cards with rationale + citations,
   floor plan, generated image with its provider/fidelity disclosure, budget breakdown), and a feedback box
   feeding the refinement re-run.

**New dependency this batch:** none required for items 1, 2, 5, 6. Item 3 needs `google-genai` (or direct
HTTP calls — decided during implementation) and a `GEMINI_API_KEY` the user must obtain themselves (free,
no card) — the system must work correctly with this key absent, just without photorealistic rendering.

### Batch ③ status: COMPLETE 2026-09-07 (backend + frontend)
All 6 build-order items complete. 74/74 tests passing (stable, ~40s). Frontend `tsc` clean. Full live
walkthrough performed against real running Flask + Vite servers (not just the test client): register →
create session → fetch a sample-room image from Vite exactly as the browser would → upload it to the
backend (auto-recognized, `is_sample_room: true`) → set preferences via `PATCH` → `generate` → poll job →
fetch recommendation (budget-compliant, every item stamped `data_source: MOCK`, real principle citations) →
fetch layout (all 5 hard constraints satisfied, valid `<svg>` floor plan, `visualization: null` since no
Gemini key yet) → submit feedback ("make it more industrial, remove the plant") → confirmed style shifted to
Industrial, plant removed, coffee table and lamp both re-matched to the new style, iteration incremented to
3. This is the first point in the project where the complete pipeline was driven end-to-end through the
actual UI's code path, not a dev script.

**⚠ Performance bug found and fixed during this live walkthrough:** first live `generate` call took ~32s
wall-clock — traced to `retrieve_principles` (a real embedding call) running once per CATALOG CANDIDATE
scored (~20–30 embedding calls per generation) instead of once per category. Fixed by hoisting retrieval to
once per category (`_retrieve_category_principles`, `ai/recommendation/scoring.py`); confirmed the same
generation now completes in **5s** on a warm process, verified live before and after the fix, not just by
code inspection. All 74 tests still pass after the change.

Items 1–5 complete and tested. Notable build decisions/findings:

- **`google-genai` version correction:** initially pinned 1.3.0 from memory; the installed package was
  missing `ImageConfig`/current fields entirely. Checked PyPI directly, found 2.22.0 current, re-pinned to
  that. Verified the actual image+text `contents=` input shape and `part.inline_data` output shape by
  reading the installed SDK's own `_transformers.t_part` source — not by trusting a summarized doc page,
  after two independent web sources gave conflicting method names/model names for the same API.
  **⚠ UPDATE 2026-09-07 — live-tested against a real API key, with a substantive finding:** the SDK
  integration itself is confirmed correct (auth succeeds; a plain text call to `gemini-3.6-flash` returned a
  real response). `models.list()` against the live account shows `gemini-2.5-flash-image` is deprecated and
  the current stable image model is **`gemini-3.1-flash-image`** (updated `MODEL_NAME` accordingly). However,
  **every image-generation model tested — both the original and the current one — returns
  `RESOURCE_EXHAUSTED` with `free_tier_requests limit: 0`**, while the text model works fine on the same key.
  This means Google's Gemini free tier no longer includes image-generation quota at all (a real policy
  change since the D003 research, which found ~500 free image requests/day as of Feb 2026 — that research
  was accurate when found; only live testing surfaced that it's since changed). **Decision needed from user:
  enable billing on the Google account (cost then becomes small-but-nonzero, contradicting the original
  "free, no card" premise of D003), implement the Cloudflare/HF fallback providers instead (deferred so far,
  not yet built), or accept floor-plan-only for this submission** (already fully working and live-verified).
  **RESOLVED 2026-09-07 — Option C chosen: floor-plan-only for this submission.** The deterministic floor
  plan (already fully working and live-verified) is the visualization for now. Photorealistic rendering via
  Gemini stays implemented and correctly wired (including the `gemini-3.1-flash-image` model-name fix above)
  but is not enabled — it requires billing on the Google account, which was not taken up. Cloudflare/HF
  fallback providers remain undesigned-beyond-D003's chain (not implemented). This is a legitimate, stated
  limitation, not a gap being hidden: per brief PART 9, the floor plan is already the authoritative record of
  the layout; the photorealistic render was always an enhancement on top of it, never a requirement. Report
  language: "Photorealistic visualization is designed and implemented (structure-preserving image editing
  via Gemini) but not enabled in this submission, as it requires a billed API account; the deterministic
  floor-plan visualization, which is authoritative for the computed layout, is fully functional and used
  throughout." No further action needed on this item unless the user revisits it.
- **D023 translator bug found and fixed before shipping:** the first version could describe two new items
  in terms of each other ("coffee table near the rug" / "rug near the coffee table") — fixed by anchoring
  new-item descriptions to EXISTING furniture only, falling back to qualitative room position otherwise.
- **D024 parser bug found and fixed before shipping:** matching only an item's last word broke on any
  catalog name with a trailing qualifier like "(Queen)" or "+ Ceramic Pot" — fixed to match on any
  significant word in the name, not just the last one. (The exact same class of bug was then independently
  reproduced in a first draft of the test suite and had to be fixed there too — worth remembering as a
  recurring trap.)
- **Graceful degradation verified live:** `run_generate_design` completes successfully with no
  `Visualization` row when `GEMINI_API_KEY` is unset (the shipped default) — confirmed by test, not just
  documented.

**Evaluation results (D025) — measured 2026-09-07, reproducible via the scripts below, not estimated:**

```
$ python -m evaluation.run_layout_study      (8 trials/fixture, SA iterations=1200)
  simulated_annealing   feasibility=32/32 (100%)  mean_score=0.7163
  random                feasibility=32/32 (100%)  mean_score=0.6334
  greedy_first_fit      feasibility=32/32 (100%)  mean_score=0.6600

$ python -m evaluation.run_recommendation_study   (120 synthetic preference combinations)
  Overall budget compliance rate: 87.5%
  Mean style-match score: 0.8857
  Per-style budget compliance: Modern 80%, Minimalist 95%, Contemporary 80%,
  Traditional 85%, Industrial 90%, Scandinavian 95%
```

SA beats random by +13.1 points and greedy by +8.5 points on mean layout score, at equal (100%) feasibility
across all four fixtures — a genuine, reproducible result for the report's evaluation chapter. Still
"Not yet measured": style/detection accuracy (no real CV in this batch, per D022) and anything about the
Gemini render path (untested — see above).

**Frontend (item 6) — complete:** `NewDesignPage` (room type → sample-room gallery or real upload →
preferences form → generate + poll), `DesignDetailPage` (recommendation cards with score bars/rationale/MOCK
badge, layout score breakdown, constraint checklist, inline floor-plan SVG, visualization image with its
structure-preserving disclosure or an honest "not available" message, feedback box that triggers and polls a
new iteration). New components: `RecommendationCard`, `FloorPlanView`, `FeedbackBox`. `api/client.ts` gained
a `patch()` method (was missing — first draft of the preferences call used `post` against a PATCH-only
route and would have 405'd; caught before it reached a live test).

---

# ▶ BATCH ④ : Style Recognition (D005 implementation) — 2026-09-07

D005 was locked (CLIP-RN50 zero-shot) back in Batch ①-era decisions but never actually built — style came
entirely from fixture data until now. This batch implements it for real.

**Built:** `ai/style_recognition/classifier.py` (CLIP `RN50-quickgelu` + `openai` weights via
`open_clip_torch`, zero-shot with 4-template prompt ensembling per class, softmax over the 6 FR-3 labels,
abstain threshold at 0.35), `ai/style_recognition/cli.py` (classify any image file standalone), 8 unit tests
(distribution validity, abstain-threshold logic tested in isolation, determinism, non-RGB safety).

**Model-correctness finding:** plain `'RN50'` loads with a QuickGELU activation mismatch against the OpenAI
weights (open_clip warns explicitly) — verified by loading with `warnings.simplefilter('error')` and
confirming only `'RN50-quickgelu'` loads clean. Using the mismatched config would have silently degraded
zero-shot accuracy without any error ever surfacing.

**Test-design finding:** an initial test asserted the classifier must abstain on a blank gray image; the
real measured confidence (0.373) landed just above the 0.35 threshold, making the test flaky by construction
(a real model's output pinned against a boundary). Fixed by extracting `should_abstain(confidence)` as a
pure function, tested directly with controlled values, separately from a softer "never near-certain on
nonsense input" check on the real model.

## Evaluation dataset: Kaggle Houzz set (as D005 specified) — with an honest, load-bearing caveat

Downloaded `stepanyarullin/interior-design-styles` (~735MB, `datasets/houzz_styles/`, gitignored) via the
user's own Kaggle API token (no credentials were available to the assistant; user set this up themselves —
see conversation). **This dataset has 19 style-folder classes and contains NO "Minimalist" class at all** —
confirmed by listing every folder. Of the six FR-3 styles, only Modern/Contemporary/Traditional/
Industrial/Scandinavian have real ground-truth images (~192-203 test images each, 986 total); Minimalist is
therefore **not evaluable** against this dataset and is reported as such, not silently dropped or faked.

## Measured results — `python -m evaluation.run_style_study`, 2026-09-07, 986 real test photos, 42.8s

```
Overall accuracy (5 evaluable classes): 0.4016 (396/986)
Mean confidence: 0.4367
Abstain rate: 0.2982

style            precision     recall         f1  support
Modern              0.2711     0.3645     0.3109      203
Contemporary        0.2989     0.3980     0.3414      196
Traditional         0.8548     0.2611     0.4000      203
Industrial          0.6859     0.5573     0.6149      192
Scandinavian        0.4912     0.4375     0.4628      192

Modern/Contemporary cross-confusion: 74 Modern→Contemporary, 68 Contemporary→Modern
  (this is the single largest confusion pair by far — matches the prediction already recorded
  in the D004/D021 decision log, made BEFORE this measurement was run)
```

**Honest interpretation:** 40.16% accuracy is ~2.4× the 6-class random baseline (16.7%) — genuine signal,
not noise, but far from strong. Traditional shows high precision (0.85) with low recall (0.26): the model
rarely mislabels OTHER styles as Traditional, but frequently mislabels true-Traditional rooms as
Modern/Contemporary instead. Industrial is the strongest class (F1 0.61). This is a legitimate, reportable
zero-shot result, consistent with the general literature finding that style classification without
domain-specific fine-tuning is genuinely hard — not a bug, not a misconfiguration (both were checked).

**RESOLVED 2026-09-07 — user invoked D005's upgrade path.** Added `encode_image_features()` to
`ai/style_recognition/classifier.py` (raw, L2-normalized CLIP embedding, no zero-shot text step) plus
`evaluation/run_style_head_study.py`: extracts frozen CLIP-RN50 embeddings for the dataset's training split,
fits a `sklearn.LogisticRegression` on top (0.2s to fit — a linear layer over frozen features, not
deep-network training), evaluates on the identical test set.

**⚠ Design decision made without a further question round (flagged here per the no-silent-decisions
rule):** the trained head is **NOT** swapped into the live classifier. This training set has the same
Minimalist gap as the test set — zero Minimalist images anywhere in the dataset — so a head trained on it
could only ever predict 5 of the 6 FR-3 styles, silently dropping Minimalist support from the live system.
`ai/style_recognition/classifier.py` (the actual, live, shipped classifier) therefore stays zero-shot, which
can still at least attempt all 6 categories. The trained head exists purely as a measured comparison
artifact for the evaluation chapter, answering "would a trained head do better?" honestly, without narrowing
what the shipped system can do.

**Measured result — `python -m evaluation.run_style_head_study`, 2026-09-07, same 986-image test set:**

```
Trained-head accuracy (5 evaluable classes): 0.5984 (590/986)
Zero-shot accuracy, same test set (run_style_study.py):    0.4016 (396/986)
                                                            +19.7 percentage points

              precision  recall  f1-score  support
Modern           0.4587  0.4926    0.4751      203
Contemporary     0.4400  0.3367    0.3815      196
Traditional      0.7054  0.8374    0.7658      203   (zero-shot recall was 0.2611 — dramatic improvement)
Industrial       0.7500  0.6719    0.7088      192
Scandinavian     0.6098  0.6510    0.6297      192
```

Modern/Contemporary remains the largest confusion pair (40 Modern→Contemporary, 60 Contemporary→Modern) even
with the trained head — confirms this confusion is a genuine property of the visual distinction between
these two styles, not an artifact of the zero-shot method specifically. Report language: "A frozen-feature
logistic-regression head improves measured accuracy from 40.2% to 59.8% on the classes where ground truth is
available, but is not used in the deployed system because the same dataset gap (no Minimalist images) that
enables this comparison would also prevent a head trained on it from ever predicting Minimalist; the shipped
classifier remains zero-shot for full six-class coverage."

## D005 wired into the live upload pipeline — 2026-09-08

Per user request, style recognition now runs for real on any genuine (non-sample) uploaded photo, not just
as a standalone module. Scoped deliberately narrow: **style only, not full recommendation** — see rationale
below.

**What happens now, for a genuine (non-sample) photo:** `POST /api/sessions/<id>/image` submits a second,
independent background job (`JobStage.STYLE_RECOGNITION` — defined since Batch ①, unused until now) that
runs the real CLIP classifier and persists a genuine `StylePrediction`, attached to a minimal `RoomAnalysis`
shell with `room_width_cm`/`room_length_cm` explicitly `NULL` and `scale_source=UNKNOWN`. New endpoint
`GET /api/sessions/<id>/style` returns it (works identically for a sample room's fixture-labeled style and a
real photo's genuine prediction — same response shape, distinguished only by `is_sample_room`).

**Why not chained after `preprocess`:** `classify_style` does its own image resizing internally, so it has
no dependency on the preprocess job's output — running it as an independent job avoids both a fake ordering
dependency and a confusing "progress bar resets to 0%" glitch two sequential 0-100 stages in one job would
have caused.

**D004 (room dimension strategy) remains explicitly open — flagged, not silently resolved.** A real photo
now gets a genuine style prediction but still cannot generate a full recommendation, because dimensions are
unknown. `run_generate_design` gained a new, distinct error, `room_dimensions_missing` — separate from
`room_analysis_missing` (analysis now genuinely exists; specifically its dimensions don't) — with a message
directing the user to a sample room for the full pipeline. This was a deliberate scope decision (stated to
the user, not decided silently): fully solving D004 (user-entered dimensions vs. depth estimation vs.
reference-object anchoring) is separate, larger work.

**Live-verified**, not just unit-tested: registered a real user, uploaded a genuine non-sample photo through
the actual running server, confirmed `style_job_id` present, polled it to completion, fetched
`GET /style` and got a real classification (correctly `abstained: true` at 32.6% confidence on a
genuinely uninformative test image — exactly brief PART 4's intended behavior), then confirmed `generate`
fails with `room_dimensions_missing` end-to-end. 4 new integration tests
(`tests/test_style_recognition_upload.py`) plus 1 existing test updated to match the new, more specific
error code. 87/87 tests passing at this point.

## D004 (room dimension strategy) — RESOLVED 2026-09-08: user-provided dimensions

The `room_dimensions_missing` gap above was intentionally left open in the same session — user chose to
close it immediately after. **Locked: Option A, user-provided dimensions** — explicitly sanctioned by the
report's own PART 3 wording ("...the system must clearly distinguish between measured / estimated /
user-provided values"). Rejected: monocular depth estimation (real effort for a method that fundamentally
cannot recover absolute metric scale from one uncalibrated photo — a genuine CV limitation, not a
workable-around implementation detail) and reference-object anchoring (blocked by the same deferred
detection work as D018).

**What changed:** `POST /api/sessions/<id>/image` accepts optional `room_width_cm`/`room_length_cm` form
fields (both-or-neither, validated to 50–3000cm — catches unit mistakes like entering meters). When
provided for a genuine (non-sample) photo, `run_style_recognition_for_upload` stamps the RoomAnalysis
`scale_source=USER_PROVIDED` with real dimensions instead of `UNKNOWN`/`NULL`, which **unlocks full
recommendation + layout generation for a real uploaded photo** — not just a style prediction. Sample rooms
silently ignore any provided dimensions (fixture's own real ones always win, matching the existing
precedence rule). Frontend: two number inputs appear alongside the "upload your own photo" file picker
(never shown for sample-room cards); `DesignDetailPage` discloses, for any real-photo-generated design, that
existing-furniture detection isn't implemented and the layout assumes an empty room.

**Live-verified end-to-end**, the first time a real (non-fixture) photo has gone all the way through the
entire pipeline: registered a user, uploaded a real photo with `room_width_cm=350`/`room_length_cm=420`,
confirmed `has_known_dimensions: true`, ran `generate` to completion (not `room_dimensions_missing`),
fetched a genuine recommendation (4 items, budget-compliant) and layout (score 0.7993, **all 5 hard
constraints satisfied**, valid floor-plan SVG) — computed from a real upload, not a fixture. 5 new tests
(`tests/test_room_dimensions.py`: full unlock, both-or-neither rejection, out-of-range rejection, non-numeric
rejection, sample-room precedence). **92/92 tests passing.**

**What's still NOT solved:** existing-furniture detection for real photos (still deferred, D018/D022) — a
real uploaded room is always treated as empty, disclosed honestly in the UI, never silently assumed.

---

## Verification approach (applies from Phase 3 onward)
Each module ships with: a runnable CLI entry point taking a real image/JSON and printing structured output,
a pytest suite, and a documented "how to verify" recipe. No module is called complete until its output has
been produced from a real input and shown.

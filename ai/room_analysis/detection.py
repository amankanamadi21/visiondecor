"""
Real furniture-instance detection for a genuine uploaded room photo
(2026-09-08 CV batch, FR-2). A pretrained (COCO) YOLOv8n model — no
fine-tuning, per D001's CPU-only constraint. Display-only this batch: see
db_adapter.py for why these detections do not (yet) feed the recommendation
engine or layout optimiser.

Report Issue R-07 note: standard COCO has no wall/window/door/floor
classes — those come from segmentation.py instead, a genuinely different
model family, not this one.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

# COCO classes with plausible presence in an indoor room photo, used to (a)
# keep the "what we detected" UI free of noise from irrelevant COCO classes
# (airplane, zebra, ...) and (b) define exactly what
# evaluation/run_detection_study.py scores mAP against — matches PLAN.md's
# pre-D006a-cut dataset decision ("chair, sofa/couch, bed, table, tv, sink"),
# extended to the handful of other classes a real room photo can plausibly
# contain. Verified against the model's own `model.names` at runtime
# (2026-09-08), not assumed from memory.
INTERIOR_RELEVANT_CLASSES = frozenset({
    "chair", "couch", "potted plant", "bed", "dining table", "tv", "sink",
    "book", "clock", "vase", "refrigerator",
})

CONFIDENCE_THRESHOLD = 0.35
MODEL_NAME = "yolov8n.pt"


@dataclass
class Detection:
    class_label: str
    confidence: float
    bbox_px: dict  # {"x": int, "y": int, "w": int, "h": int} — top-left + size, pixels
    area_px: int

    @property
    def interior_relevant(self) -> bool:
        return self.class_label in INTERIOR_RELEVANT_CLASSES


@lru_cache(maxsize=1)
def _load_model():
    from ultralytics import YOLO

    return YOLO(MODEL_NAME)


def detect_objects(image_path: str, *, confidence_threshold: float = CONFIDENCE_THRESHOLD) -> list[Detection]:
    """Runs YOLOv8n over a real photo and returns every detection above
    `confidence_threshold`, whatever the class — filtering to
    interior-relevant classes is left to the caller/UI so the stored data
    stays complete and honest (see Detection.interior_relevant)."""
    model = _load_model()
    results = model.predict(image_path, verbose=False, conf=confidence_threshold)

    detections: list[Detection] = []
    for result in results:
        names = result.names
        for box in result.boxes:
            class_id = int(box.cls[0])
            confidence = float(box.conf[0])
            x1, y1, x2, y2 = (float(v) for v in box.xyxy[0].tolist())
            w, h = x2 - x1, y2 - y1
            detections.append(
                Detection(
                    class_label=names[class_id],
                    confidence=confidence,
                    bbox_px={"x": round(x1), "y": round(y1), "w": round(w), "h": round(h)},
                    area_px=round(w * h),
                )
            )
    return detections

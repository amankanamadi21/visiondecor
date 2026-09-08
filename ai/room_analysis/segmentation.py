"""
Architectural-surface segmentation for a genuine uploaded room photo
(2026-09-08 CV batch, Report Issue R-07). Standard COCO-pretrained YOLO
(detection.py) has no wall/floor/ceiling/window/door classes — those
concepts don't exist in COCO at all — so a separate pretrained ADE20K
semantic-segmentation model supplies them instead: SegFormer-B0
(~3.8M params, CPU-viable, no fine-tuning per D001).

Class indices are matched by NAME SUBSTRING against the model's own
`config.id2label` at runtime, not hardcoded — verified once (2026-09-08) that
this checkpoint's 150 ADE20K classes include 0 wall, 3 floor, 5 ceiling,
8 windowpane, 14 door, 58 'screen door', but substring matching stays correct
even if a future checkpoint renumbers them.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import numpy as np

MODEL_NAME = "nvidia/segformer-b0-finetuned-ade-512-512"

# ADE20K label substring (lowercase) -> this project's schema label.
# "screen door" matches "door" too, deliberately merged into one class.
ARCHITECTURAL_LABEL_MAP = {
    "windowpane": "window",
    "wall": "wall",
    "floor": "floor",
    "ceiling": "ceiling",
    "door": "door",
}


@dataclass
class ArchitecturalRegion:
    class_label: str  # "wall" | "floor" | "ceiling" | "window" | "door"
    confidence: float  # mean softmax probability over the region's pixels
    bbox_px: dict  # {"x", "y", "w", "h"} — axis-aligned bounding box, pixels
    polygon_px: list[list[int]]  # simplified contour, [[x, y], ...], pixels
    area_px: int


@lru_cache(maxsize=1)
def _load_model():
    from transformers import SegformerForSemanticSegmentation, SegformerImageProcessor

    processor = SegformerImageProcessor.from_pretrained(MODEL_NAME)
    model = SegformerForSemanticSegmentation.from_pretrained(MODEL_NAME)
    model.eval()
    return processor, model


def _map_label(raw_label: str) -> str | None:
    raw_lower = raw_label.lower()
    for substring, mapped in ARCHITECTURAL_LABEL_MAP.items():
        if substring in raw_lower:
            return mapped
    return None


def segment_architecture(image_path: str, *, min_region_area_px: int = 400) -> list[ArchitecturalRegion]:
    import cv2
    import torch
    from PIL import Image

    processor, model = _load_model()
    image = Image.open(image_path).convert("RGB")
    inputs = processor(images=image, return_tensors="pt")
    with torch.no_grad():
        outputs = model(**inputs)

    target_size = [image.size[::-1]]  # (height, width)
    probs = torch.nn.functional.softmax(outputs.logits, dim=1)
    # Upsample both the class map and the per-pixel confidence to the
    # original photo's resolution so bbox/polygon coordinates line up with
    # what the frontend actually displays.
    seg_map = processor.post_process_semantic_segmentation(outputs, target_sizes=target_size)[0].numpy()
    probs_upsampled = torch.nn.functional.interpolate(
        probs, size=seg_map.shape, mode="bilinear", align_corners=False
    )[0].numpy()

    id2label = model.config.id2label
    # Merge every ADE20K class id that maps to the same schema label (e.g.
    # "door" and "screen door" both -> "door") into one combined mask.
    masks_by_label: dict[str, np.ndarray] = {}
    max_prob_by_label: dict[str, np.ndarray] = {}
    for class_id_str, raw_label in id2label.items():
        mapped = _map_label(raw_label)
        if mapped is None:
            continue
        class_id = int(class_id_str)
        mask = seg_map == class_id
        if mapped in masks_by_label:
            masks_by_label[mapped] = masks_by_label[mapped] | mask
        else:
            masks_by_label[mapped] = mask
        max_prob_by_label[mapped] = probs_upsampled[class_id]

    regions: list[ArchitecturalRegion] = []
    for label, mask in masks_by_label.items():
        area = int(mask.sum())
        if area < min_region_area_px:
            continue
        mask_u8 = (mask.astype(np.uint8)) * 255
        contours, _ = cv2.findContours(mask_u8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            continue
        largest = max(contours, key=cv2.contourArea)
        x, y, w, h = cv2.boundingRect(largest)
        epsilon = 0.01 * cv2.arcLength(largest, True)
        polygon = cv2.approxPolyDP(largest, epsilon, True).reshape(-1, 2).tolist()

        confidence = float(max_prob_by_label[label][mask].mean())
        regions.append(
            ArchitecturalRegion(
                class_label=label,
                confidence=round(confidence, 4),
                bbox_px={"x": int(x), "y": int(y), "w": int(w), "h": int(h)},
                polygon_px=polygon,
                area_px=area,
            )
        )
    return regions

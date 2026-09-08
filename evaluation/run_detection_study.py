#!/usr/bin/env python3
"""
Detection evaluation study (2026-09-08 CV batch) — revives the mAP metric
D006a explicitly cut on 2026-09-06 (downgrading Report Issue R-07 from
"measured" to "documented limitation" purely to save time for the RAG work).
Now measured, since a real detector exists in the live app anyway.

Runs the SAME pretrained YOLOv8n used in production
(ai.room_analysis.detection) against a real-photo subset of COCO val2017:
every image containing at least one of the interior-relevant classes this
project's detector actually reports (chair, couch, potted plant, bed, dining
table, tv, sink, book, clock, vase, refrigerator) — the intersecting label
space named in PLAN.md's original (pre-cut) dataset decision, extended
slightly to match what INTERIOR_RELEVANT_CLASSES actually contains.

Reports standard COCO mAP@50 / mAP@50:95 (pycocotools) PLUS precision /
recall / F1 at the confidence threshold the live app actually uses (0.35),
via IoU>=0.5 greedy matching — Section K's evaluation requirements ask for
all four (Precision / Recall / F1 / mAP@50), not just mAP.

Usage:
    source .venv/bin/activate
    python -m evaluation.run_detection_study            # auto-downloads the
                                                          # ~1600-image subset
                                                          # on first run (not
                                                          # committed to git)
"""
from __future__ import annotations

import json
import os
import urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

DATASET_DIR = "datasets/coco_val2017_indoor"
ANNOTATIONS_ZIP_URL = "http://images.cocodataset.org/annotations/annotations_trainval2017.zip"
ANNOTATIONS_PATH = f"{DATASET_DIR}/annotations/instances_val2017.json"
IMAGES_DIR = f"{DATASET_DIR}/images"
IMAGE_BASE_URL = "http://images.cocodataset.org/val2017"

CONFIDENCE_THRESHOLD = 0.35  # matches ai.room_analysis.detection.CONFIDENCE_THRESHOLD
IOU_THRESHOLD = 0.5


def _download_annotations() -> None:
    import zipfile

    os.makedirs(DATASET_DIR, exist_ok=True)
    zip_path = f"{DATASET_DIR}/annotations_trainval2017.zip"
    print(f"Downloading COCO 2017 annotations (~253MB, one-time)...")
    urllib.request.urlretrieve(ANNOTATIONS_ZIP_URL, zip_path)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extract("annotations/instances_val2017.json", DATASET_DIR)
    os.remove(zip_path)  # only the val2017 instances file is needed, not train2017's


def _relevant_image_filenames(data: dict, relevant_cat_ids: set[int]) -> dict[int, str]:
    image_ids_with_relevant = {
        ann["image_id"] for ann in data["annotations"] if ann["category_id"] in relevant_cat_ids
    }
    id_to_filename = {img["id"]: img["file_name"] for img in data["images"]}
    return {i: id_to_filename[i] for i in image_ids_with_relevant}


def _download_image(filename: str) -> None:
    dest = os.path.join(IMAGES_DIR, filename)
    if os.path.exists(dest):
        return
    urllib.request.urlretrieve(f"{IMAGE_BASE_URL}/{filename}", dest)


def ensure_dataset_downloaded(relevant_names: frozenset[str]) -> dict:
    """Downloads only the images actually needed (interior-relevant subset
    of COCO val2017, ~1600 of 5000), not the full ~778MB val2017.zip.
    Idempotent — skips anything already present."""
    if not os.path.exists(ANNOTATIONS_PATH):
        _download_annotations()

    with open(ANNOTATIONS_PATH) as f:
        data = json.load(f)
    cat_id_to_name = {c["id"]: c["name"] for c in data["categories"]}
    relevant_cat_ids = {cid for cid, name in cat_id_to_name.items() if name in relevant_names}
    filenames = _relevant_image_filenames(data, relevant_cat_ids)

    os.makedirs(IMAGES_DIR, exist_ok=True)
    missing = [fn for fn in filenames.values() if not os.path.exists(os.path.join(IMAGES_DIR, fn))]
    if missing:
        print(f"Downloading {len(missing)} images (of {len(filenames)} in the subset)...")
        with ThreadPoolExecutor(max_workers=16) as pool:
            list(pool.map(_download_image, missing))
    return data


def _iou(box_a: tuple[float, float, float, float], box_b: tuple[float, float, float, float]) -> float:
    ax1, ay1, ax2, ay2 = box_a
    bx1, by1, bx2, by2 = box_b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def run_study(confidence_threshold: float = CONFIDENCE_THRESHOLD, iou_threshold: float = IOU_THRESHOLD) -> dict:
    from ai.room_analysis.detection import INTERIOR_RELEVANT_CLASSES, _load_model

    data = ensure_dataset_downloaded(INTERIOR_RELEVANT_CLASSES)
    cat_id_to_name = {c["id"]: c["name"] for c in data["categories"]}
    name_to_cat_id = {name: cid for cid, name in cat_id_to_name.items()}
    relevant_cat_ids = {cid for cid, name in cat_id_to_name.items() if name in INTERIOR_RELEVANT_CLASSES}

    gt_by_image: dict[int, list[tuple[str, list[float]]]] = defaultdict(list)
    for ann in data["annotations"]:
        if ann["category_id"] in relevant_cat_ids:
            gt_by_image[ann["image_id"]].append((cat_id_to_name[ann["category_id"]], ann["bbox"]))

    id_to_filename = {img["id"]: img["file_name"] for img in data["images"]}
    image_ids = sorted(
        i for i in gt_by_image if os.path.exists(os.path.join(IMAGES_DIR, id_to_filename[i]))
    )

    model = _load_model()

    coco_detections = []
    tp = fp = fn = 0

    for image_id in image_ids:
        path = os.path.join(IMAGES_DIR, id_to_filename[image_id])
        # Low confidence floor so pycocotools sees the full precision/recall
        # curve for mAP; the fixed-threshold P/R/F1 below re-filters to 0.35.
        result = model.predict(path, verbose=False, conf=0.001)[0]
        names = result.names

        preds_at_threshold: list[tuple[str, tuple[float, float, float, float]]] = []
        for box in result.boxes:
            label = names[int(box.cls[0])]
            if label not in INTERIOR_RELEVANT_CLASSES:
                continue
            confidence = float(box.conf[0])
            x1, y1, x2, y2 = (float(v) for v in box.xyxy[0].tolist())
            coco_detections.append({
                "image_id": image_id, "category_id": name_to_cat_id[label],
                "bbox": [x1, y1, x2 - x1, y2 - y1], "score": confidence,
            })
            if confidence >= confidence_threshold:
                preds_at_threshold.append((label, (x1, y1, x2, y2)))

        gts = list(gt_by_image[image_id])
        matched_gt: set[int] = set()
        for label, pred_box in preds_at_threshold:
            best_iou, best_idx = 0.0, None
            for idx, (gt_label, gt_bbox) in enumerate(gts):
                if idx in matched_gt or gt_label != label:
                    continue
                gx, gy, gw, gh = gt_bbox
                iou = _iou(pred_box, (gx, gy, gx + gw, gy + gh))
                if iou > best_iou:
                    best_iou, best_idx = iou, idx
            if best_idx is not None and best_iou >= iou_threshold:
                tp += 1
                matched_gt.add(best_idx)
            else:
                fp += 1
        fn += len(gts) - len(matched_gt)

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0

    from pycocotools.coco import COCO
    from pycocotools.cocoeval import COCOeval

    coco_gt = COCO(ANNOTATIONS_PATH)
    map50 = map50_95 = None
    if coco_detections:
        coco_dt = coco_gt.loadRes(coco_detections)
        coco_eval = COCOeval(coco_gt, coco_dt, "bbox")
        coco_eval.params.imgIds = image_ids
        coco_eval.params.catIds = list(relevant_cat_ids)
        coco_eval.evaluate()
        coco_eval.accumulate()
        coco_eval.summarize()
        map50_95, map50 = coco_eval.stats[0], coco_eval.stats[1]

    return {
        "num_images": len(image_ids),
        "num_ground_truth_objects": sum(len(v) for v in gt_by_image.values()),
        "confidence_threshold": confidence_threshold,
        "iou_threshold": iou_threshold,
        "precision": precision, "recall": recall, "f1": f1,
        "tp": tp, "fp": fp, "fn": fn,
        "mAP50": map50, "mAP50_95": map50_95,
    }


def print_report(report: dict) -> None:
    print()
    print(
        f"Detection study — YOLOv8n (COCO-pretrained, no fine-tuning) on "
        f"{report['num_images']} real COCO val2017 photos containing an "
        f"interior-relevant class ({report['num_ground_truth_objects']} ground-truth objects)"
    )
    print("=" * 90)
    print(f"mAP@50:      {report['mAP50']:.4f}" if report["mAP50"] is not None else "mAP@50: n/a (no detections)")
    print(f"mAP@50:95:   {report['mAP50_95']:.4f}" if report["mAP50_95"] is not None else "mAP@50:95: n/a")
    print()
    print(f"At the live app's operating point (confidence >= {report['confidence_threshold']}, IoU >= {report['iou_threshold']}):")
    print(f"  Precision: {report['precision']:.4f}  ({report['tp']} TP / {report['tp'] + report['fp']} predictions)")
    print(f"  Recall:    {report['recall']:.4f}  ({report['tp']} TP / {report['tp'] + report['fn']} ground truth)")
    print(f"  F1:        {report['f1']:.4f}")


if __name__ == "__main__":
    print_report(run_study())

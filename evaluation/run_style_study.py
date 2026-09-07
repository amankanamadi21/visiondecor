#!/usr/bin/env python3
"""
Style recognition evaluation (decision D005) — real measured accuracy
against the Kaggle Houzz interior-design-styles dataset (dataset_test
split), which D005 explicitly locked as the evaluation set.

⚠ IMPORTANT, HONEST LIMITATION: this dataset has NO "Minimalist" class at
all (confirmed by inspecting all 19 of its style folders — see PLAN.md).
Five of the six FR-3 styles (Modern, Contemporary, Traditional, Industrial,
Scandinavian) have real ground-truth folders; Minimalist does not and is
therefore NOT evaluable against this dataset. This script reports accuracy
over the 5 evaluable classes only and says so explicitly — it does not
pretend Minimalist was measured, and does not quietly drop it from the
report without comment either.

Usage:
    source .venv/bin/activate
    python -m evaluation.run_style_study
"""
from __future__ import annotations

import glob
import time
from collections import defaultdict

from PIL import Image

from ai.style_recognition.classifier import FR3_STYLES, classify_style

DATASET_DIR = "datasets/houzz_styles/dataset_test/dataset_test"

# Houzz folder name -> FR-3 style name. Only classes with an exact,
# unambiguous match are included — see module docstring re: Minimalist.
FOLDER_TO_FR3_STYLE = {
    "modern": "Modern",
    "contemporary": "Contemporary",
    "traditional": "Traditional",
    "industrial": "Industrial",
    "scandinavian": "Scandinavian",
}
UNEVALUABLE_FR3_STYLES = [s for s in FR3_STYLES if s not in FOLDER_TO_FR3_STYLE.values()]


def load_test_set() -> list[tuple[str, str]]:
    """Returns [(image_path, true_fr3_style), ...]."""
    samples = []
    for folder_name, fr3_style in FOLDER_TO_FR3_STYLE.items():
        paths = glob.glob(f"{DATASET_DIR}/{folder_name}/*.jpg")
        samples.extend((p, fr3_style) for p in paths)
    return samples


def run_study():
    samples = load_test_set()
    print(f"Loaded {len(samples)} test images across {len(FOLDER_TO_FR3_STYLE)} classes.")
    print(f"NOT evaluable (no ground-truth images in this dataset): {UNEVALUABLE_FR3_STYLES}")
    print()

    confusion: dict[str, dict[str, int]] = {
        true_style: {pred_style: 0 for pred_style in FR3_STYLES} for true_style in FOLDER_TO_FR3_STYLE.values()
    }
    correct = 0
    abstained_count = 0
    confidences = []

    t0 = time.time()
    for i, (path, true_style) in enumerate(samples):
        image = Image.open(path)
        result = classify_style(image)
        confusion[true_style][result.predicted_style] += 1
        confidences.append(result.confidence)
        if result.abstained:
            abstained_count += 1
        if result.predicted_style == true_style:
            correct += 1
        if (i + 1) % 200 == 0:
            print(f"  ...{i + 1}/{len(samples)} processed ({time.time() - t0:.0f}s elapsed)")

    elapsed = time.time() - t0
    accuracy = correct / len(samples)

    print()
    print(f"Evaluated {len(samples)} images in {elapsed:.1f}s")
    print(f"Overall accuracy (5 evaluable classes): {accuracy:.4f} ({correct}/{len(samples)})")
    print(f"Mean confidence: {sum(confidences) / len(confidences):.4f}")
    print(f"Abstain rate (confidence < threshold): {abstained_count / len(samples):.4f}")
    print()

    print("Per-class precision / recall / F1:")
    print(f"{'style':15s} {'precision':>10s} {'recall':>10s} {'f1':>10s} {'support':>8s}")
    for style in FOLDER_TO_FR3_STYLE.values():
        tp = confusion[style][style]
        support = sum(confusion[style].values())
        predicted_as_style = sum(confusion[t][style] for t in FOLDER_TO_FR3_STYLE.values())
        precision = tp / predicted_as_style if predicted_as_style else 0.0
        recall = tp / support if support else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
        print(f"{style:15s} {precision:>10.4f} {recall:>10.4f} {f1:>10.4f} {support:>8d}")

    print()
    print("Confusion matrix (rows=true, columns=predicted; all 6 FR-3 columns shown):")
    header = "".join(f"{s[:10]:>11s}" for s in FR3_STYLES)
    print(f"{'':15s}{header}")
    for true_style in FOLDER_TO_FR3_STYLE.values():
        row = "".join(f"{confusion[true_style][pred]:>11d}" for pred in FR3_STYLES)
        print(f"{true_style:15s}{row}")

    print()
    modern_as_contemporary = confusion["Modern"]["Contemporary"]
    contemporary_as_modern = confusion["Contemporary"]["Modern"]
    print(
        f"Modern/Contemporary cross-confusion (flagged as expected in decision log D004/D021): "
        f"{modern_as_contemporary} Modern images predicted Contemporary; "
        f"{contemporary_as_modern} Contemporary images predicted Modern."
    )


if __name__ == "__main__":
    run_study()

#!/usr/bin/env python3
"""
D005 upgrade-path comparison: a logistic-regression head fit on frozen
CLIP-RN50 features, vs. the zero-shot classifier already measured in
run_style_study.py — same test set, same 5 evaluable classes, direct
comparison.

⚠ NOT swapped into the live classifier (ai/style_recognition/classifier.py
stays zero-shot) — see PLAN.md Batch ④: this dataset has no Minimalist
images at all, so a head trained on it could never predict Minimalist,
which would silently drop one of FR-3's six required style categories from
the live system. This script exists to produce an honest, measured answer
to "would a trained head do better?", not to become the shipped classifier.

This IS a training step (unlike the zero-shot path) — but a linear
classifier fit on ~30 seconds of CPU time over already-frozen features,
not a deep network trained from scratch. Consistent with D001/D005's
"no deep training" constraint in spirit, and explicitly labeled as a
comparison artifact rather than the production model.

Usage:
    source .venv/bin/activate
    python -m evaluation.run_style_head_study
"""
from __future__ import annotations

import glob
import time

import numpy as np
from PIL import Image
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix

from ai.style_recognition.classifier import encode_image_features

TRAIN_DIR = "datasets/houzz_styles/dataset_train/dataset_train"
TEST_DIR = "datasets/houzz_styles/dataset_test/dataset_test"

FOLDER_TO_FR3_STYLE = {
    "modern": "Modern",
    "contemporary": "Contemporary",
    "traditional": "Traditional",
    "industrial": "Industrial",
    "scandinavian": "Scandinavian",
}
CLASSES = list(FOLDER_TO_FR3_STYLE.values())


def _extract_features(base_dir: str) -> tuple[np.ndarray, np.ndarray]:
    features, labels = [], []
    for folder_name, fr3_style in FOLDER_TO_FR3_STYLE.items():
        paths = glob.glob(f"{base_dir}/{folder_name}/*.jpg")
        for path in paths:
            features.append(encode_image_features(Image.open(path)))
            labels.append(fr3_style)
    return np.array(features), np.array(labels)


def run_study():
    print("Extracting frozen CLIP features for the TRAINING split (fitting the head)...")
    t0 = time.time()
    X_train, y_train = _extract_features(TRAIN_DIR)
    print(f"  {len(X_train)} training images, {time.time() - t0:.1f}s")

    print("Extracting frozen CLIP features for the TEST split (same set run_style_study.py used)...")
    t0 = time.time()
    X_test, y_test = _extract_features(TEST_DIR)
    print(f"  {len(X_test)} test images, {time.time() - t0:.1f}s")

    print()
    print("Fitting logistic regression on frozen features (~30s expected)...")
    t0 = time.time()
    clf = LogisticRegression(max_iter=2000, C=1.0)
    clf.fit(X_train, y_train)
    print(f"  Fit in {time.time() - t0:.1f}s")

    y_pred = clf.predict(X_test)
    accuracy = (y_pred == y_test).mean()

    print()
    print(f"Trained-head accuracy (5 evaluable classes): {accuracy:.4f} ({(y_pred == y_test).sum()}/{len(y_test)})")
    print("Compare to zero-shot (run_style_study.py, same test set): 0.4016 (396/986)")
    print()
    print(classification_report(y_test, y_pred, labels=CLASSES, digits=4))
    print("Confusion matrix (rows=true, columns=predicted):")
    cm = confusion_matrix(y_test, y_pred, labels=CLASSES)
    header = "".join(f"{c[:10]:>11s}" for c in CLASSES)
    print(f"{'':15s}{header}")
    for true_style, row in zip(CLASSES, cm):
        row_str = "".join(f"{v:>11d}" for v in row)
        print(f"{true_style:15s}{row_str}")


if __name__ == "__main__":
    run_study()

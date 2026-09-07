#!/usr/bin/env python3
"""
Classify an arbitrary image's interior style — a real, runnable proof of
D005, independent of the rest of the pipeline (no DB, no fixtures needed).

Usage:
    source .venv/bin/activate
    python -m ai.style_recognition.cli path/to/room_photo.jpg
"""
from __future__ import annotations

import sys

from PIL import Image

from ai.style_recognition.classifier import classify_style


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python -m ai.style_recognition.cli <image_path>")
        return 1

    image = Image.open(sys.argv[1])
    result = classify_style(image)

    print(f"Detected Style: {result.predicted_style}")
    print(f"Confidence: {result.confidence:.0%}")
    if result.abstained:
        print("⚠ Confidence is low — this prediction should not be treated as certain.")
    print("Alternatives:")
    for alt in result.alternatives:
        print(f"  {alt['style']:15s} {alt['confidence']:.0%}")
    print(f"(model: {result.model_name})")
    return 0


if __name__ == "__main__":
    sys.exit(main())

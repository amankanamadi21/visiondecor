"""
Interior style recognition (decision D005): CLIP-RN50 zero-shot classification.

Model: 'RN50-quickgelu' with 'openai' pretrained weights (open_clip_torch).
The '-quickgelu' suffix matters and is not optional — plain 'RN50' loads with
a mismatched activation function relative to how the OpenAI weights were
actually trained (open_clip warns about this explicitly; verified by loading
both variants and confirming only '-quickgelu' produces zero warnings).

This is genuinely a CNN (RN50 = ResNet-50), satisfying FR-3's "CNN-based"
wording, with NO training step — CLIP's image/text encoders are used exactly
as pretrained, matching D005 and the project's "no training" constraint.

Zero-shot mechanism: each of the six FR-3 style labels is expanded into
several prompt templates (a standard CLIP technique — the original CLIP
paper itself uses "prompt ensembling" for zero-shot ImageNet), the resulting
text embeddings are averaged per class, and cosine similarity against the
image embedding is turned into a probability distribution via softmax. The
top class is the prediction; if its probability doesn't clear
ABSTAIN_CONFIDENCE_THRESHOLD, `abstained=True` is set — brief PART 4 requires
the system to say "I don't know" rather than assert a style with false
certainty.

⚠ Zero-shot accuracy on six mutually confusable interior styles is an
empirical question, not a settled one — see evaluation/run_style_study.py
for the actual measured numbers. Nothing here should be described as
"accurate" independent of that measurement.
"""
from __future__ import annotations

from dataclasses import dataclass

import torch
from PIL import Image

MODEL_NAME = "RN50-quickgelu"
PRETRAINED_TAG = "openai"

FR3_STYLES = ["Modern", "Minimalist", "Contemporary", "Traditional", "Industrial", "Scandinavian"]

# Prompt ensembling — averaging several phrasings per class is a standard,
# well-documented zero-shot CLIP technique, not a form of training.
PROMPT_TEMPLATES = [
    "a photo of a {style} style interior room",
    "an interior room decorated in {style} style",
    "{style} style home decor and furniture",
    "a photograph of a {style} living space",
]

ABSTAIN_CONFIDENCE_THRESHOLD = 0.35  # ~2x the 6-class uniform baseline (0.167)

_model = None
_preprocess = None
_tokenizer = None
_text_features_cache = None  # computed once — the style label set is fixed


@dataclass
class StyleClassificationResult:
    predicted_style: str
    confidence: float
    alternatives: list[dict]  # [{"style": ..., "confidence": ...}, ...] — all 6, sorted descending
    abstained: bool
    model_name: str


def _load_model():
    global _model, _preprocess, _tokenizer
    if _model is None:
        import open_clip

        _model, _, _preprocess = open_clip.create_model_and_transforms(MODEL_NAME, pretrained=PRETRAINED_TAG)
        _tokenizer = open_clip.get_tokenizer(MODEL_NAME)
        _model.eval()
    return _model, _preprocess, _tokenizer


def _get_text_features():
    global _text_features_cache
    if _text_features_cache is not None:
        return _text_features_cache

    model, _, tokenizer = _load_model()
    all_features = []
    with torch.no_grad():
        for style in FR3_STYLES:
            prompts = [t.format(style=style.lower()) for t in PROMPT_TEMPLATES]
            tokens = tokenizer(prompts)
            features = model.encode_text(tokens)
            features /= features.norm(dim=-1, keepdim=True)
            all_features.append(features.mean(dim=0))  # average the ensembled prompts for this class
    _text_features_cache = torch.stack(all_features)
    _text_features_cache /= _text_features_cache.norm(dim=-1, keepdim=True)
    return _text_features_cache


def encode_image_features(image: Image.Image):
    """Raw, L2-normalized CLIP image embedding (1024-dim for RN50) — no
    text/zero-shot step. Exposed so evaluation/run_style_head_study.py can
    reuse the exact same frozen encoder for the D005 upgrade-path comparison
    (a logistic-regression head fit on top of these features) without
    duplicating model-loading logic."""
    model, preprocess, _ = _load_model()
    if image.mode != "RGB":
        image = image.convert("RGB")
    image_tensor = preprocess(image).unsqueeze(0)
    with torch.no_grad():
        features = model.encode_image(image_tensor)
        features /= features.norm(dim=-1, keepdim=True)
    return features[0].numpy()


def classify_style(image: Image.Image) -> StyleClassificationResult:
    model, preprocess, _ = _load_model()
    text_features = _get_text_features()

    if image.mode != "RGB":
        image = image.convert("RGB")
    image_tensor = preprocess(image).unsqueeze(0)

    with torch.no_grad():
        image_features = model.encode_image(image_tensor)
        image_features /= image_features.norm(dim=-1, keepdim=True)
        similarity = (100.0 * image_features @ text_features.T).softmax(dim=-1)

    probs = similarity[0].tolist()
    ranked = sorted(zip(FR3_STYLES, probs), key=lambda p: p[1], reverse=True)

    top_style, top_confidence = ranked[0]
    return StyleClassificationResult(
        predicted_style=top_style,
        confidence=round(top_confidence, 4),
        alternatives=[{"style": s, "confidence": round(c, 4)} for s, c in ranked[1:]],
        abstained=should_abstain(top_confidence),
        model_name=f"clip-{MODEL_NAME}-{PRETRAINED_TAG}",
    )


def should_abstain(confidence: float) -> bool:
    """Separated from classify_style so the threshold decision itself is
    testable with controlled inputs, rather than only via a real model's
    output landing on one side of a boundary — a brittle way to test a
    threshold comparison (see tests/test_style_recognition.py)."""
    return confidence < ABSTAIN_CONFIDENCE_THRESHOLD

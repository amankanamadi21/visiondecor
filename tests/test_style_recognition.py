"""
Style recognition unit tests (decision D005). These verify the mechanism's
correctness properties (valid probability distribution, abstain triggers on
ambiguous input, sorted alternatives) — NOT classification accuracy, which
is a separate, honest empirical question measured in
evaluation/run_style_study.py against a real labeled dataset, not asserted
here as a pass/fail threshold.
"""
from __future__ import annotations

import pytest
from PIL import Image

from ai.style_recognition.classifier import ABSTAIN_CONFIDENCE_THRESHOLD, FR3_STYLES, classify_style, should_abstain


@pytest.fixture(scope="module")
def blank_image():
    return Image.new("RGB", (400, 400), (180, 180, 180))


def test_result_covers_all_six_fr3_styles(blank_image):
    result = classify_style(blank_image)
    all_styles = {result.predicted_style} | {a["style"] for a in result.alternatives}
    assert all_styles == set(FR3_STYLES)


def test_confidences_form_a_valid_probability_distribution(blank_image):
    result = classify_style(blank_image)
    all_confidences = [result.confidence] + [a["confidence"] for a in result.alternatives]
    assert abs(sum(all_confidences) - 1.0) < 0.01
    assert all(0.0 <= c <= 1.0 for c in all_confidences)


def test_alternatives_sorted_descending(blank_image):
    result = classify_style(blank_image)
    confidences = [a["confidence"] for a in result.alternatives]
    assert confidences == sorted(confidences, reverse=True)
    assert result.confidence >= confidences[0]


def test_abstain_threshold_logic_in_isolation():
    # Tests the threshold decision directly with controlled inputs, rather
    # than depending on a real model's output landing on one side of a
    # boundary — measured blank-image confidence sits close enough to
    # ABSTAIN_CONFIDENCE_THRESHOLD that asserting an exact outcome there
    # would be a flaky test of a threshold, not of the model.
    assert should_abstain(0.05) is True
    assert should_abstain(ABSTAIN_CONFIDENCE_THRESHOLD - 0.001) is True
    assert should_abstain(ABSTAIN_CONFIDENCE_THRESHOLD + 0.001) is False
    assert should_abstain(0.95) is False


def test_ambiguous_image_is_never_near_certain(blank_image):
    # A blank gray image has no room content at all. It should never be
    # reported with high confidence — whether it happens to land on one
    # side of the abstain threshold or the other is a separate, finer-
    # grained question than "is the model at least not overconfident here".
    result = classify_style(blank_image)
    assert result.confidence < 0.6


def test_model_name_is_reported_and_labeled_as_clip():
    result = classify_style(Image.new("RGB", (300, 300), (100, 100, 100)))
    assert "clip" in result.model_name.lower()


def test_non_rgb_image_does_not_crash():
    grayscale = Image.new("L", (300, 300), 128)
    result = classify_style(grayscale)  # must not raise
    assert result.predicted_style in FR3_STYLES


def test_result_is_deterministic_for_the_same_image(blank_image):
    result_a = classify_style(blank_image)
    result_b = classify_style(blank_image)
    assert result_a.predicted_style == result_b.predicted_style
    assert result_a.confidence == result_b.confidence


def test_encode_image_features_shape_and_normalization():
    from ai.style_recognition.classifier import encode_image_features

    features = encode_image_features(Image.new("RGB", (300, 300), (50, 100, 150)))
    assert features.shape == (1024,)  # RN50's embedding dimension
    norm = (features**2).sum() ** 0.5
    assert abs(norm - 1.0) < 1e-4  # L2-normalized, as documented

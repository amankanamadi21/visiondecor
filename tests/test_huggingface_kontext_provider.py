"""
Hugging Face Kontext provider tests (decision D003 extension, 2026-09-18) —
the genuine image-editing fallback added when the user needed real structure
preservation without paying for Gemini billing. Unit tests mock the HTTP
layer (no network, no credentials needed). One additional test makes REAL
network calls (the edit request AND the image-fetch request) and is skipped
automatically when HUGGINGFACE_API_TOKEN isn't set, so the suite still passes
without live credentials — but proves the integration for real when present.
"""
from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest
from dotenv import load_dotenv

from ai.visualization.providers.base import RenderUnavailableError
from ai.visualization.providers.huggingface_kontext import HuggingFaceKontextProvider

# Must run at import time, before the skipif condition below is evaluated —
# pytest evaluates skipif conditions at collection time (same fix already
# applied in test_cloudflare_provider.py / test_huggingface_provider.py).
load_dotenv()


def test_missing_token_raises_unavailable_not_a_crash():
    with pytest.raises(RenderUnavailableError):
        HuggingFaceKontextProvider("")


def test_successful_response_fetches_and_returns_image_bytes():
    provider = HuggingFaceKontextProvider("fake-token")
    fake_image_bytes = b"\xff\xd8\xff\xe0fake-jpeg-bytes"

    edit_response = MagicMock(status_code=200)
    edit_response.json.return_value = {"images": [{"url": "https://v3b.fal.media/files/fake.jpg"}]}
    fetch_response = MagicMock(status_code=200, content=fake_image_bytes)

    with patch("requests.post", return_value=edit_response), patch("requests.get", return_value=fetch_response):
        result = provider.render(b"unused-photo-bytes", "scandinavian style, same layout")
    assert result == fake_image_bytes


def test_non_200_status_on_edit_call_raises_unavailable():
    provider = HuggingFaceKontextProvider("fake-token")
    fake_response = MagicMock(status_code=400, text='{"error":"Model not supported by provider fal-ai"}')
    with patch("requests.post", return_value=fake_response):
        with pytest.raises(RenderUnavailableError, match="400"):
            provider.render(b"photo", "prompt")


def test_missing_images_with_200_status_raises_unavailable():
    provider = HuggingFaceKontextProvider("fake-token")
    fake_response = MagicMock(status_code=200)
    fake_response.json.return_value = {"images": []}
    with patch("requests.post", return_value=fake_response):
        with pytest.raises(RenderUnavailableError):
            provider.render(b"photo", "prompt")


def test_malformed_json_raises_unavailable():
    provider = HuggingFaceKontextProvider("fake-token")
    fake_response = MagicMock(status_code=200)
    fake_response.json.side_effect = ValueError("not json")
    with patch("requests.post", return_value=fake_response):
        with pytest.raises(RenderUnavailableError):
            provider.render(b"photo", "prompt")


def test_network_exception_on_edit_call_raises_unavailable():
    provider = HuggingFaceKontextProvider("fake-token")
    with patch("requests.post", side_effect=ConnectionError("network down")):
        with pytest.raises(RenderUnavailableError):
            provider.render(b"photo", "prompt")


def test_failed_image_fetch_raises_unavailable():
    provider = HuggingFaceKontextProvider("fake-token")
    edit_response = MagicMock(status_code=200)
    edit_response.json.return_value = {"images": [{"url": "https://v3b.fal.media/files/fake.jpg"}]}
    fetch_response = MagicMock(status_code=404)
    with patch("requests.post", return_value=edit_response), patch("requests.get", return_value=fetch_response):
        with pytest.raises(RenderUnavailableError):
            provider.render(b"photo", "prompt")


def test_structure_preserving_is_true():
    # Verified fact (see module docstring, live-tested against a real
    # uploaded photo) — this is the entire reason this provider exists.
    assert HuggingFaceKontextProvider.structure_preserving is True


@pytest.mark.skipif(
    not os.environ.get("HUGGINGFACE_API_TOKEN"),
    reason="requires a real HUGGINGFACE_API_TOKEN in the environment",
)
def test_real_live_call_edits_a_real_photo():
    """Not mocked — actual network calls to Hugging Face's router and fal's
    CDN. Skipped automatically wherever credentials aren't configured (e.g.
    CI), but proves the real integration works when they are.

    2026-09-18: discovered live that fal-ai-routed image-EDIT calls draw
    from a much smaller slice of Hugging Face's shared free monthly credit
    allotment than the plain text-to-image (nscale) route used by the
    sibling HuggingFaceImageProvider — a handful of manual verification
    calls during this same session were enough to exhaust it (HTTP 402,
    "You have depleted your monthly included credits"), while the
    text-to-image route kept returning 200 on the identical token. This is
    a real, disclosed account-level resource constraint, not a code defect
    — treated as a skip here (with the response surfaced, not swallowed)
    rather than a hard failure, so the suite doesn't go red every time this
    specific free quota (distinct from the sibling provider's) runs dry."""
    fixture_path = os.path.join(
        os.path.dirname(__file__), "..", "frontend", "public", "samples", "living_room_modern_cluttered.jpg"
    )
    if not os.path.exists(fixture_path):
        pytest.skip("sample room fixture image not found")
    with open(fixture_path, "rb") as f:
        photo_bytes = f.read()

    provider = HuggingFaceKontextProvider(os.environ["HUGGINGFACE_API_TOKEN"].strip())
    try:
        image_bytes = provider.render(photo_bytes, "Scandinavian style, white and natural wood palette")
    except RenderUnavailableError as exc:
        if "depleted" in str(exc).lower() or "402" in str(exc):
            pytest.skip(f"Hugging Face Kontext free credit allotment exhausted: {exc}")
        raise
    assert len(image_bytes) > 1000

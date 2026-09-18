"""
OpenAI image-edit provider tests (added 2026-09-18, paid alternative to the
exhausted free structure-preserving options). Unit tests mock the HTTP layer
(no network, no cost). The one live test that spends real money is gated
behind an EXPLICIT opt-in env var (RUN_LIVE_OPENAI_TEST=1), not just "token
present" — the Hugging Face providers' skip-if-token-present live tests ran
on every single pytest invocation this session and burned through that
entire free credit pool in a few hours; a paid key must not repeat that
mistake (explicit user instruction: minimal usage, never overused).
"""
from __future__ import annotations

import base64
import os
from unittest.mock import MagicMock, patch

import pytest
from dotenv import load_dotenv

from ai.visualization.providers.base import RenderUnavailableError
from ai.visualization.providers.openai_edit import OpenAIImageEditProvider

# Must run at import time, before the skipif condition below is evaluated —
# pytest evaluates skipif conditions at collection time.
load_dotenv()

_TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


def test_missing_key_raises_unavailable_not_a_crash():
    with pytest.raises(RenderUnavailableError):
        OpenAIImageEditProvider("")


def test_successful_response_decodes_base64_image():
    provider = OpenAIImageEditProvider("fake-key")
    fake_image_bytes = b"\x89PNG\r\n\x1a\nfake-png-bytes"
    fake_response = MagicMock(status_code=200)
    fake_response.json.return_value = {"data": [{"b64_json": base64.b64encode(fake_image_bytes).decode("ascii")}]}
    with patch("requests.post", return_value=fake_response):
        result = provider.render(_TINY_PNG, "scandinavian style, same layout")
    assert result == fake_image_bytes


def test_non_200_status_raises_unavailable():
    provider = OpenAIImageEditProvider("fake-key")
    fake_response = MagicMock(status_code=400, text='{"error": {"message": "invalid_request"}}')
    with patch("requests.post", return_value=fake_response):
        with pytest.raises(RenderUnavailableError, match="400"):
            provider.render(_TINY_PNG, "prompt")


def test_missing_data_with_200_status_raises_unavailable():
    provider = OpenAIImageEditProvider("fake-key")
    fake_response = MagicMock(status_code=200)
    fake_response.json.return_value = {"data": []}
    with patch("requests.post", return_value=fake_response):
        with pytest.raises(RenderUnavailableError):
            provider.render(_TINY_PNG, "prompt")


def test_malformed_json_raises_unavailable():
    provider = OpenAIImageEditProvider("fake-key")
    fake_response = MagicMock(status_code=200)
    fake_response.json.side_effect = ValueError("not json")
    with patch("requests.post", return_value=fake_response):
        with pytest.raises(RenderUnavailableError):
            provider.render(_TINY_PNG, "prompt")


def test_network_exception_raises_unavailable_not_propagated():
    provider = OpenAIImageEditProvider("fake-key")
    with patch("requests.post", side_effect=ConnectionError("network down")):
        with pytest.raises(RenderUnavailableError):
            provider.render(_TINY_PNG, "prompt")


def test_unreadable_photo_bytes_raise_unavailable_before_any_network_call():
    provider = OpenAIImageEditProvider("fake-key")
    with patch("requests.post") as mock_post:
        with pytest.raises(RenderUnavailableError):
            provider.render(b"not an image", "prompt")
    mock_post.assert_not_called()  # never spend a call on an input we can't even prepare


def test_request_uses_low_quality_by_default():
    # Cost-discipline regression guard: quality must never silently drift to
    # a more expensive default.
    provider = OpenAIImageEditProvider("fake-key")
    fake_response = MagicMock(status_code=200)
    fake_response.json.return_value = {"data": [{"b64_json": base64.b64encode(b"x").decode("ascii")}]}
    with patch("requests.post", return_value=fake_response) as mock_post:
        provider.render(_TINY_PNG, "prompt")
    _, kwargs = mock_post.call_args
    assert kwargs["data"]["quality"] == "low"


def test_structure_preserving_is_true():
    assert OpenAIImageEditProvider.structure_preserving is True


@pytest.mark.skipif(
    not (os.environ.get("OPENAI_API_KEY") and os.environ.get("RUN_LIVE_OPENAI_TEST") == "1"),
    reason="requires OPENAI_API_KEY AND explicit RUN_LIVE_OPENAI_TEST=1 opt-in — this test spends real money",
)
def test_real_live_call_edits_a_real_photo():
    """The ONE real, paid call for this provider. Deliberately does not run
    just because a key is present — see module docstring."""
    fixture_path = os.path.join(
        os.path.dirname(__file__), "..", "frontend", "public", "samples", "living_room_modern_cluttered.jpg"
    )
    if not os.path.exists(fixture_path):
        pytest.skip("sample room fixture image not found")
    with open(fixture_path, "rb") as f:
        photo_bytes = f.read()

    provider = OpenAIImageEditProvider(os.environ["OPENAI_API_KEY"].strip())
    image_bytes = provider.render(photo_bytes, "Scandinavian style, white and natural wood palette")
    assert len(image_bytes) > 1000

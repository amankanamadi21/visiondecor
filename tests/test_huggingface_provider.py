"""
Hugging Face provider tests (decision D003, third fallback link). Unit tests
mock the HTTP layer (no network, no credentials needed) to verify response
parsing and error handling. One additional test makes a REAL network call
and is skipped automatically when HUGGINGFACE_API_TOKEN isn't set, so the
suite still passes in an environment without live credentials — but proves
the integration for real when they are present.
"""
from __future__ import annotations

import base64
import os
from unittest.mock import MagicMock, patch

import pytest
from dotenv import load_dotenv

from ai.visualization.providers.base import RenderUnavailableError
from ai.visualization.providers.huggingface import HuggingFaceImageProvider

# Must run at import time, BEFORE the skipif condition below is evaluated —
# calling load_dotenv() only inside the test body would be too late, since
# pytest evaluates skipif conditions at collection time (a real bug caught
# and fixed in the Cloudflare provider's tests — same fix applied here from
# the start).
load_dotenv()


def test_missing_token_raises_unavailable_not_a_crash():
    with pytest.raises(RenderUnavailableError):
        HuggingFaceImageProvider("")


def test_successful_response_decodes_base64_image():
    provider = HuggingFaceImageProvider("fake-token")
    fake_image_bytes = b"\x89PNG\r\n\x1a\nfake-png-bytes"
    fake_response = MagicMock(status_code=200)
    fake_response.json.return_value = {
        "created": 123,
        "data": [{"b64_json": base64.b64encode(fake_image_bytes).decode("ascii")}],
    }
    with patch("requests.post", return_value=fake_response):
        result = provider.render(b"unused-photo-bytes", "a modern living room")
    assert result == fake_image_bytes


def test_non_200_status_raises_unavailable():
    provider = HuggingFaceImageProvider("fake-token")
    fake_response = MagicMock(status_code=401, text='{"error":"Invalid username or password."}')
    with patch("requests.post", return_value=fake_response):
        with pytest.raises(RenderUnavailableError, match="401"):
            provider.render(b"photo", "prompt")


def test_missing_data_with_200_status_raises_unavailable():
    provider = HuggingFaceImageProvider("fake-token")
    fake_response = MagicMock(status_code=200)
    fake_response.json.return_value = {"created": 123, "data": []}
    with patch("requests.post", return_value=fake_response):
        with pytest.raises(RenderUnavailableError):
            provider.render(b"photo", "prompt")


def test_malformed_json_raises_unavailable():
    provider = HuggingFaceImageProvider("fake-token")
    fake_response = MagicMock(status_code=200)
    fake_response.json.side_effect = ValueError("not json")
    with patch("requests.post", return_value=fake_response):
        with pytest.raises(RenderUnavailableError):
            provider.render(b"photo", "prompt")


def test_network_exception_raises_unavailable_not_propagated():
    provider = HuggingFaceImageProvider("fake-token")
    with patch("requests.post", side_effect=ConnectionError("network down")):
        with pytest.raises(RenderUnavailableError):
            provider.render(b"photo", "prompt")


def test_structure_preserving_is_false():
    # Verified fact (see module docstring), not a default — a regression
    # here would silently mislead the UI's disclosure to the user.
    assert HuggingFaceImageProvider.structure_preserving is False


@pytest.mark.skipif(
    not os.environ.get("HUGGINGFACE_API_TOKEN"),
    reason="requires a real HUGGINGFACE_API_TOKEN in the environment",
)
def test_real_live_call_produces_a_valid_image():
    """Not mocked — an actual network call to Hugging Face's router API.
    Skipped automatically wherever credentials aren't configured (e.g. CI),
    but proves the real integration works when they are."""
    provider = HuggingFaceImageProvider(os.environ["HUGGINGFACE_API_TOKEN"].strip())
    image_bytes = provider.render(b"unused", "a photorealistic modern living room, wide shot")
    assert len(image_bytes) > 1000
    assert image_bytes[:8] == b"\x89PNG\r\n\x1a\n"  # real PNG magic bytes

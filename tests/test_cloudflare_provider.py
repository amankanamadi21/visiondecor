"""
Cloudflare Workers AI provider tests (decision D003). Unit tests mock the
HTTP layer (no network, no credentials needed) to verify response parsing
and error handling. One additional test makes a REAL network call and is
skipped automatically when CLOUDFLARE_ACCOUNT_ID/CLOUDFLARE_API_TOKEN
aren't set, so the suite still passes in an environment without live
credentials — but proves the integration for real when they are present.
"""
from __future__ import annotations

import base64
import os
from unittest.mock import MagicMock, patch

import pytest
from dotenv import load_dotenv

from ai.visualization.providers.base import RenderUnavailableError
from ai.visualization.providers.cloudflare import CloudflareImageProvider

# Must run at import time, BEFORE the skipif condition below is evaluated —
# calling load_dotenv() only inside the test body would be too late, since
# pytest evaluates skipif conditions at collection time.
load_dotenv()


def test_missing_credentials_raises_unavailable_not_a_crash():
    with pytest.raises(RenderUnavailableError):
        CloudflareImageProvider("", "")
    with pytest.raises(RenderUnavailableError):
        CloudflareImageProvider("account-id", "")


def test_successful_response_decodes_base64_image():
    provider = CloudflareImageProvider("fake-account", "fake-token")
    fake_image_bytes = b"\xff\xd8\xff\xe0fake-jpeg-bytes"
    fake_response = MagicMock(status_code=200)
    fake_response.json.return_value = {
        "result": {"image": base64.b64encode(fake_image_bytes).decode("ascii")},
        "success": True,
    }
    with patch("requests.post", return_value=fake_response):
        result = provider.render(b"unused-photo-bytes", "a modern living room")
    assert result == fake_image_bytes


def test_non_200_status_raises_unavailable():
    provider = CloudflareImageProvider("fake-account", "fake-token")
    fake_response = MagicMock(status_code=403, text='{"errors":[{"message":"not allowed"}]}')
    with patch("requests.post", return_value=fake_response):
        with pytest.raises(RenderUnavailableError, match="403"):
            provider.render(b"photo", "prompt")


def test_success_false_with_200_status_raises_unavailable():
    # Defensive case: even if Cloudflare ever returns 200 with success=false,
    # this must not be treated as a valid image.
    provider = CloudflareImageProvider("fake-account", "fake-token")
    fake_response = MagicMock(status_code=200)
    fake_response.json.return_value = {"success": False, "result": {}, "errors": [{"message": "quota"}]}
    with patch("requests.post", return_value=fake_response):
        with pytest.raises(RenderUnavailableError):
            provider.render(b"photo", "prompt")


def test_malformed_json_raises_unavailable():
    provider = CloudflareImageProvider("fake-account", "fake-token")
    fake_response = MagicMock(status_code=200)
    fake_response.json.side_effect = ValueError("not json")
    with patch("requests.post", return_value=fake_response):
        with pytest.raises(RenderUnavailableError):
            provider.render(b"photo", "prompt")


def test_network_exception_raises_unavailable_not_propagated():
    provider = CloudflareImageProvider("fake-account", "fake-token")
    with patch("requests.post", side_effect=ConnectionError("network down")):
        with pytest.raises(RenderUnavailableError):
            provider.render(b"photo", "prompt")


def test_structure_preserving_is_false():
    # Verified fact (see module docstring), not a default — a regression
    # here would silently mislead the UI's disclosure to the user.
    assert CloudflareImageProvider.structure_preserving is False


@pytest.mark.skipif(
    not (os.environ.get("CLOUDFLARE_ACCOUNT_ID") and os.environ.get("CLOUDFLARE_API_TOKEN")),
    reason="requires real CLOUDFLARE_ACCOUNT_ID/CLOUDFLARE_API_TOKEN in the environment",
)
def test_real_live_call_produces_a_valid_image():
    """Not mocked — an actual network call to Cloudflare Workers AI. Skipped
    automatically wherever credentials aren't configured (e.g. CI), but
    proves the real integration works when they are."""
    provider = CloudflareImageProvider(
        os.environ["CLOUDFLARE_ACCOUNT_ID"].strip(), os.environ["CLOUDFLARE_API_TOKEN"].strip()
    )
    image_bytes = provider.render(b"unused", "a photorealistic modern living room, wide shot")
    assert len(image_bytes) > 1000
    assert image_bytes[:3] == b"\xff\xd8\xff"  # real JPEG magic bytes

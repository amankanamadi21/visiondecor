"""
OpenAI image-editing provider — genuine image-to-image editing via
POST /v1/images/edits (gpt-image-1-mini), added 2026-09-18 because both free
structure-preserving options (Gemini's free tier, Hugging Face Kontext's
free credit pool) were exhausted and the user offered a paid key they
already had rather than wait for a free-tier reset.

Deliberately NOT gpt-image-1 (the original model) — it's being retired
2026-10-23. gpt-image-1-mini is the cheap variant (a few cents per edit at
most, well under a cent at low quality/1024x1024) and still does real image
editing, not text-to-image.

Cost discipline (explicit user instruction, 2026-09-18 — "usage of key is
as minimal as possible, and is not overused"): `quality="low"` is
hardcoded, not exposed as a caller-settable knob that could accidentally
get cranked up. There is exactly ONE live, real-money test for this
provider, gated behind an explicit opt-in env var (RUN_LIVE_OPENAI_TEST=1)
rather than "runs whenever the key happens to be set" — that exact
skip-if-token-present pattern on the Hugging Face providers ran on every
single pytest invocation this session and burned through that entire free
credit pool in a few hours. A paid key must not repeat that mistake.
"""
from __future__ import annotations

import base64
import io

from PIL import Image

from ai.visualization.providers.base import RenderProvider, RenderUnavailableError, post_multipart_or_raise

API_URL = "https://api.openai.com/v1/images/edits"
MODEL_NAME = "gpt-image-1-mini"
REQUEST_TIMEOUT_S = 90


class OpenAIImageEditProvider(RenderProvider):
    name = "openai"
    structure_preserving = True  # genuine image-to-image editing via /v1/images/edits

    def __init__(self, api_key: str):
        if not api_key:
            raise RenderUnavailableError("OpenAI provider requires OPENAI_API_KEY.")
        self._api_key = api_key

    def render(self, room_photo_bytes: bytes, prompt: str) -> bytes:
        # The edits endpoint requires PNG — converted defensively here
        # rather than risking a wasted paid call on a format-rejection 400
        # (uploads are stored as JPEG).
        try:
            image = Image.open(io.BytesIO(room_photo_bytes)).convert("RGBA")
            png_buffer = io.BytesIO()
            image.save(png_buffer, format="PNG")
        except Exception as exc:  # noqa: BLE001
            raise RenderUnavailableError(f"Could not prepare the photo for OpenAI's edit endpoint: {exc}") from exc

        payload = post_multipart_or_raise(
            "OpenAI",
            API_URL,
            {"Authorization": f"Bearer {self._api_key}"},
            {"image": ("room.png", png_buffer.getvalue(), "image/png")},
            {"model": MODEL_NAME, "prompt": prompt, "quality": "low", "size": "1024x1024"},
            REQUEST_TIMEOUT_S,
        )

        data = payload.get("data") or []
        if not data or "b64_json" not in data[0]:
            raise RenderUnavailableError(f"OpenAI response missing image data: {payload}")

        return base64.b64decode(data[0]["b64_json"])

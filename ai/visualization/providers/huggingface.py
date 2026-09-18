"""
Hugging Face Inference provider (decisions D003/D023) — the third link in
the render-provider fallback chain (Gemini -> Cloudflare -> Hugging Face ->
cache -> deterministic floor plan).

⚠ TEXT-TO-IMAGE ONLY, not image editing — `structure_preserving = False`
below is a verified fact, not an assumption. HF's own Inference API has
moved to a multi-provider "router" model since this project's original D003
research: the classic `api-inference.huggingface.co/models/<id>` endpoint
returns an HTML login page (not a clean API error) for FLUX.1-schnell, and
that model's own `inferenceProviderMapping` (queried live via
`GET https://huggingface.co/api/models/<id>?expand=inferenceProviderMapping`)
shows `hf-inference` is not among its live providers — confirmed via a real
401/410 before finding the working route. The working endpoint, confirmed
with a real authenticated call producing a real, viewed PNG (2026-09-08):

    POST https://router.huggingface.co/nscale/v1/images/generations
    Authorization: Bearer <token>
    {"model": "black-forest-labs/FLUX.1-schnell", "prompt": "..."}
    -> 200 {"created": ..., "data": [{"b64_json": "<base64 PNG>"}]}
       (OpenAI Images-API-compatible shape — nscale is one of several
       providers HF routes this model to; the others (fal-ai, wavespeed)
       were not tried since nscale already worked)

Error shape, also confirmed live: a non-200 response is
`{"error": "<message>"}` (e.g. 400 for an unsupported model, 401 for a bad
token) — much simpler than Cloudflare's nested `{"success": false, ...}`.

Because this provider never sees the room photo at all (no image input in
the request), the room's real walls/windows/doors are not preserved by any
mechanism — same disclosure reasoning as the Cloudflare provider.
"""
from __future__ import annotations

import base64

from ai.visualization.providers.base import RenderProvider, RenderUnavailableError, post_json_or_raise

API_URL = "https://router.huggingface.co/nscale/v1/images/generations"
MODEL_NAME = "black-forest-labs/FLUX.1-schnell"
REQUEST_TIMEOUT_S = 60


class HuggingFaceImageProvider(RenderProvider):
    name = "huggingface"
    structure_preserving = False  # verified fact, not a guess — see module docstring

    def __init__(self, api_token: str):
        if not api_token:
            raise RenderUnavailableError("Hugging Face provider requires HUGGINGFACE_API_TOKEN.")
        self._api_token = api_token

    def render(self, room_photo_bytes: bytes, prompt: str) -> bytes:
        # room_photo_bytes is intentionally unused — this provider cannot
        # accept an input image (see module docstring); the interface still
        # accepts it uniformly across providers so render_service.py doesn't
        # need per-provider branching.
        payload = post_json_or_raise(
            "Hugging Face",
            API_URL,
            {"Authorization": f"Bearer {self._api_token}"},
            {"model": MODEL_NAME, "prompt": prompt},
            REQUEST_TIMEOUT_S,
        )

        data = payload.get("data") or []
        if not data or "b64_json" not in data[0]:
            raise RenderUnavailableError(f"Hugging Face response missing image data: {payload}")

        return base64.b64decode(data[0]["b64_json"])

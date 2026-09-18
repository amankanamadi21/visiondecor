"""
Hugging Face "Kontext" image-EDITING provider (decision D003, extended
2026-09-18) — genuine image-to-image editing, not text-to-image like the
other two fallbacks (Cloudflare, HuggingFaceImageProvider).

Context: Gemini (the only other structure_preserving=True provider) now
requires billing — its free tier quota is 0 (see gemini.py's docstring).
The user cannot pay for that, but still wants the room's real structure
preserved rather than a fresh, unrelated room from a text-to-image model.
Researched and LIVE-VERIFIED 2026-09-18, against a real uploaded room photo,
using the same free HUGGINGFACE_API_TOKEN already used by the sibling
text-to-image provider:

    GET https://huggingface.co/api/models/black-forest-labs/FLUX.1-Kontext-dev
        ?expand=inferenceProviderMapping
    -> confirms fal-ai/replicate/wavespeed all serve this model live with
       task "image-to-image" (not text-to-image)

    POST https://router.huggingface.co/fal-ai/fal-ai/flux-kontext/dev
    Authorization: Bearer <token>
    {"prompt": "...", "image_url": "data:image/jpeg;base64,<...>"}
    -> 200 {"images": [{"url": "https://...fal.media/.../<file>.jpg", ...}]}

The response is a URL to the generated image (fal's own CDN), not inline
base64 — a second GET is required to fetch the actual bytes. Verified on a
real uploaded photo (not a mock/fixture asset): the room's walls, window art,
sofa/chair shapes, and furniture layout were all preserved; only the
color/style palette changed per the prompt, as requested. No billing was
required for this call — it uses the same free-tier token as the sibling
text-to-image Hugging Face provider (HuggingFaceImageProvider), so it carries
the same caveat: a shared monthly credit allotment, not unlimited.
"""
from __future__ import annotations

import base64

from ai.visualization.providers.base import RenderProvider, RenderUnavailableError, post_json_or_raise

API_URL = "https://router.huggingface.co/fal-ai/fal-ai/flux-kontext/dev"
MODEL_NAME = "black-forest-labs/FLUX.1-Kontext-dev"
REQUEST_TIMEOUT_S = 90


class HuggingFaceKontextProvider(RenderProvider):
    name = "huggingface_kontext"
    structure_preserving = True  # genuine image-to-image editing — see module docstring

    def __init__(self, api_token: str):
        if not api_token:
            raise RenderUnavailableError("Hugging Face Kontext provider requires HUGGINGFACE_API_TOKEN.")
        self._api_token = api_token

    def render(self, room_photo_bytes: bytes, prompt: str) -> bytes:
        import requests

        data_uri = f"data:image/jpeg;base64,{base64.b64encode(room_photo_bytes).decode('ascii')}"
        payload = post_json_or_raise(
            "Hugging Face Kontext",
            API_URL,
            {"Authorization": f"Bearer {self._api_token}"},
            {"prompt": prompt, "image_url": data_uri},
            REQUEST_TIMEOUT_S,
        )

        images = payload.get("images") or []
        if not images or "url" not in images[0]:
            raise RenderUnavailableError(f"Hugging Face Kontext response missing image data: {payload}")

        image_url = images[0]["url"]
        try:
            image_response = requests.get(image_url, timeout=REQUEST_TIMEOUT_S)
        except Exception as exc:  # noqa: BLE001
            raise RenderUnavailableError(f"Failed to fetch Hugging Face Kontext output image: {exc}") from exc

        if image_response.status_code != 200:
            raise RenderUnavailableError(
                f"Fetching Hugging Face Kontext output image returned HTTP {image_response.status_code}"
            )

        return image_response.content

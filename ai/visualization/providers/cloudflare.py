"""
Cloudflare Workers AI image-generation provider (decisions D003/D023).

⚠ TEXT-TO-IMAGE ONLY, not image editing — `structure_preserving = False`
below is not a placeholder, it's the honest, verified fact about this
provider. It was checked empirically, not assumed:
  - The dedicated img2img model (@cf/runwayml/stable-diffusion-v1-5-img2img)
    returned HTTP 403 "This account is not allowed to access" this model on
    a free Workers AI account.
  - stable-diffusion-xl-base-1.0 was also tried with an `image_b64` input
    and rejected with "input tensor `image` is not present in the model" —
    i.e. that model genuinely has no image-input capability at all on this
    platform, contrary to some marketing copy describing it as able to
    "modify images based on text prompts".
  - @cf/black-forest-labs/flux-1-schnell (pure text-to-image) DOES work on
    a free account — confirmed with a real call. This provider uses that.

Because this provider never sees the room photo at all, the room's real
walls/windows/doors are not preserved by any mechanism — the render is a
plausible room matching the prompt's style/palette/placement description,
nothing more. This is exactly what `structure_preserving=False` discloses
to the user (see D003), not a caveat unique to this provider.

Response format, also confirmed by a real call (Cloudflare's docs do not
state this clearly — their schema viewer is JS-rendered and didn't come
through in documentation research): a successful call returns HTTP 200,
JSON body `{"result": {"image": "<base64-encoded JPEG>"}, "success": true}`.
A failed call returns a non-200 status with
`{"success": false, "errors": [{"message": ..., "code": ...}]}`.
"""
from __future__ import annotations

import base64

from ai.visualization.providers.base import RenderProvider, RenderUnavailableError

MODEL_NAME = "@cf/black-forest-labs/flux-1-schnell"
REQUEST_TIMEOUT_S = 60


class CloudflareImageProvider(RenderProvider):
    name = "cloudflare"
    structure_preserving = False  # verified fact, not a guess — see module docstring

    def __init__(self, account_id: str, api_token: str):
        if not account_id or not api_token:
            raise RenderUnavailableError(
                "Cloudflare provider requires both CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN."
            )
        self._account_id = account_id
        self._api_token = api_token

    def render(self, room_photo_bytes: bytes, prompt: str) -> bytes:
        # room_photo_bytes is intentionally unused — this provider cannot
        # accept an input image (see module docstring); the interface still
        # accepts it uniformly across providers so render_service.py doesn't
        # need per-provider branching.
        try:
            import requests
        except ImportError as exc:  # pragma: no cover — dependency always installed per requirements.txt
            raise RenderUnavailableError(f"requests library not available: {exc}") from exc

        url = f"https://api.cloudflare.com/client/v4/accounts/{self._account_id}/ai/run/{MODEL_NAME}"
        try:
            response = requests.post(
                url,
                headers={"Authorization": f"Bearer {self._api_token}"},
                json={"prompt": prompt},
                timeout=REQUEST_TIMEOUT_S,
            )
        except Exception as exc:  # noqa: BLE001 — network failure means "try the next provider"
            raise RenderUnavailableError(f"Cloudflare request failed: {exc}") from exc

        if response.status_code != 200:
            raise RenderUnavailableError(
                f"Cloudflare returned HTTP {response.status_code}: {response.text[:200]}"
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise RenderUnavailableError(f"Cloudflare response was not valid JSON: {exc}") from exc

        if not payload.get("success") or "image" not in payload.get("result", {}):
            raise RenderUnavailableError(f"Cloudflare response missing image data: {payload}")

        return base64.b64decode(payload["result"]["image"])

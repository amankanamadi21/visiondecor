"""
Gemini image-editing provider (decisions D003/D023).

Implementation grounded directly in the installed google-genai==2.22.0 SDK
source (ai/visualization/providers/gemini.py's author inspected
`google.genai._transformers.t_part`/`t_content` rather than trusting a
summarized doc page — search results for this SDK were inconsistent about
method names and model naming across sources). Confirmed from source:
  - `contents=[prompt_text, pil_image]` — a list mixing a str and a
    PIL.Image.Image is accepted directly; t_part() converts the str to a
    text Part and the PIL Image to an inline_data Part.
  - Output image bytes come back as `part.inline_data.data` (bytes) with
    `part.inline_data.mime_type`.
  - `types.GenerateContentConfig(response_modalities=["IMAGE"])` is a real,
    current field (response_modalities: list[str]).

⚠ LIVE-TESTED 2026-09-07 against a real API key — see PLAN.md Batch ③ update. The SDK call shape, auth, and
response parsing are all CONFIRMED CORRECT (a text-model call on the same key/account succeeded, and the
image-model calls returned a well-formed structured error, not a client-side failure). `MODEL_NAME` was
updated from the deprecated `gemini-2.5-flash-image` to the current `gemini-3.1-flash-image`, confirmed via
`client.models.list()` against the live account. However, every image-generation model on this account
currently returns `RESOURCE_EXHAUSTED` with a free-tier limit of 0 — Google's free tier no longer appears to
include any image-generation quota (a policy change since D003 was researched). This provider will work
once billing is enabled on the account, or once quota is otherwise granted; until then it will always raise
RenderUnavailableError, which is the correct, honest behavior — see PLAN.md for the pending user decision on
how to proceed (enable billing / build the Cloudflare-HF fallback / accept floor-plan-only).
"""
from __future__ import annotations

import io

from PIL import Image

from ai.visualization.providers.base import RenderProvider, RenderUnavailableError

MODEL_NAME = "gemini-3.1-flash-image"


class GeminiImageProvider(RenderProvider):
    name = "gemini"
    structure_preserving = True  # genuine image editing — see PLAN.md D003

    def __init__(self, api_key: str):
        if not api_key:
            raise RenderUnavailableError("Gemini provider requires GEMINI_API_KEY to be set.")
        self._api_key = api_key

    def render(self, room_photo_bytes: bytes, prompt: str) -> bytes:
        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:  # pragma: no cover — dependency always installed per requirements.txt
            raise RenderUnavailableError(f"google-genai SDK not available: {exc}") from exc

        try:
            client = genai.Client(api_key=self._api_key)
            input_image = Image.open(io.BytesIO(room_photo_bytes))

            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=[prompt, input_image],
                config=types.GenerateContentConfig(response_modalities=["IMAGE"]),
            )

            for part in response.parts:
                if part.inline_data is not None:
                    return part.inline_data.data

            raise RenderUnavailableError("Gemini response contained no image part.")
        except RenderUnavailableError:
            raise
        except Exception as exc:  # noqa: BLE001 — any SDK/API failure means "try the next provider"
            raise RenderUnavailableError(f"Gemini render failed: {exc}") from exc

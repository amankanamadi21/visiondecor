"""
RenderProvider interface (decision D003). Each provider takes the original
room photo bytes plus a text edit instruction (built by the D023 layout
translator) and returns edited image bytes, or raises RenderUnavailableError
if it cannot currently serve the request (missing key, quota exceeded, API
error) — callers use this to fail over to the next provider in the chain,
never to silently substitute a different kind of result.

`structure_preserving` is a class-level fact about the provider, not a
runtime guess: True only for providers that perform genuine image editing
(the room's real geometry survives by construction), False for text-to-image
providers where the output is not guaranteed to reflect the real room at all
(see PLAN.md D003's disclosure requirement).
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class RenderUnavailableError(Exception):
    """Raised by a provider that cannot serve this request right now —
    e.g. no API key configured, rate limit hit, or a transient API error.
    Never raised for 'this room can't be rendered' — that's not a provider
    concept, every provider either produces an image or is unavailable."""


class RenderProvider(ABC):
    name: str
    structure_preserving: bool

    @abstractmethod
    def render(self, room_photo_bytes: bytes, prompt: str) -> bytes:
        """Returns the rendered image's bytes (JPEG/PNG). Raises
        RenderUnavailableError if this provider cannot serve the request."""
        raise NotImplementedError


def _raise_for_status_and_parse_json(provider_name: str, response) -> dict:
    if response.status_code != 200:
        raise RenderUnavailableError(f"{provider_name} returned HTTP {response.status_code}: {response.text[:200]}")
    try:
        return response.json()
    except ValueError as exc:
        raise RenderUnavailableError(f"{provider_name} response was not valid JSON: {exc}") from exc


def post_json_or_raise(provider_name: str, url: str, headers: dict, json: dict, timeout: int) -> dict:
    """Shared POST -> status-check -> JSON-parse shape used by every
    JSON-body HTTP provider (Cloudflare, Hugging Face, Hugging Face
    Kontext) — only the response payload's field layout differs between
    them, so that's all each provider still handles itself."""
    import requests

    try:
        response = requests.post(url, headers=headers, json=json, timeout=timeout)
    except Exception as exc:  # noqa: BLE001 — network failure means "try the next provider"
        raise RenderUnavailableError(f"{provider_name} request failed: {exc}") from exc

    return _raise_for_status_and_parse_json(provider_name, response)


def post_multipart_or_raise(provider_name: str, url: str, headers: dict, files: dict, data: dict, timeout: int) -> dict:
    """Same shape as post_json_or_raise, for a multipart/form-data POST
    (OpenAI's edits endpoint takes a file, not a JSON body)."""
    import requests

    try:
        response = requests.post(url, headers=headers, files=files, data=data, timeout=timeout)
    except Exception as exc:  # noqa: BLE001
        raise RenderUnavailableError(f"{provider_name} request failed: {exc}") from exc

    return _raise_for_status_and_parse_json(provider_name, response)

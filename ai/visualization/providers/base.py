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

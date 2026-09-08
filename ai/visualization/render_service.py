"""
Render orchestration (decision D003): tries each configured provider in
order, falling back to the next on RenderUnavailableError, with the cache
checked first (and populated after a successful render) so an identical
request never spends a provider's quota twice.

If every provider fails or none are configured (the default — no API key
set), this returns None. That is not an error condition for the caller: the
deterministic floor plan (ai/visualization/floorplan.py) is always available
regardless, and the UI must treat a photorealistic render as optional, an
enhancement on top of the floor plan, never a requirement for the design to
be considered complete (brief PART 15 — no feature should be a hard blocker
when a graceful degraded path exists).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from ai.visualization.cache import RenderCache, cache_key
from ai.visualization.providers.base import RenderProvider, RenderUnavailableError

logger = logging.getLogger("visiondecor.visualization")


@dataclass
class RenderResult:
    image_bytes: bytes
    provider_name: str
    structure_preserving: bool
    cache_hit: bool


def render_with_fallback(
    room_photo_bytes: bytes,
    prompt: str,
    providers: list[RenderProvider],
    cache: RenderCache,
) -> RenderResult | None:
    for provider in providers:
        key = cache_key(room_photo_bytes, prompt, provider.name)
        cached = cache.get(key)
        if cached is not None:
            return RenderResult(
                image_bytes=cached, provider_name=provider.name,
                structure_preserving=provider.structure_preserving, cache_hit=True,
            )

        try:
            image_bytes = provider.render(room_photo_bytes, prompt)
        except RenderUnavailableError as exc:
            logger.info("Provider %s unavailable, trying next: %s", provider.name, exc)
            continue

        cache.put(key, image_bytes)
        return RenderResult(
            image_bytes=image_bytes, provider_name=provider.name,
            structure_preserving=provider.structure_preserving, cache_hit=False,
        )

    return None


def build_default_providers(
    gemini_api_key: str | None,
    cloudflare_account_id: str | None = None,
    cloudflare_api_token: str | None = None,
) -> list[RenderProvider]:
    """Gemini first (genuine image editing, structure-preserving — see
    GeminiImageProvider), Cloudflare second (text-to-image only, verified
    NOT structure-preserving — see CloudflareImageProvider's docstring for
    exactly what was tested and why). HuggingFace remains undesigned beyond
    D003's original chain (not implemented) — the chain degrades to 'no
    photorealistic render, floor plan only' gracefully when nothing is
    configured or every configured provider fails."""
    providers: list[RenderProvider] = []
    if gemini_api_key:
        from ai.visualization.providers.gemini import GeminiImageProvider

        providers.append(GeminiImageProvider(gemini_api_key))
    if cloudflare_account_id and cloudflare_api_token:
        from ai.visualization.providers.cloudflare import CloudflareImageProvider

        providers.append(CloudflareImageProvider(cloudflare_account_id, cloudflare_api_token))
    return providers

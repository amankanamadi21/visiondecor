"""
Content-addressed render cache (decision D003). Keyed by a hash of
everything that actually determines the output (room photo bytes + prompt
+ provider name) — an identical request always hits the cache instead of
spending a free-tier quota slot or producing a different result on a
retry. This is also what keeps a demo safe from a provider's daily rate
limit: once a render exists for a given (photo, layout, style) combination,
it's free and instant every time after.
"""
from __future__ import annotations

import hashlib
import os


def cache_key(room_photo_bytes: bytes, prompt: str, provider_name: str) -> str:
    hasher = hashlib.sha256()
    hasher.update(room_photo_bytes)
    hasher.update(prompt.encode("utf-8"))
    hasher.update(provider_name.encode("utf-8"))
    return hasher.hexdigest()


class RenderCache:
    def __init__(self, cache_dir: str):
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)

    def _path(self, key: str) -> str:
        return os.path.join(self.cache_dir, f"{key}.jpg")

    def get(self, key: str) -> bytes | None:
        path = self._path(key)
        if os.path.exists(path):
            with open(path, "rb") as f:
                return f.read()
        return None

    def put(self, key: str, image_bytes: bytes) -> str:
        path = self._path(key)
        with open(path, "wb") as f:
            f.write(image_bytes)
        return path

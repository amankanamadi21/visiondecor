"""
Visualization tests (decisions D003/D023). The critical property: the
system must work correctly with NO Gemini key configured (the shipped
default) — the job still completes, recommendation and layout are still
produced, and the layout response honestly reports no visualization rather
than fabricating one or failing the whole design generation.
"""
from __future__ import annotations

import time

from ai.visualization.cache import RenderCache, cache_key
from ai.visualization.providers.base import RenderProvider, RenderUnavailableError
from ai.visualization.render_service import render_with_fallback


def _register_and_login(client, email="alice@example.com", password="hunter2222", name="Alice"):
    client.post("/api/auth/register", json={"email": email, "password": password, "name": name})


def _poll_job_to_terminal(client, job_id, timeout_s=15):
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        resp = client.get(f"/api/jobs/{job_id}")
        job = resp.json["job"]
        if job["status"] in ("done", "failed"):
            return job
        time.sleep(0.1)
    raise TimeoutError(f"job {job_id} did not reach a terminal state within {timeout_s}s")


def test_generate_succeeds_with_no_visualization_provider_configured(client, monkeypatch, csrf_headers):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    _register_and_login(client)
    session_resp = client.post("/api/sessions", json={"room_type": "bedroom"}, headers=csrf_headers())
    session_id = session_resp.json["session"]["id"]

    import io

    from PIL import Image

    with open(
        __import__("ai.room_analysis.sample_rooms", fromlist=["SAMPLES_DIR"]).SAMPLES_DIR
        + "/bedroom_small_scandinavian.jpg",
        "rb",
    ) as f:
        sample_bytes = f.read()
    data = {"image": (io.BytesIO(sample_bytes), "sample.jpg", "image/jpeg")}
    upload_resp = client.post(
        f"/api/sessions/{session_id}/image", data=data, content_type="multipart/form-data",
        headers=csrf_headers(),
    )
    _poll_job_to_terminal(client, upload_resp.json["job_id"])

    client.patch(
        f"/api/sessions/{session_id}",
        json={"preferred_style": "Scandinavian", "budget": 60000},
        headers=csrf_headers(),
    )
    gen_resp = client.post(f"/api/sessions/{session_id}/generate", headers=csrf_headers())
    job = _poll_job_to_terminal(client, gen_resp.json["job_id"])
    assert job["status"] == "done", job  # must NOT fail just because no render provider exists

    layout = client.get(f"/api/sessions/{session_id}/layout").json["layout"]
    assert layout["visualization"] is None  # honest — no fabricated image, no fake provider name


class _FakeProvider(RenderProvider):
    name = "fake"
    structure_preserving = True

    def __init__(self, image_bytes: bytes = b"fake-image-bytes", should_fail: bool = False):
        self._image_bytes = image_bytes
        self._should_fail = should_fail
        self.call_count = 0

    def render(self, room_photo_bytes: bytes, prompt: str) -> bytes:
        self.call_count += 1
        if self._should_fail:
            raise RenderUnavailableError("fake failure")
        return self._image_bytes


def test_render_with_fallback_uses_cache_on_second_call(tmp_path):
    provider = _FakeProvider()
    cache = RenderCache(str(tmp_path))

    result1 = render_with_fallback(b"photo-bytes", "a prompt", [provider], cache)
    result2 = render_with_fallback(b"photo-bytes", "a prompt", [provider], cache)

    assert result1.cache_hit is False
    assert result2.cache_hit is True
    assert result1.image_bytes == result2.image_bytes == b"fake-image-bytes"
    assert provider.call_count == 1  # second call must NOT hit the provider again


def test_render_with_fallback_tries_next_provider_on_failure(tmp_path):
    failing = _FakeProvider(should_fail=True)
    working = _FakeProvider(image_bytes=b"second-provider-image")
    cache = RenderCache(str(tmp_path))

    result = render_with_fallback(b"photo", "prompt", [failing, working], cache)

    assert result is not None
    assert result.provider_name == "fake"
    assert result.image_bytes == b"second-provider-image"


def test_render_with_fallback_returns_none_when_all_providers_fail(tmp_path):
    failing = _FakeProvider(should_fail=True)
    cache = RenderCache(str(tmp_path))

    result = render_with_fallback(b"photo", "prompt", [failing], cache)
    assert result is None


def test_cache_key_differs_by_prompt_and_provider():
    k1 = cache_key(b"photo", "prompt A", "gemini")
    k2 = cache_key(b"photo", "prompt B", "gemini")
    k3 = cache_key(b"photo", "prompt A", "cloudflare")
    assert len({k1, k2, k3}) == 3

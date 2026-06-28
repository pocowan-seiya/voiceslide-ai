"""
VoiceSlide AI - Slide Supabase Storage helpers (Sprint 2)

These tests pin the contract of `services.supabase_storage.upload_slides_bundle`
/ `download_slides_bundle` / `list_slide_objects`. The real HTTP is mocked out
via monkeypatching httpx.AsyncClient, so tests run offline and don't rely on
Supabase being configured.
"""

from __future__ import annotations

import asyncio
import json
import os
import pytest


def test_build_slides_prefix_format():
    """Prefix is `{uid}/{pid}/slides/` with a trailing slash.

    The trailing slash matters: Supabase's list API uses the prefix literally,
    so `u/p/slides` would also match `u/p/slides_archive/`."""
    from services.supabase_storage import build_slides_prefix
    p = build_slides_prefix("user-aaa", "project-bbb")
    assert p == "user-aaa/project-bbb/slides/"
    assert p.endswith("/"), "prefix must end with a slash"


def test_build_slides_prefix_sanitizes_ids():
    """Alphanumeric + - and _ only — defensive against weird UUIDs."""
    from services.supabase_storage import build_slides_prefix
    p = build_slides_prefix("user/aaa", "project bbb!")
    assert "/" not in p.split("/")[0]  # no slash in sanitized user
    assert p.count("/") == 3  # exactly 3: user/project/slides/


def test_upload_slides_bundle_skipped_when_unconfigured(tmp_path, monkeypatch):
    """Without SUPABASE creds, upload returns None without attempting HTTP."""
    from services import supabase_storage as ss
    monkeypatch.setattr(ss, "SUPABASE_URL", "")
    monkeypatch.setattr(ss, "SUPABASE_SERVICE_ROLE_KEY", "")

    slides_dir = tmp_path / "job_slides"
    slides_dir.mkdir()
    (slides_dir / "slide_001.png").write_bytes(b"\x89PNG\r\n\x1a\n")

    result = asyncio.run(ss.upload_slides_bundle(
        str(slides_dir), "user-1", "project-1"
    ))
    assert result is None


def test_upload_slides_bundle_skipped_when_dir_missing(tmp_path, monkeypatch):
    """Missing slides_dir returns None (defensive — never crashes)."""
    from services import supabase_storage as ss
    monkeypatch.setattr(ss, "SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setattr(ss, "SUPABASE_SERVICE_ROLE_KEY", "fake-key")

    result = asyncio.run(ss.upload_slides_bundle(
        str(tmp_path / "does_not_exist"), "user-1", "project-1"
    ))
    assert result is None


def test_upload_slides_bundle_skipped_without_ids(tmp_path, monkeypatch):
    from services import supabase_storage as ss
    monkeypatch.setattr(ss, "SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setattr(ss, "SUPABASE_SERVICE_ROLE_KEY", "fake-key")

    slides_dir = tmp_path / "job_slides"
    slides_dir.mkdir()
    (slides_dir / "slide_001.png").write_bytes(b"\x89PNG\r\n\x1a\n")

    # Empty user_id
    r1 = asyncio.run(ss.upload_slides_bundle(str(slides_dir), "", "project-1"))
    # Empty project_id
    r2 = asyncio.run(ss.upload_slides_bundle(str(slides_dir), "user-1", ""))
    assert r1 is None and r2 is None


class _FakeResp:
    def __init__(self, status_code: int, text: str = "", content: bytes = b"", payload=None):
        self.status_code = status_code
        self.text = text
        self.content = content
        self._payload = payload

    def json(self):
        return self._payload


class _FakeClient:
    """Mimics httpx.AsyncClient's context manager + post/get/request API.

    Records every request so tests can assert on them. Route-specific
    responses are configured via the `responses` kwarg: `{url_substring: fake_resp}`.
    """

    def __init__(self, responses: dict):
        self._responses = responses
        self.posted = []  # list of (url, content, headers)
        self.got = []     # list of url
        self.deleted = [] # list of url

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a, **kw):
        return False

    def _match(self, url: str):
        for frag, resp in self._responses.items():
            if frag in url:
                return resp
        # Default to 200 empty
        return _FakeResp(200, "{}", b"")

    async def post(self, url, content=None, json=None, headers=None, **kw):
        self.posted.append((url, content if content is not None else json, headers))
        return self._match(url)

    async def get(self, url, headers=None, **kw):
        self.got.append(url)
        return self._match(url)

    async def request(self, method, url, json=None, headers=None, **kw):
        if method == "DELETE":
            self.deleted.append(url)
        return self._match(url)

    async def delete(self, url, headers=None, **kw):
        self.deleted.append(url)
        return self._match(url)

    async def patch(self, *a, **kw):
        return _FakeResp(204)


def test_upload_slides_bundle_happy_path(tmp_path, monkeypatch):
    """Upload posts one PUT/POST per file and returns the storage prefix."""
    from services import supabase_storage as ss
    monkeypatch.setattr(ss, "SUPABASE_URL", "https://fake.supabase.co")
    monkeypatch.setattr(ss, "SUPABASE_SERVICE_ROLE_KEY", "fake-key")

    slides_dir = tmp_path / "job_slides"
    slides_dir.mkdir()
    (slides_dir / "slide_001.png").write_bytes(b"fakepng-1")
    (slides_dir / "slide_002.png").write_bytes(b"fakepng-2")
    (slides_dir / "slide_data.json").write_text(json.dumps({"slides": []}))

    fake_client = _FakeClient(responses={
        "/storage/v1/object/slides/": _FakeResp(201, '{"Key": "ok"}'),
    })
    monkeypatch.setattr(ss.httpx, "AsyncClient", lambda **kw: fake_client)

    result = asyncio.run(ss.upload_slides_bundle(
        str(slides_dir), "user-xxx", "proj-yyy"
    ))
    assert result == "user-xxx/proj-yyy/slides/"

    # 3 posts: 2 PNGs + 1 JSON
    assert len(fake_client.posted) == 3
    # Assert each filename is part of one of the URLs (order is not guaranteed
    # because we gather concurrently)
    posted_urls = [p[0] for p in fake_client.posted]
    for name in ("slide_001.png", "slide_002.png", "slide_data.json"):
        assert any(name in u for u in posted_urls), f"{name} was not uploaded"

    # Content-Type headers must match per file
    for url, content, headers in fake_client.posted:
        if url.endswith(".png"):
            assert headers["Content-Type"] == "image/png"
        elif url.endswith(".json"):
            assert headers["Content-Type"] == "application/json"
        assert headers["x-upsert"] == "true"


def test_upload_slides_bundle_partial_failure_still_returns_prefix(tmp_path, monkeypatch):
    """If one PNG fails but others succeed, the bundle still returns the prefix
    so the DB gets updated — at least some slides are recoverable."""
    from services import supabase_storage as ss
    monkeypatch.setattr(ss, "SUPABASE_URL", "https://fake.supabase.co")
    monkeypatch.setattr(ss, "SUPABASE_SERVICE_ROLE_KEY", "fake-key")

    slides_dir = tmp_path / "job_slides"
    slides_dir.mkdir()
    (slides_dir / "slide_001.png").write_bytes(b"ok")
    (slides_dir / "slide_002.png").write_bytes(b"bad")

    call_count = {"n": 0}

    class _Client(_FakeClient):
        async def post(self, url, content=None, json=None, headers=None, **kw):
            call_count["n"] += 1
            # Fail the second call (whichever file)
            status = 500 if call_count["n"] == 2 else 201
            resp = _FakeResp(status, "oops" if status == 500 else "{}")
            self.posted.append((url, content, headers))
            return resp

    monkeypatch.setattr(ss.httpx, "AsyncClient", lambda **kw: _Client(responses={}))

    result = asyncio.run(ss.upload_slides_bundle(
        str(slides_dir), "user-x", "proj-y"
    ))
    assert result == "user-x/proj-y/slides/"  # still returns prefix despite partial


def test_upload_slides_bundle_total_failure_returns_none(tmp_path, monkeypatch):
    """All uploads fail → None so caller can mark cache status=failed."""
    from services import supabase_storage as ss
    monkeypatch.setattr(ss, "SUPABASE_URL", "https://fake.supabase.co")
    monkeypatch.setattr(ss, "SUPABASE_SERVICE_ROLE_KEY", "fake-key")

    slides_dir = tmp_path / "job_slides"
    slides_dir.mkdir()
    (slides_dir / "slide_001.png").write_bytes(b"x")

    fake_client = _FakeClient(responses={
        "/storage/v1/object/slides/": _FakeResp(500, "server error"),
    })
    monkeypatch.setattr(ss.httpx, "AsyncClient", lambda **kw: fake_client)

    result = asyncio.run(ss.upload_slides_bundle(
        str(slides_dir), "user-x", "proj-y"
    ))
    assert result is None


def test_download_slides_bundle_happy_path(tmp_path, monkeypatch):
    """List returns N names → N downloads land on disk."""
    from services import supabase_storage as ss
    monkeypatch.setattr(ss, "SUPABASE_URL", "https://fake.supabase.co")
    monkeypatch.setattr(ss, "SUPABASE_SERVICE_ROLE_KEY", "fake-key")

    listed = [
        {"name": "slide_001.png"},
        {"name": "slide_002.png"},
        {"name": "slide_data.json"},
    ]

    class _Client(_FakeClient):
        async def post(self, url, content=None, json=None, headers=None, **kw):
            self.posted.append((url, content if content is not None else json, headers))
            # list endpoint is POST /storage/v1/object/list/{bucket}
            if "/object/list/" in url:
                return _FakeResp(200, payload=listed)
            return _FakeResp(200)

        async def get(self, url, headers=None, **kw):
            self.got.append(url)
            # Return fake file contents per basename
            basename = url.rsplit("/", 1)[-1]
            return _FakeResp(200, content=f"content-{basename}".encode())

    fake_client = _Client(responses={})
    monkeypatch.setattr(ss.httpx, "AsyncClient", lambda **kw: fake_client)

    dest = tmp_path / "restored"
    count = asyncio.run(ss.download_slides_bundle(
        "user-x/proj-y/slides/", str(dest)
    ))
    assert count == 3
    assert (dest / "slide_001.png").exists()
    assert (dest / "slide_002.png").exists()
    assert (dest / "slide_data.json").exists()
    assert (dest / "slide_001.png").read_bytes() == b"content-slide_001.png"


def test_download_slides_bundle_empty_when_prefix_unlisted(tmp_path, monkeypatch):
    """List returns 0 → download count is 0 (not an error)."""
    from services import supabase_storage as ss
    monkeypatch.setattr(ss, "SUPABASE_URL", "https://fake.supabase.co")
    monkeypatch.setattr(ss, "SUPABASE_SERVICE_ROLE_KEY", "fake-key")

    class _Client(_FakeClient):
        async def post(self, url, content=None, json=None, headers=None, **kw):
            return _FakeResp(200, payload=[])

    monkeypatch.setattr(ss.httpx, "AsyncClient", lambda **kw: _Client(responses={}))

    count = asyncio.run(ss.download_slides_bundle(
        "user-x/proj-y/slides/", str(tmp_path / "empty")
    ))
    assert count == 0


def test_download_slides_bundle_unconfigured_returns_zero(tmp_path, monkeypatch):
    from services import supabase_storage as ss
    monkeypatch.setattr(ss, "SUPABASE_URL", "")
    monkeypatch.setattr(ss, "SUPABASE_SERVICE_ROLE_KEY", "")
    count = asyncio.run(ss.download_slides_bundle("u/p/slides/", str(tmp_path)))
    assert count == 0

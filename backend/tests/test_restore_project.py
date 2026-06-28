"""
VoiceSlide AI - Restore project endpoint tests
Tests that the /api/restore-project endpoint correctly handles the step parameter.
"""


def test_restore_project_default_step(test_client):
    """Test that restore defaults to step=5 when no step is provided"""
    response = test_client.post(
        "/api/restore-project",
        json={
            "transcript": "Hello world",
            "polished_transcript": "Hello, world!",
            "outline": {"title": "Test", "slides": []},
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "job_id" in data
    assert data["status"] == "restored"

    # Check the job was created with step=5 (default)
    status_response = test_client.get(f"/api/status/{data['job_id']}")
    assert status_response.status_code == 200
    status_data = status_response.json()
    assert status_data["step"] == 5


def test_restore_project_with_step_6(test_client):
    """Test that restore uses the provided step value"""
    response = test_client.post(
        "/api/restore-project",
        json={
            "transcript": "Hello world",
            "polished_transcript": "Hello, world!",
            "outline": {"title": "Test", "slides": []},
            "step": 6,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "job_id" in data

    # Check the job was created with step=6
    status_response = test_client.get(f"/api/status/{data['job_id']}")
    assert status_response.status_code == 200
    status_data = status_response.json()
    assert status_data["step"] == 6


def test_restore_project_with_step_8(test_client):
    """Test that restore works with step=8"""
    response = test_client.post(
        "/api/restore-project",
        json={
            "transcript": "Hello world",
            "polished_transcript": "Hello, world!",
            "outline": {"title": "Test", "slides": []},
            "step": 8,
        },
    )
    assert response.status_code == 200
    data = response.json()

    status_response = test_client.get(f"/api/status/{data['job_id']}")
    status_data = status_response.json()
    assert status_data["step"] == 8


def test_restore_project_invalid_step_too_high(test_client):
    """Test that an out-of-range step (>10) falls back to default 5"""
    response = test_client.post(
        "/api/restore-project",
        json={
            "transcript": "Hello world",
            "step": 99,
        },
    )
    assert response.status_code == 200
    data = response.json()

    status_response = test_client.get(f"/api/status/{data['job_id']}")
    status_data = status_response.json()
    assert status_data["step"] == 5


def test_restore_project_invalid_step_too_low(test_client):
    """Test that an out-of-range step (<1) falls back to default 5"""
    response = test_client.post(
        "/api/restore-project",
        json={
            "transcript": "Hello world",
            "step": 0,
        },
    )
    assert response.status_code == 200
    data = response.json()

    status_response = test_client.get(f"/api/status/{data['job_id']}")
    status_data = status_response.json()
    assert status_data["step"] == 5


# ---------------------------------------------------------------------------
# Regression: "4 slides became 2 on restore"
#
# Root cause: the frontend used to HEAD-check each stored slide preview URL
# (which pointed at the OLD job_id on ephemeral Railway disk). Partial 404s
# caused some URLs to be filtered out, so 4 slides would show as 2.
#
# Fix: /api/restore-project now returns `slide_previews` — an authoritative
# list built from the NEW job_id's slide directory after copying. These tests
# ensure that list always matches the number of PNGs copied, never partial.
# ---------------------------------------------------------------------------


def _seed_slides_dir(old_job_id: str, count: int):
    """Create N fake slide PNGs under OUTPUT_DIR/{old_job_id}_slides/."""
    import os
    from config import OUTPUT_DIR
    slides_dir = os.path.join(OUTPUT_DIR, f"{old_job_id}_slides")
    os.makedirs(slides_dir, exist_ok=True)
    for i in range(1, count + 1):
        p = os.path.join(slides_dir, f"slide_{i:03d}.png")
        # Minimal valid 1x1 PNG — we only care about file presence+copy
        with open(p, "wb") as f:
            f.write(
                b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
                b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
                b"\x00\x00\x00\rIDATx\x9cc\xfc\xcf\xc0P\x0f\x00\x01\x05\x01\x02"
                b"\x5b\x03\xe6W\x00\x00\x00\x00IEND\xaeB`\x82"
            )
    return slides_dir


def _cleanup_slides_dir(job_id: str):
    import os, shutil
    from config import OUTPUT_DIR
    for suffix in ("_slides",):
        d = os.path.join(OUTPUT_DIR, f"{job_id}{suffix}")
        if os.path.isdir(d):
            shutil.rmtree(d, ignore_errors=True)


def test_restore_returns_all_slide_previews(test_client):
    """4 slides on disk → restore response must return 4 preview URLs.

    This is the exact regression: previously the frontend filtered by HEAD
    check against stored URLs and could end up with a partial list."""
    old_job_id = "00000000-0000-0000-0000-00000000aaaa"
    _seed_slides_dir(old_job_id, count=4)
    try:
        response = test_client.post(
            "/api/restore-project",
            json={
                "transcript": "Hello world",
                "outline": {"title": "Test", "slides": []},
                "polished_outline": {"title": "Test", "slides": []},
                "step": 6,
                "slide_previews": [
                    # The backend parses the old_job_id from the first URL.
                    # The PATH itself is not HEAD-checked by the backend.
                    f"https://example.com/outputs/{old_job_id}_slides/slide_001.png",
                ],
            },
        )
        assert response.status_code == 200
        data = response.json()
        new_job_id = data["job_id"]

        # 1) slides_recovered count must match what we seeded
        assert data["slides_recovered"] == 4, (
            f"Expected 4 slides recovered, got {data['slides_recovered']}"
        )

        # 2) slide_previews must be an array of length 4
        previews = data.get("slide_previews")
        assert isinstance(previews, list), "slide_previews must be a list"
        assert len(previews) == 4, (
            f"Expected 4 preview URLs, got {len(previews)}: {previews}"
        )

        # 3) Each URL must point at the NEW job_id's dir (not the old one)
        for p in previews:
            assert new_job_id in p, f"Preview URL should contain new job_id: {p}"
            assert old_job_id not in p, f"Preview URL must not leak old job_id: {p}"
            assert p.startswith(f"/outputs/{new_job_id}_slides/slide_"), p

        # 4) Ordering is stable (slide_001, slide_002, ...)
        filenames = [p.rsplit("/", 1)[-1] for p in previews]
        assert filenames == sorted(filenames), (
            f"slide_previews should be ordered by filename, got {filenames}"
        )
    finally:
        _cleanup_slides_dir(old_job_id)
        # new_job_id cleanup is best-effort — it's uuid4, so safe to ignore


def test_restore_returns_empty_previews_when_no_old_slides(test_client):
    """If the old job_id's dir doesn't exist on this container, slide_previews
    must be an empty array (not missing, not None) so the frontend can
    reliably test its length to decide whether to show the regen banner."""
    response = test_client.post(
        "/api/restore-project",
        json={
            "transcript": "Hello world",
            "outline": {"title": "Test", "slides": []},
            "step": 6,
            "slide_previews": [
                # Non-existent old job id
                "https://example.com/outputs/deadbeef-0000-0000-0000-000000000000_slides/slide_001.png",
            ],
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["slides_recovered"] == 0
    assert data["slide_previews"] == []


def test_restore_without_slide_previews_returns_empty_list(test_client):
    """When the caller doesn't pass slide_previews at all, backend should still
    return `slide_previews: []` — never missing or None — so the frontend
    doesn't crash trying to read `.length` on undefined."""
    response = test_client.post(
        "/api/restore-project",
        json={
            "transcript": "Hello world",
            "step": 5,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "slide_previews" in data
    assert data["slide_previews"] == []


# ---------------------------------------------------------------------------
# Regression: "video silently disappears after navigating away from step 10"
#
# Root cause: _cache_video_to_storage runs as fire-and-forget after
# /api/generate-video returns. If the user navigates to the dashboard before
# the upload PATCHes projects.video_storage_path, the DB keeps:
#   status=completed, video_url=/video/<old>, video_storage_path=NULL
# On restore, the old video_url is stale (pointing at a recycled job_id), so
# we must NOT treat it as playable. These tests pin the contract:
#   step=10 AND video_url_hint set AND video_storage_path missing
#     → video_expired=true
# The frontend then rewinds step and shows the "動画が保存されていませんでした" banner.
# ---------------------------------------------------------------------------


def test_restore_step_10_without_storage_path_marks_expired(test_client):
    """Cache-write race: project was at step 10 (video_url_hint present) but
    video_storage_path never landed in the DB. Must be flagged as expired."""
    response = test_client.post(
        "/api/restore-project",
        json={
            "transcript": "Hello world",
            "outline": {"title": "Test", "slides": []},
            "polished_outline": {"title": "Test", "slides": []},
            "step": 10,
            "video_url_hint": "/video/00000000-0000-0000-0000-00000000bbbb?t=123",
            # Intentionally NO video_storage_path — this is the bug trigger.
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["video_recovered"] is False
    assert data["video_expired"] is True
    assert data["video_url"] is None


def test_restore_step_10_with_storage_path_but_download_fails(test_client):
    """If storage_path is set but the download fails (Supabase unconfigured
    in tests), existing behavior must still flag expired — not regressed."""
    response = test_client.post(
        "/api/restore-project",
        json={
            "transcript": "Hello world",
            "outline": {"title": "Test", "slides": []},
            "step": 10,
            "video_storage_path": "user/project/video.mp4",
            "video_cached_at": "2099-01-01T00:00:00+00:00",  # future = age_ok=True
            "video_url_hint": "/video/some-old-id",
        },
    )
    assert response.status_code == 200
    data = response.json()
    # In the test env Supabase is not configured, so download returns False.
    # Either path (download path OR hint-based path) must land on expired=true.
    assert data["video_recovered"] is False
    assert data["video_expired"] is True


def test_restore_step_9_without_storage_path_does_not_mark_expired(test_client):
    """Negative control: at step 9, the user never reached the video screen,
    so the hint-based 'expired' branch MUST NOT fire — otherwise we'd show
    a bogus banner on projects that legitimately have no video yet."""
    response = test_client.post(
        "/api/restore-project",
        json={
            "transcript": "Hello world",
            "outline": {"title": "Test", "slides": []},
            "step": 9,
            # No video_url_hint, no video_storage_path — fresh pre-video state.
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["video_recovered"] is False
    assert data["video_expired"] is False


def test_restore_step_10_without_hint_does_not_mark_expired(test_client):
    """Edge case: older clients might not send video_url_hint. In that case
    we can't distinguish "user reached step 10" from "restore was called
    with step=10 for some other reason" — prefer false negative (no banner)
    over false positive (banner on a project that has no video). The
    frontend's defensive branch at adjustedStep===10 && !video_storage_path
    still handles the UI rewind independently."""
    response = test_client.post(
        "/api/restore-project",
        json={
            "transcript": "Hello world",
            "outline": {"title": "Test", "slides": []},
            "step": 10,
            # No video_url_hint provided (legacy client)
        },
    )
    assert response.status_code == 200
    data = response.json()
    # Backend cannot prove a video existed, so doesn't flag expired.
    # (Frontend takes over with its defensive rewind logic in this case.)
    assert data["video_expired"] is False


# ---------------------------------------------------------------------------
# Regression: "slides disappear after Railway redeploys" (Sprint 2)
#
# Root cause: slide PNGs only lived on the Railway container's ephemeral disk,
# so any redeploy or container reshuffle wiped them. Fix: persist the bundle
# to Supabase Storage and download on restore when the local old_job_id dir
# is empty. These tests pin:
#   1. When `slides_storage_prefix` is provided AND local recovery finds 0,
#      the backend must call download_slides_bundle and rebuild the slide dir.
#   2. When download returns 0 (unconfigured / prefix empty), the restore
#      response still succeeds with empty previews — the frontend shows the
#      regen banner as usual.
# ---------------------------------------------------------------------------


def test_restore_downloads_slides_from_storage_when_local_missing(test_client, monkeypatch):
    """Local old_job_id has no slides, but the project has slides_storage_prefix.
    Backend must call download_slides_bundle and the restore response must
    reflect the recovered slides."""
    import os
    from config import OUTPUT_DIR

    async def fake_download(prefix, dest_dir):
        # Simulate: supabase delivers 2 PNGs and a slide_data.json
        os.makedirs(dest_dir, exist_ok=True)
        with open(os.path.join(dest_dir, "slide_001.png"), "wb") as f:
            f.write(b"\x89PNG")
        with open(os.path.join(dest_dir, "slide_002.png"), "wb") as f:
            f.write(b"\x89PNG")
        with open(os.path.join(dest_dir, "slide_data.json"), "w") as f:
            f.write('{"slides":[]}')
        return 3

    from services import supabase_storage as ss
    monkeypatch.setattr(ss, "download_slides_bundle", fake_download)

    response = test_client.post(
        "/api/restore-project",
        json={
            "transcript": "Hello world",
            "outline": {"title": "Test", "slides": []},
            "polished_outline": {"title": "Test", "slides": []},
            "step": 6,
            # No slide_previews → backend can't parse old_job_id, so the local
            # recovery path finds nothing (recovered_slides=0)
            "slides_storage_prefix": "user-a/project-b/slides/",
        },
    )
    assert response.status_code == 200
    data = response.json()
    new_job_id = data["job_id"]

    # Backend should have downloaded 2 PNGs → 2 previews returned (json is not a preview)
    assert data["slides_recovered"] == 2, (
        f"Expected 2 slides recovered from storage, got {data['slides_recovered']}"
    )
    assert len(data["slide_previews"]) == 2
    for p in data["slide_previews"]:
        assert new_job_id in p
        assert p.startswith(f"/outputs/{new_job_id}_slides/slide_")

    # Cleanup
    import shutil
    d = os.path.join(OUTPUT_DIR, f"{new_job_id}_slides")
    if os.path.isdir(d):
        shutil.rmtree(d, ignore_errors=True)


def test_restore_falls_back_gracefully_when_storage_download_returns_zero(test_client, monkeypatch):
    """If Storage download finds nothing (e.g. not configured in test env,
    or prefix is empty), restore must still succeed — frontend will show
    regen banner, but server must not 500."""
    async def zero_download(prefix, dest_dir):
        return 0

    from services import supabase_storage as ss
    monkeypatch.setattr(ss, "download_slides_bundle", zero_download)

    response = test_client.post(
        "/api/restore-project",
        json={
            "transcript": "Hello world",
            "outline": {"title": "Test", "slides": []},
            "step": 6,
            "slides_storage_prefix": "user-x/project-y/slides/",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["slides_recovered"] == 0
    assert data["slide_previews"] == []


def test_restore_prefers_local_old_job_id_over_storage(test_client, monkeypatch):
    """When the local old_job_id dir exists on this container (same
    container, container not yet redeployed), backend should NOT call
    download_slides_bundle — local is faster and authoritative."""
    import os
    from config import OUTPUT_DIR

    storage_called = {"n": 0}
    async def tracking_download(prefix, dest_dir):
        storage_called["n"] += 1
        return 0

    from services import supabase_storage as ss
    monkeypatch.setattr(ss, "download_slides_bundle", tracking_download)

    # Seed local slides for an old job id
    old_job_id = "00000000-0000-0000-0000-00000000cccc"
    slides_dir = os.path.join(OUTPUT_DIR, f"{old_job_id}_slides")
    os.makedirs(slides_dir, exist_ok=True)
    for i in (1, 2):
        with open(os.path.join(slides_dir, f"slide_{i:03d}.png"), "wb") as f:
            f.write(b"\x89PNG")

    try:
        response = test_client.post(
            "/api/restore-project",
            json={
                "transcript": "Hello world",
                "outline": {"title": "Test", "slides": []},
                "polished_outline": {"title": "Test", "slides": []},
                "step": 6,
                "slide_previews": [f"https://example.com/outputs/{old_job_id}_slides/slide_001.png"],
                "slides_storage_prefix": "user-a/project-b/slides/",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["slides_recovered"] == 2  # from local
        # Storage should NOT have been called when local path succeeded
        assert storage_called["n"] == 0
    finally:
        import shutil
        shutil.rmtree(slides_dir, ignore_errors=True)
        d = os.path.join(OUTPUT_DIR, f"{data['job_id']}_slides")
        if os.path.isdir(d):
            shutil.rmtree(d, ignore_errors=True)

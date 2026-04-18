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

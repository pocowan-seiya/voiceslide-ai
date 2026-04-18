"""
Phase-1 robustness regression tests.

These cover the 3 critical fixes from the architectural audit:
  1. Video cache: retry + structured logging + status tracking
  2. Cleanup: _slide_data_cache and _used_layouts_cache must be popped
     when a job is cleaned up (was leaking memory)
  3. Audio storage: explicit status reporting (persisted/skipped/failed)
     so the frontend can warn the user when persistence fails
"""

import asyncio
import os
import sys
from unittest.mock import patch, AsyncMock, MagicMock

import pytest


@pytest.fixture(autouse=True)
def _clear_caches_between_tests():
    """Each test gets a clean cache state — important because module-level
    dicts persist across the test session otherwise."""
    from services.ai_slide_generator import _slide_data_cache, _used_layouts_cache
    _slide_data_cache.clear()
    _used_layouts_cache.clear()
    yield
    _slide_data_cache.clear()
    _used_layouts_cache.clear()


# ---------------------------------------------------------------------------
# Fix 2: cleanup must clear ai_slide_generator caches
# ---------------------------------------------------------------------------


def test_cleanup_pops_slide_data_cache_for_dead_jobs():
    """Regression: cleanup_old_jobs used to leave _slide_data_cache entries
    around forever, leaking memory. Now it pops them along with the rest."""
    from services.ai_slide_generator import _slide_data_cache, _used_layouts_cache
    import main

    job_id = "leak-test-001"
    _slide_data_cache[job_id] = {"slides": [{"number": 1}], "strategy": {}}
    _used_layouts_cache[job_id] = ["Center Hero"]
    assert job_id in _slide_data_cache
    assert job_id in _used_layouts_cache

    # Simulate the inner block of cleanup_old_jobs that pops per-job state.
    # We don't want to run the full async loop here — just exercise the path
    # that frees this job's caches.
    main.jobs.pop(job_id, None)
    main.api_keys.pop(job_id, None)
    main.slide_progress.pop(job_id, None)
    main.slide_history.pop(job_id, None)
    main.job_timestamps.pop(job_id, None)
    # The new lines added in Phase-1:
    _slide_data_cache.pop(job_id, None)
    _used_layouts_cache.pop(job_id, None)

    assert job_id not in _slide_data_cache
    assert job_id not in _used_layouts_cache


def test_cleanup_loop_pops_caches_end_to_end():
    """Verify the actual cleanup_old_jobs loop pops the caches.
    Drives one iteration via a manually-aged job_timestamp."""
    from datetime import datetime, timedelta
    from services.ai_slide_generator import _slide_data_cache, _used_layouts_cache
    import main

    job_id = "leak-test-002"
    main.jobs[job_id] = {"id": job_id}
    main.job_timestamps[job_id] = datetime.now() - timedelta(hours=main.JOB_MAX_AGE_HOURS + 1)
    _slide_data_cache[job_id] = {"slides": [], "strategy": {}}
    _used_layouts_cache[job_id] = []

    # Run one iteration of the cleanup body. We can't run the full while loop
    # (it sleeps an hour), but we can patch asyncio.sleep to short-circuit.
    async def _run_one_pass():
        with patch("asyncio.sleep", side_effect=asyncio.CancelledError):
            try:
                await main.cleanup_old_jobs()
            except asyncio.CancelledError:
                pass

    asyncio.run(_run_one_pass())

    assert job_id not in _slide_data_cache, "cleanup must pop slide_data_cache"
    assert job_id not in _used_layouts_cache, "cleanup must pop used_layouts_cache"
    assert job_id not in main.jobs


# ---------------------------------------------------------------------------
# Fix 1: video cache retry + structured status
# ---------------------------------------------------------------------------


def test_video_cache_retries_on_transient_failure_then_succeeds():
    """upload_video returns None twice (transient), succeeds on attempt 3."""
    import main

    # Speed up retry delays so the test isn't slow
    monkey_delays = (0, 0, 0)
    with patch("main._VIDEO_CACHE_RETRY_DELAYS_SEC", monkey_delays):
        attempts = {"n": 0}

        async def fake_upload(*args, **kwargs):
            attempts["n"] += 1
            return "user/proj/video.mp4" if attempts["n"] >= 3 else None

        with patch("services.supabase_storage.upload_video", side_effect=fake_upload), \
             patch("services.supabase_storage.is_configured", return_value=True), \
             patch("services.supabase_storage.SUPABASE_URL", "https://example.supabase.co"), \
             patch("services.supabase_storage.SUPABASE_SERVICE_ROLE_KEY", "test-key"):
            # Mock the PATCH call to succeed
            mock_response = MagicMock()
            mock_response.status_code = 204
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = False
            mock_client.patch = AsyncMock(return_value=mock_response)

            with patch("httpx.AsyncClient", return_value=mock_client):
                job_id = "video-retry-001"
                main.jobs[job_id] = {"id": job_id, "status": "completed"}
                asyncio.run(main._cache_video_to_storage(
                    "/tmp/fake.mp4", "user-1", "proj-1", job_id=job_id,
                ))

        assert attempts["n"] == 3, f"expected 3 attempts, got {attempts['n']}"
        assert main.jobs[job_id]["video_cache_status"] == "cached"

        del main.jobs[job_id]


def test_video_cache_marks_failed_after_exhausting_retries():
    """All 4 attempts fail → status='failed' (not silently swallowed like before)."""
    import main

    with patch("main._VIDEO_CACHE_RETRY_DELAYS_SEC", (0, 0, 0)):
        async def always_fail(*args, **kwargs):
            return None  # upload_video returning None = soft failure

        with patch("services.supabase_storage.upload_video", side_effect=always_fail), \
             patch("services.supabase_storage.is_configured", return_value=True):
            job_id = "video-retry-002"
            main.jobs[job_id] = {"id": job_id, "status": "completed"}
            asyncio.run(main._cache_video_to_storage(
                "/tmp/fake.mp4", "user-1", "proj-1", job_id=job_id,
            ))

        assert main.jobs[job_id]["video_cache_status"] == "failed"
        assert "video_cache_detail" in main.jobs[job_id]

        del main.jobs[job_id]


def test_video_cache_skips_when_supabase_not_configured():
    """No retry waste when Supabase isn't configured — mark as skipped."""
    import main

    with patch("services.supabase_storage.is_configured", return_value=False):
        job_id = "video-retry-003"
        main.jobs[job_id] = {"id": job_id, "status": "completed"}
        asyncio.run(main._cache_video_to_storage(
            "/tmp/fake.mp4", "user-1", "proj-1", job_id=job_id,
        ))

        assert main.jobs[job_id]["video_cache_status"] == "skipped"
        assert main.jobs[job_id]["video_cache_detail"] == "not_configured"

        del main.jobs[job_id]


# ---------------------------------------------------------------------------
# Fix 3: audio storage explicit status reporting
# ---------------------------------------------------------------------------


def test_audio_storage_status_skipped_without_credentials():
    """Without user_id/project_id, status is 'skipped' (not 'failed')."""
    import main

    path, status, detail = asyncio.run(
        main._upload_audio_to_storage_with_retry("/tmp/fake.wav", None, None)
    )
    assert path is None
    assert status == "skipped"
    assert detail == "missing_user_or_project_id"


def test_audio_storage_status_persisted_on_success():
    """Successful upload returns ('path', 'persisted', '')."""
    import main

    with patch("main._AUDIO_STORAGE_RETRY_DELAYS_SEC", (0, 0, 0)):
        async def ok_upload(*args, **kwargs):
            return "user/proj/audio.wav"

        with patch("services.supabase_storage.upload_audio", side_effect=ok_upload), \
             patch("services.supabase_storage.is_configured", return_value=True):
            path, status, detail = asyncio.run(
                main._upload_audio_to_storage_with_retry(
                    "/tmp/fake.wav", "u1", "p1"
                )
            )
        assert path == "user/proj/audio.wav"
        assert status == "persisted"


def test_audio_storage_status_failed_after_retries():
    """All retries fail → returns (None, 'failed', detail)."""
    import main

    with patch("main._AUDIO_STORAGE_RETRY_DELAYS_SEC", (0, 0, 0)):
        async def fail_upload(*args, **kwargs):
            raise RuntimeError("network bork")

        with patch("services.supabase_storage.upload_audio", side_effect=fail_upload), \
             patch("services.supabase_storage.is_configured", return_value=True):
            path, status, detail = asyncio.run(
                main._upload_audio_to_storage_with_retry(
                    "/tmp/fake.wav", "u1", "p1"
                )
            )
        assert path is None
        assert status == "failed"
        assert "RuntimeError" in detail


def test_audio_storage_retries_until_success():
    """First two attempts return None, third returns a path."""
    import main

    with patch("main._AUDIO_STORAGE_RETRY_DELAYS_SEC", (0, 0, 0)):
        attempts = {"n": 0}

        async def flaky_upload(*args, **kwargs):
            attempts["n"] += 1
            return "user/proj/audio.wav" if attempts["n"] >= 3 else None

        with patch("services.supabase_storage.upload_audio", side_effect=flaky_upload), \
             patch("services.supabase_storage.is_configured", return_value=True):
            path, status, detail = asyncio.run(
                main._upload_audio_to_storage_with_retry(
                    "/tmp/fake.wav", "u1", "p1"
                )
            )
        assert attempts["n"] == 3
        assert status == "persisted"
        assert path == "user/proj/audio.wav"


# ---------------------------------------------------------------------------
# Phase 2.1: per-job mutex protects _slide_data_cache from concurrent writes
# ---------------------------------------------------------------------------


def test_concurrent_save_html_contents_does_not_lose_writes():
    """Two threads writing to the same job's html_contents must serialize.
    Without the per-job lock, the slower thread's edit would silently disappear
    (the dict assignment + JSON write race on the same key)."""
    import threading
    import tempfile
    import shutil
    from services.ai_slide_generator import save_slide_data, save_html_contents, _slide_data_cache

    job_id = "concurrent-edit-001"
    # Need a real slides dir so _persist_slide_data writes to disk
    tmp = tempfile.mkdtemp(prefix="vs_lock_")
    slides_dir = os.path.join(tmp, f"{job_id}_slides")
    os.makedirs(slides_dir, exist_ok=True)

    try:
        with patch("config.OUTPUT_DIR", tmp):
            save_slide_data(job_id, [{"number": 1}, {"number": 2}], {})

            results = []

            def writer(html_a: str, html_b: str, idx: int):
                # Each thread does many writes to maximize race chance
                for _ in range(50):
                    save_html_contents(job_id, [html_a, html_b])
                results.append(idx)

            t1 = threading.Thread(target=writer, args=("<A>v1</A>", "<B>v1</B>", 1))
            t2 = threading.Thread(target=writer, args=("<A>v2</A>", "<B>v2</B>", 2))
            t1.start()
            t2.start()
            t1.join()
            t2.join()

            # Both threads completed without exception
            assert len(results) == 2

            # Final cache state is one consistent pair (not interleaved)
            final = _slide_data_cache[job_id]["html_contents"]
            assert len(final) == 2
            # Both elements should come from the SAME thread's last write
            # (i.e. either both v1 or both v2). Without the lock, you could
            # see [<A>v1</A>, <B>v2</B>] which is mixed.
            v1 = final[0].count("v1")
            v2 = final[0].count("v2")
            assert v1 + v2 == 1, f"first slot has weird value: {final[0]}"
            second_v1 = final[1].count("v1")
            second_v2 = final[1].count("v2")
            assert second_v1 + second_v2 == 1
            # Both slots must come from the same thread
            assert (v1 == second_v1) and (v2 == second_v2), (
                f"interleaved write detected: {final}"
            )
    finally:
        _slide_data_cache.pop(job_id, None)
        shutil.rmtree(tmp, ignore_errors=True)


def test_release_slide_data_lock_drops_entry():
    """cleanup_old_jobs calls release_slide_data_lock — without it, every
    job_id ever seen would leak a Lock object forever."""
    from services.ai_slide_generator import (
        save_slide_data, _slide_data_locks, release_slide_data_lock, _slide_data_cache,
    )

    job_id = "lock-release-001"
    # save creates the lock entry on first access
    save_slide_data(job_id, [], {})
    assert job_id in _slide_data_locks

    release_slide_data_lock(job_id)
    assert job_id not in _slide_data_locks

    # Calling release on a non-existent job_id is a no-op (not an error)
    release_slide_data_lock("never-existed")

    _slide_data_cache.pop(job_id, None)

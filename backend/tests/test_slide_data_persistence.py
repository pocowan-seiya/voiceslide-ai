"""
Regression tests for slide_data disk persistence.

Bug: `_slide_data_cache` (used by the feedback/edit endpoint) was purely
in-memory, so restoring a project with a new job_id always returned
`Slide data not found for job {job_id}` on slide edit. Fixed by persisting
to `{OUTPUT_DIR}/{job_id}_slides/slide_data.json` and rehydrating on restore.

These tests exercise the save → disk → load round-trip directly so a future
change to the JSON shape or path doesn't silently re-break slide editing.
"""

import json
import os
import shutil
import tempfile

import pytest


@pytest.fixture
def isolated_output_dir(monkeypatch):
    """Point config.OUTPUT_DIR at a fresh temp dir for this test."""
    tmp = tempfile.mkdtemp(prefix="voiceslide_test_")
    monkeypatch.setattr("config.OUTPUT_DIR", tmp)
    # ai_slide_generator imports OUTPUT_DIR lazily inside functions, so the
    # monkeypatch on config is picked up on next call.
    yield tmp
    shutil.rmtree(tmp, ignore_errors=True)


def _slides_dir(output_dir: str, job_id: str) -> str:
    d = os.path.join(output_dir, f"{job_id}_slides")
    os.makedirs(d, exist_ok=True)
    return d


def test_save_slide_data_persists_to_disk(isolated_output_dir):
    from services.ai_slide_generator import save_slide_data, _slide_data_cache

    job_id = "test-job-persist-001"
    _slides_dir(isolated_output_dir, job_id)
    slides = [{"number": 1, "content": "intro"}, {"number": 2, "content": "outro"}]
    strategy = {"palette": "cosmic"}

    try:
        save_slide_data(job_id, slides, strategy)

        expected_path = os.path.join(isolated_output_dir, f"{job_id}_slides", "slide_data.json")
        assert os.path.exists(expected_path), "slide_data.json must be written next to slides"
        with open(expected_path, "r", encoding="utf-8") as f:
            written = json.load(f)
        assert written["slides"] == slides
        assert written["strategy"] == strategy
    finally:
        _slide_data_cache.pop(job_id, None)


def test_load_slide_data_from_disk_rehydrates_cache(isolated_output_dir):
    """The critical restore path: new job_id, same JSON on disk, cache gets filled."""
    from services.ai_slide_generator import load_slide_data_from_disk, _slide_data_cache

    new_job_id = "restored-job-002"
    slides_dir = _slides_dir(isolated_output_dir, new_job_id)
    payload = {
        "slides": [{"number": 1, "content": "one"}],
        "strategy": {"mode": "hybrid"},
        "html_contents": ["<html>one</html>"],
    }
    with open(os.path.join(slides_dir, "slide_data.json"), "w", encoding="utf-8") as f:
        json.dump(payload, f)

    _slide_data_cache.pop(new_job_id, None)
    try:
        ok = load_slide_data_from_disk(new_job_id)
        assert ok is True
        assert _slide_data_cache[new_job_id] == payload
    finally:
        _slide_data_cache.pop(new_job_id, None)


def test_load_returns_false_when_no_file(isolated_output_dir):
    from services.ai_slide_generator import load_slide_data_from_disk

    # Dir doesn't exist — graceful False, no crash
    assert load_slide_data_from_disk("nonexistent-job-003") is False


def test_load_rejects_malformed_json(isolated_output_dir):
    """Guard against a half-written or corrupt JSON silently clobbering the cache."""
    from services.ai_slide_generator import load_slide_data_from_disk, _slide_data_cache

    job_id = "malformed-job-004"
    slides_dir = _slides_dir(isolated_output_dir, job_id)
    with open(os.path.join(slides_dir, "slide_data.json"), "w", encoding="utf-8") as f:
        f.write("{not valid json")

    _slide_data_cache.pop(job_id, None)
    assert load_slide_data_from_disk(job_id) is False
    assert job_id not in _slide_data_cache


def test_save_html_contents_also_persists(isolated_output_dir):
    """Editing a slide updates HTML — the JSON on disk must reflect that too,
    otherwise a redeploy mid-edit loses the user's change."""
    from services.ai_slide_generator import (
        save_slide_data, save_html_contents, _slide_data_cache,
    )

    job_id = "html-sync-job-005"
    _slides_dir(isolated_output_dir, job_id)
    try:
        save_slide_data(job_id, [{"number": 1}, {"number": 2}], {})
        save_html_contents(job_id, ["<html>one</html>", "<html>two</html>"])

        path = os.path.join(isolated_output_dir, f"{job_id}_slides", "slide_data.json")
        with open(path, "r", encoding="utf-8") as f:
            on_disk = json.load(f)
        assert on_disk["html_contents"] == ["<html>one</html>", "<html>two</html>"]
    finally:
        _slide_data_cache.pop(job_id, None)


def test_strategy_with_non_serializable_values_still_persists(isolated_output_dir):
    """Strategy can pick up odd values over time. We fall back to default=str
    so one rogue value doesn't wipe the entire JSON — otherwise the next
    restore silently fails with no signal to the user."""
    from services.ai_slide_generator import save_slide_data, _slide_data_cache

    job_id = "non-serializable-job-006"
    _slides_dir(isolated_output_dir, job_id)
    try:
        class Custom:
            def __repr__(self):
                return "custom-obj"

        save_slide_data(job_id, [{"number": 1}], {"exotic": Custom()})

        path = os.path.join(isolated_output_dir, f"{job_id}_slides", "slide_data.json")
        assert os.path.exists(path), "JSON must be written despite non-serializable strategy value"
        with open(path, "r", encoding="utf-8") as f:
            on_disk = json.load(f)
        assert on_disk["strategy"]["exotic"] == "custom-obj"
    finally:
        _slide_data_cache.pop(job_id, None)


def test_restore_flow_end_to_end(isolated_output_dir):
    """Full flow: save under OLD job → copy JSON to NEW job dir →
    load_slide_data_from_disk → cache keyed by NEW job_id.
    This is exactly what /api/restore-project does."""
    from services.ai_slide_generator import (
        save_slide_data, save_html_contents, load_slide_data_from_disk,
        get_slide_data, _slide_data_cache,
    )

    old_job = "old-job-007"
    new_job = "new-job-008"
    _slides_dir(isolated_output_dir, old_job)
    _slides_dir(isolated_output_dir, new_job)

    try:
        save_slide_data(old_job, [{"number": 1, "content": "a"}], {"mode": "full-ai"})
        save_html_contents(old_job, ["<html>a</html>"])

        old_json = os.path.join(isolated_output_dir, f"{old_job}_slides", "slide_data.json")
        new_json = os.path.join(isolated_output_dir, f"{new_job}_slides", "slide_data.json")
        shutil.copy2(old_json, new_json)

        # Simulate a fresh container: wipe in-memory cache entirely
        _slide_data_cache.pop(old_job, None)
        _slide_data_cache.pop(new_job, None)

        assert load_slide_data_from_disk(new_job) is True
        recovered = get_slide_data(new_job)
        assert recovered is not None, "cache must be populated after restore"
        assert recovered["slides"][0]["content"] == "a"
        assert recovered["html_contents"] == ["<html>a</html>"]
    finally:
        _slide_data_cache.pop(old_job, None)
        _slide_data_cache.pop(new_job, None)

"""
Regression tests for slide direct editing bugs reported by Tanaka-san.

Bug 1: Selecting slide N and entering direct edit mode showed HTML for a
        different slide (index mismatch). Root cause: html_contents was not
        updated after fix_body_dimensions was applied during rendering, so
        the stored HTML didn't match what was actually rendered.

Bug 2: Only highlighted (leaf) text elements were editable; other text
        elements couldn't be clicked into edit mode. Root cause: the old
        isLeafText() function only matched elements with no child elements,
        missing elements that mix direct text nodes with inline children.

Both fixed in commit 42d77aa.
"""

import pytest
from services.ai_slide_generator import (
    fix_body_dimensions,
    save_slide_data,
    save_html_contents,
    load_html_contents,
    get_html_content,
    update_html_content,
    _slide_data_cache,
)


# ---------------------------------------------------------------------------
# Bug 1 regression: html_contents must reflect post-fix_body_dimensions HTML
# ---------------------------------------------------------------------------

class TestSlideIndexHtmlConsistency:
    """Ensure the HTML stored in html_contents matches the rendered version
    after fix_body_dimensions is applied."""

    def setup_method(self):
        """Clean up cache before each test."""
        _slide_data_cache.pop("regression-test", None)

    def teardown_method(self):
        _slide_data_cache.pop("regression-test", None)

    def test_fix_body_dimensions_portrait_modifies_html(self):
        """fix_body_dimensions should replace 1920/1080 with portrait dims."""
        html = "<html><head><style>body { width: 1920px; height: 1080px; }</style></head><body>Hello</body></html>"
        fixed = fix_body_dimensions(html, 1080, 1920)
        assert "width: 1080px" in fixed
        assert "height: 1920px" in fixed
        assert "1920px" not in fixed.split("width")[1].split(";")[0]  # width shouldn't be 1920

    def test_fix_body_dimensions_landscape_noop(self):
        """fix_body_dimensions should be a no-op for standard landscape."""
        html = "<html><head><style>body { width: 1920px; height: 1080px; }</style></head><body>Hello</body></html>"
        fixed = fix_body_dimensions(html, 1920, 1080)
        assert fixed == html

    def test_html_contents_index_matches_slide_number(self):
        """get_html_content(job, N) must return html_contents[N-1]."""
        job_id = "regression-test"
        slides = [{"number": i, "title": f"Slide {i}"} for i in range(1, 4)]
        strategy = {"theme": "test"}
        save_slide_data(job_id, slides, strategy)

        html_list = [
            "<html><body>Slide 1 content</body></html>",
            "<html><body>Slide 2 content</body></html>",
            "<html><body>Slide 3 content</body></html>",
        ]
        save_html_contents(job_id, html_list)

        for i in range(1, 4):
            result = get_html_content(job_id, i)
            assert result == html_list[i - 1], (
                f"Slide {i}: expected html_contents[{i-1}] but got different HTML"
            )

    def test_update_html_content_updates_correct_index(self):
        """update_html_content should modify exactly the right slide."""
        job_id = "regression-test"
        save_slide_data(job_id, [{"number": 1}, {"number": 2}], {})
        save_html_contents(job_id, ["<html>A</html>", "<html>B</html>"])

        update_html_content(job_id, 2, "<html>B-updated</html>")

        assert get_html_content(job_id, 1) == "<html>A</html>", "Slide 1 should be untouched"
        assert get_html_content(job_id, 2) == "<html>B-updated</html>", "Slide 2 should be updated"

    def test_html_contents_updated_after_fix_body_dimensions(self):
        """Simulate the rendering flow: after fix_body_dimensions, the stored
        HTML should be the post-processed version (the actual bug scenario)."""
        job_id = "regression-test"
        save_slide_data(job_id, [{"number": 1}], {})

        original_html = "<html><head><style>body { width: 1920px; height: 1080px; }</style></head><body>Content</body></html>"
        html_contents = [original_html]
        save_html_contents(job_id, html_contents)

        # Simulate what the rendering loop does (portrait mode)
        vw, vh = 1080, 1920
        html = original_html
        html = fix_body_dimensions(html, vw, vh)
        # The fix: update html_contents with the post-processed version
        html_contents[-1] = html
        save_html_contents(job_id, html_contents)

        stored = get_html_content(job_id, 1)
        assert "width: 1080px" in stored, (
            "Stored HTML must contain the fixed dimensions, not the original 1920px"
        )
        assert stored == html, "Stored HTML must exactly match the rendered version"

    def test_out_of_range_slide_number_returns_none(self):
        """Requesting a slide beyond the list should return None, not crash."""
        job_id = "regression-test"
        save_slide_data(job_id, [{"number": 1}], {})
        save_html_contents(job_id, ["<html>Only slide</html>"])

        assert get_html_content(job_id, 0) is None
        assert get_html_content(job_id, 2) is None
        assert get_html_content(job_id, -1) is None


# ---------------------------------------------------------------------------
# Bug 1 additional: API endpoint returns correct slide for given number
# ---------------------------------------------------------------------------

class TestGetSlideHtmlEndpoint:
    """Test the GET /api/slides/{job_id}/html/{slide_number} endpoint."""

    def setup_method(self):
        _slide_data_cache.pop("api-test", None)

    def teardown_method(self):
        _slide_data_cache.pop("api-test", None)

    def test_get_slide_html_returns_correct_slide(self, test_client):
        """The API should return the HTML for the requested slide number."""
        from main import jobs
        from services.pipeline import pipelines, HybridPipeline
        from unittest.mock import patch, MagicMock

        job_id = "api-test"
        jobs[job_id] = {"status": "completed"}

        save_slide_data(job_id, [{"number": 1}, {"number": 2}, {"number": 3}], {})
        save_html_contents(job_id, [
            "<html><body>First slide</body></html>",
            "<html><body>Second slide</body></html>",
            "<html><body>Third slide</body></html>",
        ])

        mock_pipeline = MagicMock(spec=HybridPipeline)
        mock_pipeline.aspect_ratio = "landscape"
        pipelines[job_id] = mock_pipeline

        try:
            # Request slide 2
            res = test_client.get(f"/api/slides/{job_id}/html/2")
            assert res.status_code == 200
            data = res.json()
            assert "Second slide" in data["html"], (
                "Requesting slide 2 must return the second slide's HTML"
            )
            assert "First slide" not in data["html"]
            assert "Third slide" not in data["html"]

            # Request slide 3
            res = test_client.get(f"/api/slides/{job_id}/html/3")
            assert res.status_code == 200
            assert "Third slide" in res.json()["html"]
        finally:
            jobs.pop(job_id, None)
            pipelines.pop(job_id, None)


# ---------------------------------------------------------------------------
# Sprint 2: slide-edit endpoints must schedule a debounced slides-cache task
# so edits eventually land in Supabase Storage. Rather than exercising the
# real HTTP stack (which requires Playwright, Supabase, etc.), we poke the
# debounce helper directly to pin its contract:
#   - identical-project rapid calls coalesce to a single task
#   - missing user_id/project_id is a no-op (no anonymous uploads)
# ---------------------------------------------------------------------------


class TestSlidesCacheDebounce:
    def _drain(self):
        """Cancel any leftover debounce tasks from other tests / runs."""
        import asyncio
        from main import _slides_cache_debounce
        for k, t in list(_slides_cache_debounce.items()):
            if not t.done():
                t.cancel()
        _slides_cache_debounce.clear()

    def test_debounce_coalesces_rapid_edits(self):
        """Five schedule calls within the debounce window produce exactly 1
        pending task per project_id (second call cancels the first, etc.)."""
        import asyncio
        from main import (
            _schedule_slides_cache_debounced,
            _slides_cache_debounce,
        )

        async def _run():
            self._drain()
            for _ in range(5):
                _schedule_slides_cache_debounced("job-1", "user-a", "proj-xyz")
            tasks = list(_slides_cache_debounce.values())
            # Exactly one task should remain pending for this project
            assert len(tasks) == 1
            # And the previous 4 should have been cancelled
            task = tasks[0]
            assert not task.done()
            # Cleanup
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass
            self._drain()

        asyncio.run(_run())

    def test_debounce_per_project_not_global(self):
        """Two different project_ids get two separate tasks (no coalescing
        across projects — otherwise one busy user would delay another)."""
        import asyncio
        from main import (
            _schedule_slides_cache_debounced,
            _slides_cache_debounce,
        )

        async def _run():
            self._drain()
            _schedule_slides_cache_debounced("job-a", "user-a", "proj-A")
            _schedule_slides_cache_debounced("job-b", "user-a", "proj-B")
            assert len(_slides_cache_debounce) == 2
            for t in _slides_cache_debounce.values():
                t.cancel()
            self._drain()

        asyncio.run(_run())

    def test_debounce_noop_without_ids(self):
        """Anonymous session (no user_id / project_id) → no task registered."""
        import asyncio
        from main import (
            _schedule_slides_cache_debounced,
            _slides_cache_debounce,
        )

        async def _run():
            self._drain()
            _schedule_slides_cache_debounced("job-x", None, "proj-z")
            _schedule_slides_cache_debounced("job-x", "user-a", None)
            _schedule_slides_cache_debounced("job-x", None, None)
            assert len(_slides_cache_debounce) == 0

        asyncio.run(_run())

    def test_immediate_schedule_fires_task(self):
        """_schedule_slides_cache_immediate creates a task right away (not
        routed through the debounce window)."""
        import asyncio
        from main import _schedule_slides_cache_immediate

        async def _run():
            # Install a stub for the actual upload task so we don't hit HTTP.
            from main import jobs
            import main as main_mod
            created = []

            original = main_mod._cache_slides_to_storage

            async def stub(job_id, user_id, project_id):
                created.append((job_id, user_id, project_id))

            main_mod._cache_slides_to_storage = stub
            try:
                jobs["test-job"] = {"id": "test-job"}
                _schedule_slides_cache_immediate("test-job", "user-1", "proj-1")
                # Let the event loop run the scheduled task
                await asyncio.sleep(0)
                await asyncio.sleep(0)  # may need a couple ticks
                assert created == [("test-job", "user-1", "proj-1")]
            finally:
                main_mod._cache_slides_to_storage = original
                jobs.pop("test-job", None)

        asyncio.run(_run())

    def test_immediate_schedule_noop_without_ids(self):
        """Anonymous session bypasses the Storage path entirely."""
        import asyncio
        from main import _schedule_slides_cache_immediate

        async def _run():
            import main as main_mod
            created = []

            async def stub(job_id, user_id, project_id):
                created.append(job_id)

            original = main_mod._cache_slides_to_storage
            main_mod._cache_slides_to_storage = stub
            try:
                _schedule_slides_cache_immediate("test-job", None, None)
                await asyncio.sleep(0)
                assert created == []
            finally:
                main_mod._cache_slides_to_storage = original

        asyncio.run(_run())

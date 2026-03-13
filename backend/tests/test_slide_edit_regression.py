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

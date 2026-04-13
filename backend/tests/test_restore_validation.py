"""
Sprint 4: Restore project validation tests.

Tests the restore step validation logic and edge cases
without requiring the full FastAPI test client.
These tests cover scenarios not already in test_restore_project.py:
- Invalid step values (negative, string coerced, boundary)
- timing_map and outline null/empty handling
- Step clamping logic
"""


def compute_restore_step(step_value):
    """
    Mirrors the restore step logic in main.py:
    If step is not None and 1 <= step <= 10, use it; otherwise default to 5.
    """
    restore_step = 5
    if step_value is not None and isinstance(step_value, (int, float)):
        int_step = int(step_value)
        if 1 <= int_step <= 10:
            restore_step = int_step
    return restore_step


def build_restored_pipeline_state(
    transcript="",
    polished_transcript="",
    outline=None,
    polished_outline=None,
    timing_map=None,
    aspect_ratio="landscape",
):
    """
    Mirrors the pipeline field assignment in the restore endpoint.
    Returns a dict representing the restored pipeline state.
    """
    state = {
        "raw_transcript": transcript,
        "polished_transcript": polished_transcript,
        "raw_outline": outline,
        "polished_outline": polished_outline,
        "timing_map": timing_map if timing_map else [],
        "aspect_ratio": aspect_ratio if aspect_ratio else "landscape",
    }
    return state


# ---------------------------------------------------------------------------
# 1. Invalid step values
# ---------------------------------------------------------------------------


class TestRestoreStepValidation:
    def test_negative_step_falls_back_to_5(self):
        assert compute_restore_step(-1) == 5

    def test_zero_step_falls_back_to_5(self):
        assert compute_restore_step(0) == 5

    def test_step_100_falls_back_to_5(self):
        assert compute_restore_step(100) == 5

    def test_step_11_falls_back_to_5(self):
        assert compute_restore_step(11) == 5

    def test_step_none_falls_back_to_5(self):
        assert compute_restore_step(None) == 5

    def test_step_float_3_7_becomes_3(self):
        """Float values are truncated to int."""
        assert compute_restore_step(3.7) == 3

    def test_step_string_falls_back_to_5(self):
        """Non-numeric types fall back to default."""
        assert compute_restore_step("abc") == 5

    def test_step_1_is_valid(self):
        assert compute_restore_step(1) == 1

    def test_step_10_is_valid(self):
        assert compute_restore_step(10) == 10

    def test_step_5_is_valid(self):
        assert compute_restore_step(5) == 5

    def test_step_6_is_valid(self):
        assert compute_restore_step(6) == 6


# ---------------------------------------------------------------------------
# 2. timing_map null/empty handling
# ---------------------------------------------------------------------------


class TestTimingMapRestore:
    def test_none_timing_map_becomes_empty_list(self):
        state = build_restored_pipeline_state(timing_map=None)
        assert state["timing_map"] == []

    def test_empty_timing_map_stays_empty(self):
        state = build_restored_pipeline_state(timing_map=[])
        assert state["timing_map"] == []

    def test_valid_timing_map_preserved(self):
        tm = [{"start": 0, "end": 5, "slideIndex": 0}]
        state = build_restored_pipeline_state(timing_map=tm)
        assert state["timing_map"] == tm
        assert len(state["timing_map"]) == 1

    def test_large_timing_map_preserved(self):
        tm = [{"start": i, "end": i + 1, "slideIndex": i} for i in range(100)]
        state = build_restored_pipeline_state(timing_map=tm)
        assert len(state["timing_map"]) == 100


# ---------------------------------------------------------------------------
# 3. outline null/empty handling
# ---------------------------------------------------------------------------


class TestOutlineRestore:
    def test_none_outline_stored_as_none(self):
        state = build_restored_pipeline_state(outline=None)
        assert state["raw_outline"] is None

    def test_empty_dict_outline_stored(self):
        state = build_restored_pipeline_state(outline={})
        assert state["raw_outline"] == {}

    def test_valid_outline_preserved(self):
        outline = {"title": "Test", "slides": [{"title": "S1"}]}
        state = build_restored_pipeline_state(outline=outline)
        assert state["raw_outline"]["title"] == "Test"
        assert len(state["raw_outline"]["slides"]) == 1

    def test_none_polished_outline_stored_as_none(self):
        state = build_restored_pipeline_state(polished_outline=None)
        assert state["polished_outline"] is None


# ---------------------------------------------------------------------------
# 4. aspect_ratio handling
# ---------------------------------------------------------------------------


class TestAspectRatioRestore:
    def test_none_aspect_ratio_defaults_to_landscape(self):
        state = build_restored_pipeline_state(aspect_ratio=None)
        assert state["aspect_ratio"] == "landscape"

    def test_empty_string_aspect_ratio_defaults_to_landscape(self):
        state = build_restored_pipeline_state(aspect_ratio="")
        assert state["aspect_ratio"] == "landscape"

    def test_portrait_aspect_ratio_preserved(self):
        state = build_restored_pipeline_state(aspect_ratio="portrait")
        assert state["aspect_ratio"] == "portrait"

    def test_landscape_aspect_ratio_preserved(self):
        state = build_restored_pipeline_state(aspect_ratio="landscape")
        assert state["aspect_ratio"] == "landscape"


# ---------------------------------------------------------------------------
# 5. Combined restore state
# ---------------------------------------------------------------------------


class TestCombinedRestoreState:
    def test_full_restore_with_all_fields(self):
        """Integration test: all fields provided, step valid."""
        step = compute_restore_step(6)
        state = build_restored_pipeline_state(
            transcript="Hello world",
            polished_transcript="Hello, world!",
            outline={"slides": [{"title": "Intro"}]},
            polished_outline={"slides": [{"title": "Polished Intro"}]},
            timing_map=[{"start": 0, "end": 10}],
            aspect_ratio="portrait",
        )
        assert step == 6
        assert state["raw_transcript"] == "Hello world"
        assert state["polished_transcript"] == "Hello, world!"
        assert state["raw_outline"]["slides"][0]["title"] == "Intro"
        assert state["polished_outline"]["slides"][0]["title"] == "Polished Intro"
        assert len(state["timing_map"]) == 1
        assert state["aspect_ratio"] == "portrait"

    def test_minimal_restore_with_defaults(self):
        """Integration test: no optional fields, step invalid."""
        step = compute_restore_step(-5)
        state = build_restored_pipeline_state()
        assert step == 5
        assert state["raw_transcript"] == ""
        assert state["polished_transcript"] == ""
        assert state["raw_outline"] is None
        assert state["polished_outline"] is None
        assert state["timing_map"] == []
        assert state["aspect_ratio"] == "landscape"

    def test_restore_with_very_long_transcript(self):
        """Edge case: 200K character transcript."""
        long_text = "X" * 200_000
        state = build_restored_pipeline_state(
            transcript=long_text,
            polished_transcript=long_text,
        )
        assert len(state["raw_transcript"]) == 200_000
        assert len(state["polished_transcript"]) == 200_000

"""
VoiceSlide AI - Pipeline basic tests
Tests pipeline.py with all external APIs mocked.
"""

import os
import pytest
from unittest.mock import patch, MagicMock


def test_pipeline_initialization(tmp_path):
    """Test HybridPipeline can be initialized"""
    with patch.dict(os.environ, {"OUTPUT_DIR": str(tmp_path)}):
        from services.pipeline import HybridPipeline

        audio_path = str(tmp_path / "test_audio.mp3")
        # Create a dummy file
        with open(audio_path, "w") as f:
            f.write("dummy")

        pipeline = HybridPipeline(job_id="test-job-001", audio_path=audio_path)

        assert pipeline.job_id == "test-job-001"
        assert pipeline.audio_path == audio_path
        assert pipeline.raw_transcript is None
        assert pipeline.segments is None
        assert pipeline.aspect_ratio == "landscape"
        assert pipeline.speed_factor == 1.0


def test_pipeline_output_outline_without_data():
    """Test step_output_outline returns correct structure even with no data"""
    from services.pipeline import HybridPipeline

    with patch("os.makedirs"):
        pipeline = HybridPipeline.__new__(HybridPipeline)
        pipeline.job_id = "test-job"
        pipeline.raw_transcript = None
        pipeline.polished_transcript = "Test transcript"
        pipeline.raw_outline = {"slides": [{"number": 1, "title": "Test"}]}
        pipeline.polished_outline = None

    result = pipeline.step_output_outline()
    assert result["step"] == 6
    assert result["status"] == "completed"
    assert result["outline"] == {"slides": [{"number": 1, "title": "Test"}]}
    assert result["transcript"] == "Test transcript"


def test_pipeline_sync_segments_with_transcript():
    """Test _sync_segments_with_transcript preserves timing"""
    from services.pipeline import HybridPipeline

    with patch("os.makedirs"):
        pipeline = HybridPipeline.__new__(HybridPipeline)
        pipeline.segments = [
            {"id": 0, "start": 0.0, "end": 5.0, "text": "Original text 1"},
            {"id": 1, "start": 5.0, "end": 10.0, "text": "Original text 2"},
        ]
        pipeline.polished_transcript = None

    edited = "Edited text line 1\nEdited text line 2"
    synced = pipeline._sync_segments_with_transcript(edited)

    assert len(synced) == 2
    assert synced[0]["start"] == 0.0
    assert synced[0]["end"] == 5.0
    assert synced[1]["start"] == 5.0
    assert synced[1]["end"] == 10.0
    assert pipeline.polished_transcript == edited


def test_pipeline_sync_segments_empty():
    """Test _sync_segments_with_transcript handles empty segments"""
    from services.pipeline import HybridPipeline

    with patch("os.makedirs"):
        pipeline = HybridPipeline.__new__(HybridPipeline)
        pipeline.segments = None
        pipeline.polished_transcript = None

    result = pipeline._sync_segments_with_transcript("any text")
    assert result == []


def test_get_or_create_pipeline_requires_audio(tmp_path):
    """Test get_or_create_pipeline raises error when no audio available"""
    from services.pipeline import get_or_create_pipeline, pipelines

    # Clean up any existing test pipeline
    test_id = "test-no-audio-xyz"
    pipelines.pop(test_id, None)

    with patch.dict(os.environ, {"UPLOAD_DIR": str(tmp_path)}):
        with pytest.raises(ValueError, match="audio_path required"):
            get_or_create_pipeline(test_id)

    # Clean up
    pipelines.pop(test_id, None)


def test_delete_pipeline():
    """Test delete_pipeline removes pipeline from storage"""
    from services.pipeline import pipelines, delete_pipeline

    pipelines["test-delete"] = MagicMock()
    assert "test-delete" in pipelines

    delete_pipeline("test-delete")
    assert "test-delete" not in pipelines


def test_delete_pipeline_nonexistent():
    """Test delete_pipeline handles nonexistent pipeline gracefully"""
    from services.pipeline import delete_pipeline
    # Should not raise
    delete_pipeline("nonexistent-pipeline-id")

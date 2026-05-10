"""Regression tests for exposing Sprint 1〜2 telemetry fields on status APIs."""

from __future__ import annotations


def test_status_exposes_generation_telemetry_summary_total_calls(test_client):
    from main import jobs

    job_id = "test-status-total-calls"
    try:
        jobs[job_id] = {
            "id": job_id,
            "status": "completed",
            "generation_telemetry_summary": {
                "job_id": job_id,
                "entry_count": 3,
                "total_calls": 3,
                "fallback_count": 1,
            },
            "design_quality_metrics": [
                {
                    "slide_number": 1,
                    "quality_gate": "pass",
                    "min_font_size_px": 32,
                    "small_text_count": 0,
                }
            ],
        }

        response = test_client.get(f"/api/status/{job_id}")

        assert response.status_code == 200
        body = response.json()
        summary = body["generation_telemetry_summary"]
        assert summary["entry_count"] == 3
        assert summary["total_calls"] == 3
        assert summary["total_calls"] == summary["entry_count"]
        assert body["design_quality_metrics"][0]["quality_gate"] == "pass"
    finally:
        jobs.pop(job_id, None)


def test_batch_status_exposes_generation_telemetry_summary_total_calls(test_client):
    from main import jobs, slide_progress

    job_id = "test-batch-total-calls"
    try:
        jobs[job_id] = {
            "id": job_id,
            "generation_telemetry_summary": {
                "job_id": job_id,
                "entry_count": 2,
                "total_calls": 2,
                "fallback_count": 0,
            },
            "design_quality_metrics": [
                {
                    "slide_number": 1,
                    "quality_gate": "fail",
                    "min_font_size_px": 18,
                    "small_text_count": 1,
                }
            ],
        }
        slide_progress[job_id] = {
            "status": "complete",
            "message": "バッチ完了",
            "generation_telemetry_summary": jobs[job_id]["generation_telemetry_summary"],
            "design_quality_metrics": jobs[job_id]["design_quality_metrics"],
        }

        response = test_client.get(f"/api/batch-status/{job_id}")

        assert response.status_code == 200
        body = response.json()
        summary = body["generation_telemetry_summary"]
        assert summary["entry_count"] == 2
        assert summary["total_calls"] == 2
        assert summary["total_calls"] == summary["entry_count"]
        assert body["design_quality_metrics"][0]["quality_gate"] == "fail"
    finally:
        jobs.pop(job_id, None)
        slide_progress.pop(job_id, None)

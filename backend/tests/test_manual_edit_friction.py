"""Manual edit friction recorder regression tests."""


def test_manual_edit_friction_records_privacy_safe_event_and_summary(test_client):
    from main import jobs, manual_edit_friction_events

    job_id = "job-manual-edit-friction"
    jobs[job_id] = {"id": job_id, "status": "completed"}
    manual_edit_friction_events.pop(job_id, None)
    try:
        response = test_client.post(
            f"/api/manual-edit-friction/{job_id}",
            json={
                "event_type": "direct_editor_text_input",
                "slide_number": 2,
                "workflow_mode": "full-ai",
                "design_mode": "pro",
                "elapsed_ms": 1234,
                "source": "iframe",
                "details": {
                    "target_tag": "H1",
                    "text_length_before": 12,
                    "text_length_after": 18,
                    "edited_text": "これは保存してはいけない本文",
                },
                "quality_snapshot": {
                    "slide_number": 2,
                    "quality_gate": "warn",
                    "fallback_used": False,
                    "text_clipping_detected": True,
                    "small_text_count": 1,
                    "warnings": ["raw warning should not be copied"],
                },
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert body["manual_edit_friction_summary"]["event_count"] == 1
        assert body["manual_edit_friction_summary"]["by_type"]["direct_editor_text_input"] == 1
        assert body["manual_edit_friction_summary"]["by_slide"]["2"]["event_count"] == 1

        stored_event = jobs[job_id]["manual_edit_friction_events"][0]
        assert stored_event["details"]["target_tag"] == "H1"
        assert stored_event["details"]["text_length_after"] == 18
        assert "edited_text" not in stored_event["details"]
        assert stored_event["quality_snapshot"]["quality_gate"] == "warn"
        assert stored_event["quality_snapshot"]["warnings_count"] == 1
    finally:
        jobs.pop(job_id, None)
        manual_edit_friction_events.pop(job_id, None)


def test_manual_edit_friction_rejects_unknown_event_type(test_client):
    from main import jobs, manual_edit_friction_events

    job_id = "job-manual-edit-unknown"
    jobs[job_id] = {"id": job_id, "status": "completed"}
    manual_edit_friction_events.pop(job_id, None)
    try:
        response = test_client.post(
            f"/api/manual-edit-friction/{job_id}",
            json={"event_type": "raw_text_changed", "slide_number": 1},
        )

        assert response.status_code == 400
        assert manual_edit_friction_events.get(job_id) is None
    finally:
        jobs.pop(job_id, None)
        manual_edit_friction_events.pop(job_id, None)


def test_status_and_batch_status_expose_manual_edit_friction_summary(test_client):
    from main import jobs, manual_edit_friction_events, slide_progress

    job_id = "job-manual-edit-status"
    summary = {"event_count": 2, "by_type": {"slide_selected": 1, "direct_editor_opened": 1}}
    jobs[job_id] = {
        "id": job_id,
        "status": "completed",
        "manual_edit_friction_summary": summary,
        "design_quality_metrics": [],
    }
    slide_progress[job_id] = {"status": "complete", "design_quality_metrics": []}
    manual_edit_friction_events.pop(job_id, None)
    try:
        status_response = test_client.get(f"/api/status/{job_id}")
        batch_response = test_client.get(f"/api/batch-status/{job_id}")

        assert status_response.status_code == 200
        assert status_response.json()["manual_edit_friction_summary"] == summary
        assert batch_response.status_code == 200
        assert batch_response.json()["manual_edit_friction_summary"] == summary
    finally:
        jobs.pop(job_id, None)
        slide_progress.pop(job_id, None)
        manual_edit_friction_events.pop(job_id, None)

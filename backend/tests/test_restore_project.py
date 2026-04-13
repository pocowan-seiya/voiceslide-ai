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

"""
VoiceSlide AI - API health check tests
Tests FastAPI app startup and basic endpoints using TestClient (no external APIs).
"""


def test_root_endpoint(test_client):
    """Test that the root endpoint returns expected response"""
    response = test_client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "service" in data
    assert "VoiSlide" in data["service"]


def test_aspect_ratios_endpoint(test_client):
    """Test the aspect ratios endpoint returns valid data"""
    response = test_client.get("/api/aspect-ratios")
    assert response.status_code == 200
    data = response.json()
    assert "presets" in data
    assert "landscape" in data["presets"]
    assert "portrait" in data["presets"]


def test_color_themes_endpoint(test_client):
    """Test the color themes endpoint returns valid data"""
    response = test_client.get("/api/color-themes")
    assert response.status_code == 200
    data = response.json()
    assert "themes" in data
    assert isinstance(data["themes"], list)
    assert len(data["themes"]) > 0


def test_nonexistent_job_status_returns_404(test_client):
    """Test that requesting status for a nonexistent job returns 404"""
    response = test_client.get("/api/status/nonexistent-job-id")
    assert response.status_code == 404


def test_auth_check_without_cookie(test_client):
    """Test auth check without session cookie"""
    response = test_client.get("/api/auth/check")
    assert response.status_code == 200
    data = response.json()
    # Should indicate not authenticated or password not required
    assert "authenticated" in data or "password_required" in data

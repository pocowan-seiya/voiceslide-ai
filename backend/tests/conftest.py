"""
VoiceSlide AI - pytest configuration and fixtures
"""

import os
import sys
import pytest

# Add backend directory to Python path so imports work
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Set dummy environment variables before importing any app modules
os.environ.setdefault("OPENAI_API_KEY", "test-dummy-key")
os.environ.setdefault("GEMINI_API_KEY", "test-dummy-key")
os.environ.setdefault("ACCESS_PASSWORD", "")


@pytest.fixture
def test_client():
    """Create a FastAPI TestClient"""
    from fastapi.testclient import TestClient
    from main import app
    return TestClient(app)


@pytest.fixture
def sample_segments():
    """Sample transcription segments for testing"""
    return [
        {"id": 0, "start": 0.0, "end": 5.0, "text": "Hello, welcome to this presentation."},
        {"id": 1, "start": 5.0, "end": 10.0, "text": "Today we will discuss AI technology."},
        {"id": 2, "start": 10.0, "end": 15.0, "text": "Let's get started with the basics."},
    ]

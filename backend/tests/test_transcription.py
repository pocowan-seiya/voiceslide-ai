"""
VoiceSlide AI - Transcription service unit tests
All OpenAI/Gemini API calls are mocked.
"""

import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock


def test_get_available_gemini_model_does_not_print_key_fragments(capsys):
    """Gemini model discovery logs must not reveal API key prefixes/suffixes."""
    from services.transcription import get_available_gemini_model

    synthetic_key = "AIzaSy1234567890abcdef"
    with patch("services.transcription.genai.configure"), \
         patch("services.transcription.genai.list_models", return_value=[]):
        get_available_gemini_model(synthetic_key)

    captured = capsys.readouterr()
    assert "AIzaSy1234" not in captured.out
    assert "cdef" not in captured.out
    assert "[REDACTED]" in captured.out


def test_format_timestamp():
    """Test SRT timestamp formatting"""
    from services.transcription import format_timestamp

    assert format_timestamp(0.0) == "00:00:00,000"
    assert format_timestamp(61.5) == "00:01:01,500"
    assert format_timestamp(3661.123) == "01:01:01,123"


def test_generate_srt():
    """Test SRT generation from segments"""
    from services.transcription import generate_srt

    segments = [
        {"id": 0, "start": 0.0, "end": 2.5, "text": "Hello"},
        {"id": 1, "start": 2.5, "end": 5.0, "text": "World"},
    ]

    srt = generate_srt(segments)
    lines = srt.strip().split("\n")

    assert lines[0] == "1"
    assert "00:00:00,000 --> 00:00:02,500" in lines[1]
    assert lines[2] == "Hello"
    assert lines[4] == "2"
    assert lines[6] == "World"


def test_get_openai_client_with_key():
    """Test OpenAI client creation with explicit key"""
    with patch("services.transcription.OpenAI") as mock_openai:
        from services.transcription import get_openai_client

        client = get_openai_client("test-key-123")
        mock_openai.assert_called_once_with(api_key="test-key-123")


def test_get_openai_client_no_key():
    """Test OpenAI client raises error without key"""
    from services.transcription import get_openai_client

    with patch("services.transcription.OPENAI_API_KEY", ""):
        with pytest.raises(ValueError, match="OpenAI API key is required"):
            get_openai_client(None)


def test_transcribe_audio_mocked():
    """Test transcribe_audio with mocked OpenAI Whisper"""
    mock_segment = MagicMock()
    mock_segment.id = 0
    mock_segment.start = 0.0
    mock_segment.end = 3.0
    mock_segment.text = " Test transcription "

    mock_response = MagicMock()
    mock_response.segments = [mock_segment]

    mock_client = MagicMock()
    mock_client.audio.transcriptions.create.return_value = mock_response

    with patch("services.transcription.get_openai_client", return_value=mock_client), \
         patch("os.path.getsize", return_value=1000), \
         patch("builtins.open", MagicMock()):

        from services.transcription import _transcribe_sync

        result = _transcribe_sync("/fake/audio.mp3", "test-key")

    assert result["full_text"] == "Test transcription"
    assert len(result["segments"]) == 1
    assert result["segments"][0]["text"] == "Test transcription"
    assert result["duration"] == 3.0


def test_polish_transcript_no_key():
    """Test polish_transcript returns original text when no API key"""
    with patch("services.transcription.GEMINI_API_KEY", ""):
        from services.transcription import polish_transcript

        result = asyncio.run(polish_transcript("Test text", gemini_key=None))
        assert result == "Test text"


def test_polish_transcript_mocked():
    """Test polish_transcript with mocked Gemini API"""
    with patch("services.transcription.GEMINI_API_KEY", "test-key"), \
         patch("services.transcription.get_available_gemini_model", return_value="gemini-pro"), \
         patch("services.transcription.safe_gemini_generate", new_callable=AsyncMock, return_value="Polished text"):

        from services.transcription import polish_transcript

        result = asyncio.run(polish_transcript("Raw text", gemini_key="test-key"))
        assert result == "Polished text"

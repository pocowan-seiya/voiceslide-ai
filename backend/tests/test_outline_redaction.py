import asyncio
from unittest.mock import MagicMock

from services import outline_generator, openrouter_utils


def test_openrouter_generate_redacts_provider_user_id_from_stdout(monkeypatch, capsys):
    class FakeCompletions:
        async def create(self, **kwargs):
            raise RuntimeError("OpenRouter error user_id=user_SYNTHETIC1234567890abcdef key=sk-or-...cdef")

    class FakeChat:
        completions = FakeCompletions()

    class FakeClient:
        chat = FakeChat()

    monkeypatch.setattr(openrouter_utils, "AsyncOpenAI", lambda **kwargs: FakeClient())

    try:
        asyncio.run(openrouter_utils.openrouter_generate(
            model_name="anthropic/claude-opus-4-7",
            prompt="hello",
            key="dummy-openrouter-key",
            max_retries=1,
        ))
    except RuntimeError:
        pass

    captured = capsys.readouterr()
    assert "user_SYNTHETIC1234567890abcdef" not in captured.out
    assert "1234567890abcdef" not in captured.out
    assert "[REDACTED]" in captured.out


def test_generate_outline_redacts_provider_user_id_from_stdout(monkeypatch, capsys):
    async def fake_generate(*args, **kwargs):
        raise RuntimeError("OpenRouter error user_id=user_SYNTHETIC1234567890abcdef key=sk-or-...cdef")

    monkeypatch.setattr(outline_generator, "safe_gemini_generate", fake_generate)
    monkeypatch.setattr(
        outline_generator.openai_client.chat.completions,
        "create",
        MagicMock(side_effect=RuntimeError("GPT fallback user_id=user_SYNTHETIC1234567890abcdef")),
    )

    result = asyncio.run(outline_generator.generate_outline(
        transcript="Short transcript for outline.",
        segments=[{"start": 0.0, "end": 3.0, "text": "Short transcript for outline."}],
        gemini_key="dummy-key",
        openrouter_key="dummy-openrouter-key",
    ))

    captured = capsys.readouterr()
    assert result.get("slides")
    assert "user_SYNTHETIC1234567890abcdef" not in captured.out
    assert "1234567890abcdef" not in captured.out
    assert "[REDACTED]" in captured.out


def test_polish_outline_redacts_provider_user_id_from_stdout(monkeypatch, capsys):
    async def fake_generate(*args, **kwargs):
        raise RuntimeError("OpenRouter error user_id=user_SYNTHETIC1234567890abcdef key=sk-or-...cdef")

    monkeypatch.setattr(outline_generator, "safe_gemini_generate", fake_generate)

    outline = {"slides": [{"title": "Slide 1"}], "_segments": [], "_total_duration": 0}
    result = asyncio.run(outline_generator.polish_outline(
        outline,
        gemini_key="dummy-key",
        openrouter_key="dummy-openrouter-key",
    ))

    captured = capsys.readouterr()
    assert result.get("slides")
    assert "user_SYNTHETIC1234567890abcdef" not in captured.out
    assert "1234567890abcdef" not in captured.out
    assert "[REDACTED]" in captured.out

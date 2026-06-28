import asyncio

from services import slide_design_ai, slide_generator, image_generator


def test_slide_design_ai_model_errors_are_redacted(monkeypatch, capsys):
    async def fake_generate(*args, **kwargs):
        raise RuntimeError("provider user_id=user_SYNTHETIC1234567890abcdef key=sk-or-...cdef")

    monkeypatch.setattr(slide_design_ai, "safe_gemini_generate", fake_generate)

    result = asyncio.run(slide_design_ai.analyze_slide_design(
        slide={"title": "安全なタイトル", "points": ["one"]},
        slide_number=1,
        total_slides=1,
        gemini_key="dummy-key",
    ))

    captured = capsys.readouterr()
    assert result["layout_type"]
    assert "user_SYNTHETIC1234567890abcdef" not in captured.out
    assert "1234567890abcdef" not in captured.out
    assert "[REDACTED]" in captured.out


def test_background_generation_errors_are_redacted(monkeypatch, capsys):
    class FakeModel:
        def __init__(self, *args, **kwargs):
            pass

        def generate_content(self, *args, **kwargs):
            raise RuntimeError("provider user_id=user_SYNTHETIC1234567890abcdef key=sk-or-...cdef")

    monkeypatch.setattr(slide_design_ai.genai, "GenerativeModel", FakeModel)
    monkeypatch.setattr(slide_design_ai.genai, "GenerationConfig", lambda **kwargs: kwargs)

    result = asyncio.run(slide_design_ai.generate_background_image(
        prompt="abstract background",
        gemini_key="dummy-key",
    ))

    captured = capsys.readouterr()
    assert result is None
    assert "user_SYNTHETIC1234567890abcdef" not in captured.out
    assert "1234567890abcdef" not in captured.out
    assert "[REDACTED]" in captured.out


def test_legacy_slide_generator_errors_are_redacted(monkeypatch, capsys):
    async def fake_gemini_outline(*args, **kwargs):
        raise RuntimeError("provider user_id=user_SYNTHETIC1234567890abcdef key=sk-or-...cdef")

    async def fake_gpt_outline(*args, **kwargs):
        return {"slides": []}

    monkeypatch.setattr(slide_generator, "generate_outline_with_gemini", fake_gemini_outline)
    monkeypatch.setattr(slide_generator, "generate_outline_with_gpt4", fake_gpt_outline)

    result = asyncio.run(slide_generator.generate_outline(
        transcript="safe transcript",
        segments=[],
    ))

    captured = capsys.readouterr()
    assert result == {"slides": []}
    assert "user_SYNTHETIC1234567890abcdef" not in captured.out
    assert "1234567890abcdef" not in captured.out
    assert "[REDACTED]" in captured.out


def test_image_generator_errors_are_redacted(monkeypatch, capsys):
    class FakeModel:
        def __init__(self, *args, **kwargs):
            pass

        def generate_content(self, *args, **kwargs):
            raise RuntimeError("provider user_id=user_SYNTHETIC1234567890abcdef key=sk-or-...cdef")

    monkeypatch.setattr(image_generator.genai, "GenerativeModel", FakeModel)
    monkeypatch.setattr(image_generator.genai, "GenerationConfig", lambda **kwargs: kwargs)

    result = asyncio.run(image_generator.generate_slide_illustration(
        title="safe illustration",
        points=["safe point"],
        description="safe description",
        model_name="dummy-model",
    ))

    captured = capsys.readouterr()
    assert result is None
    assert "user_SYNTHETIC1234567890abcdef" not in captured.out
    assert "1234567890abcdef" not in captured.out
    assert "[REDACTED]" in captured.out

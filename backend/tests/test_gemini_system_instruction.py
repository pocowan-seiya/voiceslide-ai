"""
Sprint A — safe_gemini_generate routes `system_prompt` to
`genai.GenerativeModel(system_instruction=...)` on the direct Gemini
path, and to OpenRouter's system role on the proxy path. This test pins
the direct-Gemini path.

Before Sprint A, design/strategy prompts were a single big user-role string
both on Gemini and on OpenRouter. Gemini tolerates it (it has a soft role
convention) but the native system_instruction slot is the correct spot.
Putting it there:
  (a) improves prompt-cache hit rate because the user slot becomes the only
      per-call variable piece, and
  (b) brings behavior parity with OpenRouter-served Claude/GPT.
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

from services.ai_utils import safe_gemini_generate


def _mock_response(text: str = "ok"):
    resp = MagicMock()
    resp.parts = [MagicMock()]
    resp.text = text
    return resp


def test_direct_gemini_passes_system_instruction():
    """When system_prompt is provided and no OpenRouter key is set,
    GenerativeModel must receive system_instruction=<system_prompt>."""
    captured = {}

    def fake_model_ctor(model_name, system_instruction=None):
        captured["model_name"] = model_name
        captured["system_instruction"] = system_instruction
        m = MagicMock()
        m.generate_content = MagicMock(return_value=_mock_response("ok"))
        return m

    with patch("services.ai_utils.genai.configure"), \
         patch("services.ai_utils.genai.GenerativeModel", side_effect=fake_model_ctor):
        asyncio.run(safe_gemini_generate(
            model_name="gemini-3-flash-preview",
            prompt="concrete user task",
            key="fake-key",
            max_retries=1,
            system_prompt="You are an architect.",
        ))

    assert captured["model_name"] == "gemini-3-flash-preview"
    assert captured["system_instruction"] == "You are an architect."


def test_direct_gemini_without_system_prompt_uses_legacy_ctor():
    """system_prompt=None must NOT pass system_instruction=None into the
    GenerativeModel constructor. Some google-generativeai versions raise
    when the kwarg is explicitly None, so the call signature matters —
    this is why the implementation branches instead of always passing it."""
    captured_kwargs = {}

    def fake_model_ctor(*args, **kwargs):
        captured_kwargs.update(kwargs)
        m = MagicMock()
        m.generate_content = MagicMock(return_value=_mock_response("ok"))
        return m

    with patch("services.ai_utils.genai.configure"), \
         patch("services.ai_utils.genai.GenerativeModel", side_effect=fake_model_ctor):
        asyncio.run(safe_gemini_generate(
            model_name="gemini-3-flash-preview",
            prompt="hi",
            key="fake-key",
            max_retries=1,
        ))

    assert "system_instruction" not in captured_kwargs


def test_openrouter_path_forwards_system_prompt():
    """When an OpenRouter key is provided, safe_gemini_generate should
    forward system_prompt through to openrouter_generate, not try to run
    the Gemini path."""
    captured = {}

    async def fake_openrouter_generate(**kwargs):
        captured.update(kwargs)
        return "ok-from-openrouter"

    with patch("services.openrouter_utils.openrouter_generate", side_effect=fake_openrouter_generate):
        result = asyncio.run(safe_gemini_generate(
            model_name="gemini-3-flash-preview",
            prompt="task",
            key="fake-key",
            max_retries=1,
            openrouter_key="or-fake",
            openrouter_model="anthropic/claude-opus-4-6",
            system_prompt="You are an architect.",
        ))

    assert result == "ok-from-openrouter"
    assert captured["system_prompt"] == "You are an architect."
    assert captured["model_name"] == "anthropic/claude-opus-4-6"

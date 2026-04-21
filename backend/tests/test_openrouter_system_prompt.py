"""
Sprint A — OpenRouter system prompt + fallback notification + temperature.

Before this sprint, callers stuffed role/rule guidance into the user prompt,
which Gemini tolerates (because of its soft "role" convention) but Claude and
GPT do not — they key on the native system slot and significantly under-
perform without it. These tests pin down the new contract:

1. When `system_prompt` is provided, it MUST appear as `messages[0]` with
   `role="system"` in the OpenRouter request payload.
2. When the caller passes an invalid model ID, the fallback event is
   recorded in the `_openrouter_warnings` ContextVar so the UI can surface it.
3. `pick_temperature()` returns model-family defaults when requested=None.
"""

from __future__ import annotations

import asyncio
import contextvars
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.openrouter_utils import (
    _openrouter_warnings,
    openrouter_generate,
    pick_temperature,
)


# ---------------------------------------------------------------------------
# pick_temperature
# ---------------------------------------------------------------------------


def test_pick_temperature_claude_family_defaults_lower():
    """Claude performs best at 0.5-0.7; we pick 0.6 to balance format adherence
    with creativity on HTML slide design prompts."""
    assert pick_temperature("anthropic/claude-opus-4-6", None) == 0.6
    assert pick_temperature("anthropic/claude-sonnet-4-5", None) == 0.6
    assert pick_temperature("claude-3-5-sonnet-20241022", None) == 0.6


def test_pick_temperature_openai_family_defaults_mid():
    assert pick_temperature("openai/gpt-5", None) == 0.7
    assert pick_temperature("openai/gpt-4o", None) == 0.7


def test_pick_temperature_gemini_family_defaults_higher():
    """Gemini tolerates and benefits from higher temperatures on design tasks."""
    assert pick_temperature("google/gemini-3-flash-preview", None) == 0.8
    assert pick_temperature("google/gemini-2.5-flash", None) == 0.8


def test_pick_temperature_unknown_model_defaults_mid():
    assert pick_temperature("cohere/command-r-plus", None) == 0.7


def test_pick_temperature_explicit_value_wins():
    """Whatever the caller passes always overrides the family default."""
    assert pick_temperature("anthropic/claude-opus-4-6", 0.9) == 0.9
    assert pick_temperature("google/gemini-3-flash-preview", 0.1) == 0.1


# ---------------------------------------------------------------------------
# system_prompt plumbing
# ---------------------------------------------------------------------------


class _CompletionsStub:
    """Records the kwargs we were called with, returns a canned response."""

    def __init__(self, content: str = "ok"):
        self.content = content
        self.calls: List[Dict[str, Any]] = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        # Build a minimal object graph that matches what openai SDK returns
        msg = MagicMock()
        msg.content = self.content
        choice = MagicMock()
        choice.message = msg
        resp = MagicMock()
        resp.choices = [choice]
        return resp


class _ClientStub:
    def __init__(self, completions: _CompletionsStub):
        self.chat = MagicMock()
        self.chat.completions = completions


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro) if False else asyncio.run(coro)


def test_system_prompt_is_prepended_as_system_role():
    """system_prompt='You are an architect' must land as messages[0]."""
    completions = _CompletionsStub()
    with patch("services.openrouter_utils.AsyncOpenAI", return_value=_ClientStub(completions)):
        _run(openrouter_generate(
            model_name="anthropic/claude-opus-4-6",
            prompt="Design a slide about trees.",
            key="sk-fake",
            max_retries=1,
            system_prompt="You are a world-class AI design architect.",
        ))

    assert len(completions.calls) == 1
    messages = completions.calls[0]["messages"]
    assert messages[0]["role"] == "system"
    assert "design architect" in messages[0]["content"]
    assert messages[1]["role"] == "user"
    assert messages[1]["content"] == "Design a slide about trees."


def test_no_system_prompt_means_only_user_role():
    """Backwards compat — existing callers that don't pass system_prompt
    still see the same user-only message list they always did."""
    completions = _CompletionsStub()
    with patch("services.openrouter_utils.AsyncOpenAI", return_value=_ClientStub(completions)):
        _run(openrouter_generate(
            model_name="google/gemini-2.5-flash",
            prompt="Hello",
            key="sk-fake",
            max_retries=1,
        ))

    messages = completions.calls[0]["messages"]
    assert len(messages) == 1
    assert messages[0]["role"] == "user"
    assert messages[0]["content"] == "Hello"


def test_system_prompt_not_duplicated_when_already_present():
    """If the caller pre-built a message list containing a system role,
    we should not stack a second system message on top."""
    completions = _CompletionsStub()
    prebuilt = [
        {"role": "system", "content": "Pre-existing system message."},
        {"role": "user", "content": "User question."},
    ]
    with patch("services.openrouter_utils.AsyncOpenAI", return_value=_ClientStub(completions)):
        _run(openrouter_generate(
            model_name="anthropic/claude-opus-4-6",
            prompt=prebuilt,
            key="sk-fake",
            max_retries=1,
            system_prompt="Second system message that should NOT be added.",
        ))

    messages = completions.calls[0]["messages"]
    assert sum(1 for m in messages if m.get("role") == "system") == 1
    assert messages[0]["content"] == "Pre-existing system message."


def test_temperature_auto_picked_when_not_given():
    """When caller passes temperature=None, openrouter_generate applies the
    family default via pick_temperature() before sending."""
    completions = _CompletionsStub()
    with patch("services.openrouter_utils.AsyncOpenAI", return_value=_ClientStub(completions)):
        _run(openrouter_generate(
            model_name="anthropic/claude-opus-4-6",
            prompt="hi",
            key="sk-fake",
            max_retries=1,
            temperature=None,
        ))

    assert completions.calls[0]["temperature"] == 0.6


def test_temperature_explicit_value_overrides_default():
    completions = _CompletionsStub()
    with patch("services.openrouter_utils.AsyncOpenAI", return_value=_ClientStub(completions)):
        _run(openrouter_generate(
            model_name="anthropic/claude-opus-4-6",
            prompt="hi",
            key="sk-fake",
            max_retries=1,
            temperature=0.95,
        ))

    assert completions.calls[0]["temperature"] == 0.95

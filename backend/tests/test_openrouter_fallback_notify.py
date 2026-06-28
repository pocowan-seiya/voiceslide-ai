"""
Sprint A — OpenRouter silent-fallback telemetry.

When a user sets their OpenRouter design model to something that turns out
to be invalid (deprecated, misspelled, or not enabled for their account),
openrouter_generate swaps to OPENROUTER_SAFE_FALLBACK_MODEL and keeps going.

Before Sprint A this was completely silent — the user thought they were
paying for Claude Opus 4.7 but was actually being served by
google/gemini-2.5-flash. These tests pin the fix: the fallback event lands
in the `_openrouter_warnings` ContextVar so the backend endpoint handler
can attach it to jobs[job_id]["warnings"] and the UI can toast it.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

from services.openrouter_utils import (
    _openrouter_warnings,
    openrouter_generate,
    OPENROUTER_SAFE_FALLBACK_MODEL,
)


class _FailingThenOKCompletions:
    """First call raises "not a valid model ID" → triggers fallback.
    Second call returns success with the fallback model name in kwargs."""

    def __init__(self):
        self.calls: List[Dict[str, Any]] = []
        self.call_count = 0

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        self.call_count += 1
        if self.call_count == 1:
            # Mimic the shape of OpenRouter's error on bad model id
            raise Exception(
                "Error code: 400 - {'error': {'message': "
                "\"anthropic/claude-opus-4-7\" is not a valid model ID', "
                "'code': 400}}"
            )
        # Second call: return canned success
        msg = MagicMock()
        msg.content = "ok"
        choice = MagicMock()
        choice.message = msg
        resp = MagicMock()
        resp.choices = [choice]
        return resp


class _Client:
    def __init__(self, completions):
        self.chat = MagicMock()
        self.chat.completions = completions


def test_fallback_appends_warning_to_contextvar():
    completions = _FailingThenOKCompletions()
    _openrouter_warnings.set([])
    with patch("services.openrouter_utils.AsyncOpenAI", return_value=_Client(completions)):
        result = asyncio.run(openrouter_generate(
            model_name="anthropic/claude-opus-4-7",
            prompt="design a slide",
            key="sk-fake",
            max_retries=3,
        ))

    # First attempt used the bad model, second used the fallback
    assert completions.call_count == 2
    assert completions.calls[0]["model"] == "anthropic/claude-opus-4-7"
    assert completions.calls[1]["model"] == OPENROUTER_SAFE_FALLBACK_MODEL
    assert result == "ok"

    warnings = _openrouter_warnings.get()
    assert isinstance(warnings, list)
    assert len(warnings) == 1
    w = warnings[0]
    assert w["kind"] == "openrouter_fallback"
    assert w["requested_model"] == "anthropic/claude-opus-4-7"
    assert w["fallback_model"] == OPENROUTER_SAFE_FALLBACK_MODEL
    assert w["reason"] == "invalid_model_id"


def test_fallback_is_noop_when_contextvar_not_initialized():
    """When no caller has set the ContextVar (i.e. token is the default None),
    _record_fallback_warning should not raise. This keeps scripts/tests that
    don't care about warnings from breaking."""
    # Reset to the default state
    try:
        _openrouter_warnings.set(None)
    except Exception:
        pass

    completions = _FailingThenOKCompletions()
    with patch("services.openrouter_utils.AsyncOpenAI", return_value=_Client(completions)):
        # Should NOT raise even though the ContextVar is None
        asyncio.run(openrouter_generate(
            model_name="anthropic/claude-opus-4-7",
            prompt="x",
            key="sk-fake",
            max_retries=3,
        ))


def test_no_fallback_means_no_warning():
    """Normal successful request should leave the ContextVar list empty."""
    class _OK:
        calls: List[Dict[str, Any]] = []

        async def create(self, **kwargs):
            self.calls.append(kwargs)
            msg = MagicMock()
            msg.content = "ok"
            choice = MagicMock()
            choice.message = msg
            resp = MagicMock()
            resp.choices = [choice]
            return resp

    completions = _OK()
    _openrouter_warnings.set([])
    with patch("services.openrouter_utils.AsyncOpenAI", return_value=_Client(completions)):
        asyncio.run(openrouter_generate(
            model_name="google/gemini-2.5-flash",
            prompt="x",
            key="sk-fake",
            max_retries=1,
        ))

    assert _openrouter_warnings.get() == []

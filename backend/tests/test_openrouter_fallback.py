"""
Regression tests for the OpenRouter "invalid model" safe fallback.

Bug: the project shipped with `google/gemini-3-flash` as a hardcoded default
OpenRouter model ID, which OpenRouter rejects with 400 "is not a valid model
ID". Every Polish/Outline/Slide call that fell back to the default failed.

Fix: openrouter_generate now catches that specific 400 error and retries
ONCE with OPENROUTER_SAFE_FALLBACK_MODEL. These tests pin down the contract
so a future refactor can't silently lose that recovery path.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class _BadRequestError(Exception):
    """Mimics openai.BadRequestError's str() format so the fallback check
    matches on '400' and 'not a valid model ID' substrings."""
    def __init__(self, model_name: str):
        super().__init__(
            f"Error code: 400 - {{'error': {{'message': '{model_name} "
            f"is not a valid model ID', 'code': 400}}}}"
        )


def _make_mock_client(side_effects):
    """Build an AsyncOpenAI-like mock whose `chat.completions.create` returns
    the supplied list of side effects in order (each can be an exception or
    a mock response)."""
    client = MagicMock()
    client.chat = MagicMock()
    client.chat.completions = MagicMock()
    client.chat.completions.create = AsyncMock(side_effect=side_effects)
    return client


def _ok_response(text: str):
    mock = MagicMock()
    mock.choices = [MagicMock()]
    mock.choices[0].message = MagicMock()
    mock.choices[0].message.content = text
    return mock


def test_valid_model_returns_without_fallback():
    """Happy path: caller passes a valid model, gets content back."""
    from services.openrouter_utils import openrouter_generate

    client = _make_mock_client([_ok_response("hello world")])

    with patch("services.openrouter_utils.AsyncOpenAI", return_value=client):
        out = asyncio.run(
            openrouter_generate(
                model_name="google/gemini-2.5-flash",
                prompt="hi",
                key="test-key",
                max_retries=3,
            )
        )
    assert out == "hello world"
    # Only one call — no fallback needed
    assert client.chat.completions.create.await_count == 1


def test_invalid_model_triggers_fallback_and_succeeds():
    """The actual bug scenario: caller passes google/gemini-3-flash →
    OpenRouter rejects it → we retry with OPENROUTER_SAFE_FALLBACK_MODEL →
    it succeeds → the user's workflow keeps moving."""
    from services.openrouter_utils import openrouter_generate, OPENROUTER_SAFE_FALLBACK_MODEL

    client = _make_mock_client([
        _BadRequestError("google/gemini-3-flash"),
        _ok_response("fallback worked"),
    ])

    with patch("services.openrouter_utils.AsyncOpenAI", return_value=client):
        out = asyncio.run(
            openrouter_generate(
                model_name="google/gemini-3-flash",
                prompt="hi",
                key="test-key",
                max_retries=3,
            )
        )

    assert out == "fallback worked"
    # Must have called twice: original (failed) + fallback (succeeded)
    assert client.chat.completions.create.await_count == 2

    # Second call must have used the fallback model
    second_kwargs = client.chat.completions.create.await_args_list[1].kwargs
    assert second_kwargs["model"] == OPENROUTER_SAFE_FALLBACK_MODEL


def test_fallback_does_not_recurse():
    """If the fallback model ITSELF is rejected (e.g. OpenRouter outage of
    that provider), we don't ping-pong — the error propagates after one
    retry attempt. Otherwise we'd waste retries before the user sees failure."""
    from services.openrouter_utils import openrouter_generate

    client = _make_mock_client([
        _BadRequestError("google/gemini-3-flash"),
        _BadRequestError("google/gemini-2.5-flash"),
    ])

    with patch("services.openrouter_utils.AsyncOpenAI", return_value=client):
        with pytest.raises(_BadRequestError):
            asyncio.run(
                openrouter_generate(
                    model_name="google/gemini-3-flash",
                    prompt="hi",
                    key="test-key",
                    max_retries=3,
                )
            )

    # Exactly 2 calls: original + 1 fallback, then we give up
    assert client.chat.completions.create.await_count == 2


def test_fallback_not_triggered_for_unrelated_400_errors():
    """A 400 that's NOT about model validity (e.g. bad request payload)
    shouldn't silently swap the model — that would hide real bugs."""
    from services.openrouter_utils import openrouter_generate

    unrelated_400 = Exception("Error code: 400 - malformed request body")
    client = _make_mock_client([unrelated_400])

    with patch("services.openrouter_utils.AsyncOpenAI", return_value=client):
        with pytest.raises(Exception):
            asyncio.run(
                openrouter_generate(
                    model_name="google/gemini-2.5-flash",
                    prompt="hi",
                    key="test-key",
                    max_retries=3,
                )
            )

    # Only 1 call — no fallback because the error didn't match the pattern
    assert client.chat.completions.create.await_count == 1

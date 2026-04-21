"""OpenRouter API utility for multi-model text generation.

OpenRouter provides an OpenAI-compatible API that supports multiple providers
(Anthropic, Google, OpenAI, etc.) with a single API key.
"""

import asyncio
import contextvars
import random
import json
from typing import Any, Optional, List, Dict
from openai import AsyncOpenAI


# Known-working Gemini flash-class fallback. Used when a caller specifies
# a model ID that OpenRouter rejects as invalid (e.g. misspelled, unreleased,
# or provisioned for a different account). Keeps the pipeline alive rather
# than failing the whole user request — Polish/Outline/Slide all still run,
# just on a different model.
OPENROUTER_SAFE_FALLBACK_MODEL = "google/gemini-2.5-flash"


# ContextVar that collects fallback events that happen during a request.
# Set by openrouter_generate() when it swaps to the safe fallback model;
# read by backend/main.py after the user's generation finishes so the UI
# can toast "モデル X が利用不可のため Y にフォールバックしました" — the
# previous behavior was silent, which is how users ended up with "Opus 4.7"
# in settings but actually got served by gemini-2.5-flash.
_openrouter_warnings: contextvars.ContextVar[Optional[List[Dict[str, str]]]] = (
    contextvars.ContextVar("_openrouter_warnings", default=None)
)


def _record_fallback_warning(requested_model: str, fallback_model: str, reason: str) -> None:
    """Append a fallback event to the current request's warning list.

    No-op when the ContextVar isn't set (i.e. caller isn't interested).
    The list is mutated in place so the backend request handler can read
    it after the generate call returns."""
    warnings = _openrouter_warnings.get()
    if warnings is None:
        return
    warnings.append({
        "kind": "openrouter_fallback",
        "requested_model": requested_model,
        "fallback_model": fallback_model,
        "reason": reason,
    })


def pick_temperature(model_name: str, requested: Optional[float]) -> Optional[float]:
    """Choose a default temperature tuned to the target model family.

    Rationale: different model providers have very different "sweet spots"
    for creative generation:
      - Anthropic Claude family performs best at lower temperatures (0.5-0.7);
        higher temps hurt coherence and make it drop format rules.
      - OpenAI GPT family is well-behaved in the 0.6-0.8 range.
      - Google Gemini family tolerates/benefits from higher temperatures
        (0.7-0.9) for design-style tasks.

    The caller's explicit `requested` value always wins — this only fills
    in sensible defaults when the caller passed `None`.

    Model names follow the OpenRouter convention: "<provider>/<model>".
    """
    if requested is not None:
        return requested
    name = (model_name or "").lower()
    if "claude" in name or "anthropic/" in name:
        return 0.6
    if "gpt" in name or "openai/" in name:
        return 0.7
    if "gemini" in name or "google/" in name:
        return 0.8
    return 0.7


async def openrouter_generate(
    model_name: str,
    prompt: Any,
    key: str,
    max_retries: int = 5,
    json_mode: bool = False,
    max_tokens: int = 8192,
    temperature: Optional[float] = None,
    system_prompt: Optional[str] = None,
) -> str:
    """
    Call OpenRouter API with robust retry logic.
    Compatible interface with safe_gemini_generate for easy swapping.

    Args:
        model_name: OpenRouter model ID (e.g., "google/gemini-2.5-flash", "anthropic/claude-opus-4-7")
        prompt: Text prompt or list of message dicts
        key: OpenRouter API key
        max_retries: Max retry attempts
        json_mode: If True, request JSON response format
        max_tokens: Maximum tokens in response
        temperature: Sampling temperature (0.0-2.0). When None, pick_temperature()
                     chooses a model-family default (Claude 0.6, GPT 0.7, Gemini 0.8).
        system_prompt: Optional system message prepended to `messages`. Matters
                       a lot for Anthropic Claude (which takes system prompts
                       strongly into account) and GPT (native system role). For
                       Gemini-family models served through OpenRouter, OpenAI's
                       chat-completions shim maps it to the provider's instruction
                       slot. Pre-`system_prompt` support this file used to shove
                       everything into `user`, which silently neutered Claude's
                       strength and was the main reason OpenRouter felt
                       "lower-quality than direct Gemini".

    If the supplied `model_name` is rejected as invalid by OpenRouter (400),
    we log loudly and retry ONCE with OPENROUTER_SAFE_FALLBACK_MODEL so the
    user's workflow keeps moving. This protects against stale model IDs
    stored in user_settings from before OpenRouter deprecated them.
    """
    # Apply model-family temperature default if the caller didn't specify
    temperature = pick_temperature(model_name, temperature)

    print(
        f"[OpenRouter] Generating with model={model_name}, json_mode={json_mode}, "
        f"max_tokens={max_tokens}, temperature={temperature}, "
        f"system_prompt={'yes' if system_prompt else 'no'}"
    )
    client = AsyncOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=key,
    )

    # Build messages from prompt
    if isinstance(prompt, str):
        messages = [{"role": "user", "content": prompt}]
    elif isinstance(prompt, list):
        # Assume it's already a list of message dicts or content parts
        if len(prompt) > 0 and isinstance(prompt[0], dict) and "role" in prompt[0]:
            messages = list(prompt)
        else:
            # Treat as content parts (text + image for multimodal)
            messages = [{"role": "user", "content": prompt}]
    else:
        messages = [{"role": "user", "content": str(prompt)}]

    # Prepend system message if provided AND not already present. Defensive —
    # callers that pass a pre-built message list might already include a
    # system role; don't duplicate it.
    if system_prompt:
        has_system = any(
            isinstance(m, dict) and m.get("role") == "system" for m in messages
        )
        if not has_system:
            messages = [{"role": "system", "content": system_prompt}] + messages

    delays = [10, 30, 60, 120, 240]
    last_err = None
    # Track whether we've already swapped to the fallback model so we don't
    # retry forever or fall back from the fallback.
    tried_fallback = False
    current_model = model_name

    for attempt in range(max_retries):
        try:
            kwargs: Dict[str, Any] = {
                "model": current_model,
                "messages": messages,
                "max_tokens": max_tokens,
            }
            if temperature is not None:
                kwargs["temperature"] = temperature
            if json_mode:
                kwargs["response_format"] = {"type": "json_object"}

            response = await client.chat.completions.create(**kwargs)

            content = response.choices[0].message.content
            if content is None:
                print(f"[OpenRouter] Empty response from {current_model} (attempt {attempt+1})")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2)
                    continue
                return ""

            return content.strip()

        except Exception as e:
            last_err = e
            err_str = str(e)

            is_rate_limit = any(x in err_str for x in ["429", "rate_limit", "Rate limit", "quota"])
            is_busy = any(x in err_str for x in ["503", "502", "Service Unavailable", "overloaded"])
            # 400 "is not a valid model ID" — caller passed a stale or
            # misspelled model. Swap to the safe fallback and retry ONCE.
            is_invalid_model = (
                "400" in err_str
                and "not a valid model ID" in err_str
                and not tried_fallback
                and current_model != OPENROUTER_SAFE_FALLBACK_MODEL
            )

            if is_invalid_model:
                print(
                    f"[OpenRouter] ✗ model {current_model!r} rejected as invalid by OpenRouter. "
                    f"Falling back to {OPENROUTER_SAFE_FALLBACK_MODEL!r}. "
                    f"Update your settings to pick a currently-supported model."
                )
                # Record the fallback event so the backend can surface it to
                # the UI. See module-level _openrouter_warnings comment.
                _record_fallback_warning(
                    requested_model=current_model,
                    fallback_model=OPENROUTER_SAFE_FALLBACK_MODEL,
                    reason="invalid_model_id",
                )
                current_model = OPENROUTER_SAFE_FALLBACK_MODEL
                tried_fallback = True
                continue  # retry immediately with the fallback model

            if (is_rate_limit or is_busy) and attempt < max_retries - 1:
                wait_time = delays[attempt] + random.uniform(0, 5)
                print(f"[OpenRouter:{current_model}] Rate limit/busy (attempt {attempt+1}/{max_retries}). Waiting {wait_time:.1f}s...")
                await asyncio.sleep(wait_time)
                continue
            else:
                print(f"[OpenRouter] Error ({current_model}): {type(e).__name__}: {err_str[:200]}")
                raise e

    raise last_err


async def smart_generate(
    prompt: Any,
    gemini_key: Optional[str] = None,
    openrouter_key: Optional[str] = None,
    gemini_model: str = "gemini-2.5-flash",
    openrouter_model: str = "google/gemini-2.5-flash",
    max_retries: int = 5,
    json_mode: bool = False,
    config: Any = None,
) -> str:
    """
    Smart text generation router: OpenRouter優先、Geminiフォールバック.

    If openrouter_key is provided, uses OpenRouter with the specified model.
    Otherwise falls back to direct Gemini API.
    """
    if openrouter_key:
        print(f"[SmartGen] Using OpenRouter with model: {openrouter_model}")
        return await openrouter_generate(
            model_name=openrouter_model,
            prompt=prompt,
            key=openrouter_key,
            max_retries=max_retries,
            json_mode=json_mode,
        )
    elif gemini_key:
        from services.ai_utils import safe_gemini_generate
        print(f"[SmartGen] Using direct Gemini with model: {gemini_model}")
        return await safe_gemini_generate(
            model_name=gemini_model,
            prompt=prompt,
            key=gemini_key,
            config=config,
            max_retries=max_retries,
        )
    else:
        raise ValueError("No API key available: provide either openrouter_key or gemini_key")

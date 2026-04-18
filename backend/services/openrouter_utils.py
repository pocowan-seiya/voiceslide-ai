"""OpenRouter API utility for multi-model text generation.

OpenRouter provides an OpenAI-compatible API that supports multiple providers
(Anthropic, Google, OpenAI, etc.) with a single API key.
"""

import asyncio
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


async def openrouter_generate(
    model_name: str,
    prompt: Any,
    key: str,
    max_retries: int = 5,
    json_mode: bool = False,
    max_tokens: int = 8192,
    temperature: Optional[float] = None,
) -> str:
    """
    Call OpenRouter API with robust retry logic.
    Compatible interface with safe_gemini_generate for easy swapping.

    Args:
        model_name: OpenRouter model ID (e.g., "google/gemini-2.5-flash", "anthropic/claude-opus-4-6")
        prompt: Text prompt or list of message dicts
        key: OpenRouter API key
        max_retries: Max retry attempts
        json_mode: If True, request JSON response format
        max_tokens: Maximum tokens in response
        temperature: Sampling temperature (0.0-2.0)

    If the supplied `model_name` is rejected as invalid by OpenRouter (400),
    we log loudly and retry ONCE with OPENROUTER_SAFE_FALLBACK_MODEL so the
    user's workflow keeps moving. This protects against stale model IDs
    stored in user_settings from before OpenRouter deprecated them.
    """
    print(f"[OpenRouter] Generating with model={model_name}, json_mode={json_mode}, max_tokens={max_tokens}, temperature={temperature}")
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
            messages = prompt
        else:
            # Treat as content parts (text + image for multimodal)
            messages = [{"role": "user", "content": prompt}]
    else:
        messages = [{"role": "user", "content": str(prompt)}]

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

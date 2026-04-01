"""OpenRouter API utility for multi-model text generation.

OpenRouter provides an OpenAI-compatible API that supports multiple providers
(Anthropic, Google, OpenAI, etc.) with a single API key.
"""

import asyncio
import random
import json
from typing import Any, Optional, List, Dict
from openai import AsyncOpenAI


async def openrouter_generate(
    model_name: str,
    prompt: Any,
    key: str,
    max_retries: int = 5,
    json_mode: bool = False,
    max_tokens: int = 8192,
) -> str:
    """
    Call OpenRouter API with robust retry logic.
    Compatible interface with safe_gemini_generate for easy swapping.

    Args:
        model_name: OpenRouter model ID (e.g., "google/gemini-3-flash", "anthropic/claude-opus-4-6")
        prompt: Text prompt or list of message dicts
        key: OpenRouter API key
        max_retries: Max retry attempts
        json_mode: If True, request JSON response format
        max_tokens: Maximum tokens in response
    """
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

    for attempt in range(max_retries):
        try:
            kwargs: Dict[str, Any] = {
                "model": model_name,
                "messages": messages,
                "max_tokens": max_tokens,
            }
            if json_mode:
                kwargs["response_format"] = {"type": "json_object"}

            response = await client.chat.completions.create(**kwargs)

            content = response.choices[0].message.content
            if content is None:
                print(f"[OpenRouter] Empty response from {model_name} (attempt {attempt+1})")
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

            if (is_rate_limit or is_busy) and attempt < max_retries - 1:
                wait_time = delays[attempt] + random.uniform(0, 5)
                print(f"[OpenRouter:{model_name}] Rate limit/busy (attempt {attempt+1}/{max_retries}). Waiting {wait_time:.1f}s...")
                await asyncio.sleep(wait_time)
                continue
            else:
                print(f"[OpenRouter] Error ({model_name}): {type(e).__name__}: {err_str[:200]}")
                raise e

    raise last_err


async def smart_generate(
    prompt: Any,
    gemini_key: Optional[str] = None,
    openrouter_key: Optional[str] = None,
    gemini_model: str = "gemini-3-flash-preview",
    openrouter_model: str = "google/gemini-3-flash",
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

import asyncio
import random
import json
import time
import google.generativeai as genai
from typing import Dict, Any, List, Optional

async def safe_gemini_generate(
    model_name: str,
    prompt: Any,
    key: str,
    config: Optional[genai.GenerationConfig] = None,
    max_retries: int = 5,
    openrouter_key: Optional[str] = None,
    openrouter_model: Optional[str] = None,
    use_design_model: bool = False,
    system_prompt: Optional[str] = None,
) -> str:
    """
    Safely call AI API with robust retry logic.
    If openrouter_key is provided, routes through OpenRouter instead of Gemini.
    Works for both single-part (text) and multi-part (text+image) prompts.

    use_design_model: If True, uses the design model (for HTML slide generation)
                      instead of the text model (for outline/transcript).
    system_prompt: Optional system instruction. On Gemini, passed to
                   `genai.GenerativeModel(system_instruction=...)`. On OpenRouter,
                   prepended to `messages` as `{"role": "system", ...}`. Before
                   this existed, callers stuffed role-like guidance into `prompt`
                   which worked on Gemini (Gemini has a soft "role" convention)
                   but NOT on Claude through OpenRouter — Claude keys hard on
                   the system slot, so design prompts underperformed.
    """
    # Check contextvars for OpenRouter config if not explicitly passed
    if not openrouter_key:
        try:
            import contextvars
            # Import from ai_slide_generator where the vars are defined
            from services.ai_slide_generator import _openrouter_key_var, _openrouter_model_var, _openrouter_design_model_var
            openrouter_key = _openrouter_key_var.get(None)
            if openrouter_key and not openrouter_model:
                if use_design_model:
                    openrouter_model = _openrouter_design_model_var.get('google/gemini-3-flash-preview')
                else:
                    openrouter_model = _openrouter_model_var.get('google/gemini-3-flash-preview')
        except (ImportError, LookupError):
            pass

    # OpenRouter routing: text-only prompts can go through OpenRouter
    if openrouter_key and openrouter_model and isinstance(prompt, str):
        from services.openrouter_utils import openrouter_generate
        started = time.monotonic()
        json_mode = False
        max_tokens = 8192
        temperature = None
        if config:
            if hasattr(config, 'response_mime_type') and config.response_mime_type == "application/json":
                json_mode = True
            if hasattr(config, 'max_output_tokens') and config.max_output_tokens:
                max_tokens = config.max_output_tokens
            if hasattr(config, 'temperature') and config.temperature is not None:
                temperature = config.temperature
        result = await openrouter_generate(
            model_name=openrouter_model,
            prompt=prompt,
            key=openrouter_key,
            max_retries=max_retries,
            json_mode=json_mode,
            max_tokens=max_tokens,
            temperature=temperature,
            system_prompt=system_prompt,
        )
        return result

    # Direct Gemini API
    genai.configure(api_key=key)
    # When a system_prompt is provided, pass it via Gemini's native
    # system_instruction slot. Passing None there would error on some
    # google-generativeai versions, so we only supply the kwarg when set.
    if system_prompt:
        model = genai.GenerativeModel(model_name, system_instruction=system_prompt)
    else:
        model = genai.GenerativeModel(model_name)

    # Increased delays: 10, 30, 60, 120, 240 seconds
    delays = [10, 30, 60, 120, 240]
    last_err = None

    for attempt in range(max_retries):
        try:
            # model.generate_content is blocking, run in executor
            started = time.monotonic()
            response = await asyncio.to_thread(model.generate_content, prompt, generation_config=config)

            # Check if response has parts (safety check)
            if not response.parts:
                print(f"[Gemini] Empty response from {model_name} (attempt {attempt+1})")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2)
                    continue
                return ""

            try:
                from services.generation_telemetry import record_current_telemetry
                usage = getattr(response, "usage_metadata", None)
                input_tokens = getattr(usage, "prompt_token_count", None) if usage else None
                output_tokens = getattr(usage, "candidates_token_count", None) if usage else None
                record_current_telemetry(
                    requested_model=model_name,
                    actual_model=model_name,
                    provider="gemini",
                    duration_ms=int((time.monotonic() - started) * 1000),
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    estimated_cost_usd=None,
                )
            except Exception:
                pass
            return response.text.strip()

        except Exception as e:
            last_err = e
            err_str = str(e)

            # Check for rate limit or busy errors
            is_rate_limit = any(x in err_str for x in ["429", "Resource exhausted", "Quota exceeded", "ResourceExhausted"])
            is_busy = any(x in err_str for x in ["503", "Service Unavailable", "Internal error", "500"])

            if (is_rate_limit or is_busy) and attempt < max_retries - 1:
                wait_time = delays[attempt] + random.uniform(0, 5)
                # Dynamic log with context
                loc = f"Gemini:{model_name}"
                print(f"[{loc}] Rate limit/Busy hit (attempt {attempt+1}/{max_retries}). Waiting {wait_time:.1f}s...")
                await asyncio.sleep(wait_time)
                continue
            else:
                # Log the actual error type and snippet
                print(f"[Gemini] Critical error ({model_name}): {type(e).__name__}: {err_str[:200]}")
                raise e

    raise last_err

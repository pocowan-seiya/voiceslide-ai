import asyncio
import random
import json
import google.generativeai as genai
from typing import Dict, Any, List, Optional

async def safe_gemini_generate(model_name: str, prompt: Any, key: str, config: Optional[genai.GenerationConfig] = None, max_retries: int = 5, openrouter_key: Optional[str] = None, openrouter_model: Optional[str] = None, use_design_model: bool = False) -> str:
    """
    Safely call AI API with robust retry logic.
    If openrouter_key is provided, routes through OpenRouter instead of Gemini.
    Works for both single-part (text) and multi-part (text+image) prompts.

    use_design_model: If True, uses the design model (for HTML slide generation)
                      instead of the text model (for outline/transcript).
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
                    openrouter_model = _openrouter_design_model_var.get('google/gemini-3-flash')
                else:
                    openrouter_model = _openrouter_model_var.get('google/gemini-3-flash')
        except (ImportError, LookupError):
            pass

    # OpenRouter routing: text-only prompts can go through OpenRouter
    if openrouter_key and openrouter_model and isinstance(prompt, str):
        from services.openrouter_utils import openrouter_generate
        # Extract json_mode and max_tokens from Gemini config if available
        json_mode = False
        max_tokens = 8192
        if config:
            if hasattr(config, 'response_mime_type') and config.response_mime_type == "application/json":
                json_mode = True
            if hasattr(config, 'max_output_tokens') and config.max_output_tokens:
                max_tokens = config.max_output_tokens
        return await openrouter_generate(
            model_name=openrouter_model,
            prompt=prompt,
            key=openrouter_key,
            max_retries=max_retries,
            json_mode=json_mode,
            max_tokens=max_tokens,
        )

    # Direct Gemini API
    genai.configure(api_key=key)
    model = genai.GenerativeModel(model_name)

    # Increased delays: 10, 30, 60, 120, 240 seconds
    delays = [10, 30, 60, 120, 240]
    last_err = None

    for attempt in range(max_retries):
        try:
            # model.generate_content is blocking, run in executor
            response = await asyncio.to_thread(model.generate_content, prompt, generation_config=config)

            # Check if response has parts (safety check)
            if not response.parts:
                print(f"[Gemini] Empty response from {model_name} (attempt {attempt+1})")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2)
                    continue
                return ""

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

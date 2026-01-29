import asyncio
import random
import json
import google.generativeai as genai
from typing import Dict, Any, List, Optional

async def safe_gemini_generate(model_name: str, prompt: Any, key: str, config: Optional[genai.GenerationConfig] = None, max_retries: int = 5) -> str:
    """
    Safely call Gemini API with robust retry logic for 429/Busy errors.
    Works for both single-part (text) and multi-part (text+image) prompts.
    """
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

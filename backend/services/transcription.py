"""
VoiceSlide AI v3 - Audio Transcription Service
Transcription + Polishing with AI
"""

import os
import asyncio
from concurrent.futures import ThreadPoolExecutor
from openai import OpenAI
import google.generativeai as genai
from typing import Dict, Any, List, Optional

from config import OPENAI_API_KEY, GEMINI_API_KEY


# Thread pool for blocking IO
executor = ThreadPoolExecutor(max_workers=2)


def get_openai_client(api_key: Optional[str] = None) -> OpenAI:
    """Get OpenAI client with provided or default API key"""
    key = api_key or OPENAI_API_KEY
    if not key:
        raise ValueError("OpenAI API key is required. Please set it in settings.")
    return OpenAI(api_key=key)


def configure_gemini(api_key: Optional[str] = None):
    """Configure Gemini with provided or default API key"""
    key = api_key or GEMINI_API_KEY
    if not key:
        raise ValueError("Gemini API key is required. Please set it in settings.")
    
    # Log key info (only first/last 4 chars for security)
    key_preview = f"{key[:8]}...{key[-4:]}" if len(key) > 12 else "***"
    print(f"[Gemini Config] Configuring with key: {key_preview}")
    
    genai.configure(api_key=key)
    
    # Try to list available models for debugging
    try:
        models = list(genai.list_models())
        model_names = [m.name for m in models if 'generateContent' in str(m.supported_generation_methods)]
        print(f"[Gemini Config] Available models: {model_names[:5]}")  # First 5 models
    except Exception as e:
        print(f"[Gemini Config] Could not list models: {str(e)[:100]}")


def _transcribe_sync(audio_path: str, openai_key: Optional[str] = None) -> Dict[str, Any]:
    """Synchronous transcription (runs in thread pool)"""
    client = get_openai_client(openai_key)
    
    with open(audio_path, "rb") as audio_file:
        response = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            response_format="verbose_json",
            timestamp_granularities=["segment"]
        )
    
    segments = []
    for segment in response.segments:
        segments.append({
            "id": segment.id,
            "start": segment.start,
            "end": segment.end,
            "text": segment.text.strip()
        })
    
    srt_content = generate_srt(segments)
    srt_path = audio_path.rsplit(".", 1)[0] + ".srt"
    
    with open(srt_path, "w", encoding="utf-8") as f:
        f.write(srt_content)
    
    return {
        "srt_path": srt_path,
        "segments": segments,
        "full_text": " ".join([s["text"] for s in segments]),
        "duration": segments[-1]["end"] if segments else 0
    }


async def transcribe_audio(audio_path: str, openai_key: Optional[str] = None) -> Dict[str, Any]:
    """Async wrapper for transcription"""
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(executor, _transcribe_sync, audio_path, openai_key)
    return result


def generate_srt(segments: List[Dict[str, Any]]) -> str:
    """Generate SRT format subtitles"""
    srt_lines = []
    for i, seg in enumerate(segments, 1):
        start = format_timestamp(seg["start"])
        end = format_timestamp(seg["end"])
        srt_lines.append(f"{i}")
        srt_lines.append(f"{start} --> {end}")
        srt_lines.append(seg["text"])
        srt_lines.append("")
    return "\n".join(srt_lines)


def format_timestamp(seconds: float) -> str:
    """Format seconds to SRT timestamp"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def _polish_sync(text: str, gemini_key: Optional[str] = None) -> str:
    """Synchronous polishing (runs in thread pool)"""
    try:
        print(f"[Polish] Configuring Gemini with key: {'provided' if gemini_key else 'default'}")
        configure_gemini(gemini_key)
        
        prompt = f"""以下の文字起こしテキストを読みやすく整形してください。
    
要件:
- 「えー」「あー」などのフィラーを削除
- 文章を自然に区切る
- 明らかな言い間違いを修正
- 意味は変えない
- 敬体（です・ます調）を維持

元のテキスト:
{text}

整形後:"""
        
        # Try different model names (API version compatibility)
        model_names = ["gemini-2.0-flash-exp", "gemini-1.5-flash-latest", "gemini-pro"]
        
        for model_name in model_names:
            try:
                print(f"[Polish] Trying model: {model_name}")
                model = genai.GenerativeModel(model_name)
                response = model.generate_content(prompt)
                print(f"[Polish] Success with {model_name}!")
                return response.text.strip()
            except Exception as e:
                print(f"[Polish] Model {model_name} failed: {str(e)[:100]}")
                continue
        
        raise ValueError("利用可能なGeminiモデルがありません")
        
    except Exception as e:
        print(f"[Polish] Error: {type(e).__name__}: {str(e)}")
        raise ValueError(f"Gemini APIエラー: {str(e)}. APIキーを確認してください。")


async def polish_transcript(text: str, gemini_key: Optional[str] = None) -> str:
    """Async wrapper for polishing"""
    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(executor, _polish_sync, text, gemini_key)
        return result
    except Exception as e:
        print(f"[Polish Async] Error: {str(e)}")
        raise

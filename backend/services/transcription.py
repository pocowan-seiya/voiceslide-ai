"""
VoiceSlide AI v3 - Audio Transcription Service
Transcription + Polishing with AI
"""

import os
import asyncio
from concurrent.futures import ThreadPoolExecutor
from openai import OpenAI
import google.generativeai as genai
from typing import Dict, Any, List

from config import OPENAI_API_KEY, GEMINI_API_KEY


# Initialize clients
openai_client = OpenAI(api_key=OPENAI_API_KEY)
genai.configure(api_key=GEMINI_API_KEY)

# Thread pool for blocking IO
executor = ThreadPoolExecutor(max_workers=2)


def _transcribe_sync(audio_path: str) -> Dict[str, Any]:
    """Synchronous transcription (runs in thread pool)"""
    with open(audio_path, "rb") as audio_file:
        response = openai_client.audio.transcriptions.create(
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
        "full_text": response.text
    }


async def transcribe_audio(audio_path: str) -> Dict[str, Any]:
    """Transcribe audio using Whisper API (async)"""
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(executor, _transcribe_sync, audio_path)
    return result


async def polish_transcript(transcript: str) -> str:
    """
    Polish and improve the transcript using AI
    - Fix typos and misheard words
    - Improve readability
    - Maintain original meaning
    """
    prompt = f"""以下の音声文字起こしをブラッシュアップしてください。

【ルール】
1. 誤字脱字を修正
2. 「えー」「あのー」などのフィラーを削除
3. 文章を読みやすく整形
4. 段落分けを適切に
5. 意味は変えない
6. 専門用語は保持

【文字起こし原文】
{transcript}

【ブラッシュアップ後】
"""
    
    try:
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"Gemini polish failed: {e}, falling back to GPT-4")
        
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a professional editor. Polish the transcript while maintaining its meaning."},
                {"role": "user", "content": prompt}
            ]
        )
        return response.choices[0].message.content.strip()


def generate_srt(segments: List[Dict[str, Any]]) -> str:
    """Generate SRT subtitle file content"""
    srt_lines = []
    
    for i, segment in enumerate(segments, 1):
        start_time = format_srt_time(segment["start"])
        end_time = format_srt_time(segment["end"])
        
        srt_lines.append(str(i))
        srt_lines.append(f"{start_time} --> {end_time}")
        srt_lines.append(segment["text"])
        srt_lines.append("")
    
    return "\n".join(srt_lines)


def format_srt_time(seconds: float) -> str:
    """Convert seconds to SRT time format"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

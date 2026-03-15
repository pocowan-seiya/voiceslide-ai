"""
VoiceSlide AI v3 - Audio Transcription Service
Transcription + Polishing with AI
"""

import os
import asyncio
import subprocess
import re
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from openai import OpenAI
import google.generativeai as genai
from typing import Dict, Any, List, Optional

from config import OPENAI_API_KEY, GEMINI_API_KEY, VIDEO_WIDTH, VIDEO_HEIGHT
from services.ai_utils import safe_gemini_generate


# Thread pool for blocking IO
executor = ThreadPoolExecutor(max_workers=2)


def trim_silence_from_audio(audio_path: str, output_path: str = None, threshold_db: int = -40, min_silence_duration: float = 0.5) -> str:
    """
    音声ファイルの冒頭と末尾の無音部分をカット
    
    Args:
        audio_path: 入力音声ファイルパス
        output_path: 出力パス（省略時は _trimmed を付加）
        threshold_db: 無音とみなすdB閾値（デフォルト: -40dB）
        min_silence_duration: 無音とみなす最小時間（秒）
    
    Returns:
        トリミング済みファイルのパス
    """
    if output_path is None:
        base, ext = os.path.splitext(audio_path)
        output_path = f"{base}_trimmed{ext}"
    
    try:
        # Step 1: 音声の長さを取得
        duration_cmd = [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", audio_path
        ]
        duration_result = subprocess.run(duration_cmd, capture_output=True, text=True)
        total_duration = float(duration_result.stdout.strip())
        print(f"[AudioTrim] Total duration: {total_duration:.1f}s")
        
        # Step 2: 無音検出
        silence_cmd = [
            "ffmpeg", "-i", audio_path, "-af",
            f"silencedetect=n={threshold_db}dB:d={min_silence_duration}",
            "-f", "null", "-"
        ]
        result = subprocess.run(silence_cmd, capture_output=True, text=True)
        stderr = result.stderr
        
        # 無音開始/終了を抽出
        silence_starts = re.findall(r"silence_start: ([\d.]+)", stderr)
        silence_ends = re.findall(r"silence_end: ([\d.]+)", stderr)
        
        # 冒頭の無音をカット: 最初の音声が始まる位置を見つける
        start_time = 0.0
        if silence_starts and float(silence_starts[0]) < 0.1:
            # 冒頭に無音がある場合、最初の無音終了位置から開始
            if silence_ends:
                start_time = float(silence_ends[0])
                print(f"[AudioTrim] Trimming {start_time:.1f}s from start")
        
        # 末尾の無音をカット: 最後の音声が終わる位置を見つける
        end_time = total_duration
        # 末尾の無音カット: 最後の無音が「音声の本当の終わり」の後にある場合のみ
        # 条件: 無音開始が末尾1秒以内 AND 無音が0.5秒以上続く
        if silence_starts and silence_ends and len(silence_starts) == len(silence_ends):
            last_silence_start = float(silence_starts[-1])
            last_silence_end = float(silence_ends[-1])
            last_silence_duration = last_silence_end - last_silence_start
            if last_silence_start > total_duration - 1.0 and last_silence_duration > 0.5:
                end_time = last_silence_start
                print(f"[AudioTrim] Trimming {total_duration - end_time:.1f}s silence from end")
        elif silence_starts:
            # silence_endが見つからない場合（末尾まで無音が続く）
            last_silence_start = float(silence_starts[-1])
            if last_silence_start > total_duration - 1.0:
                end_time = last_silence_start
                print(f"[AudioTrim] Trimming trailing silence from {last_silence_start:.1f}s")
        
        # 変更がない場合は元のファイルを返す
        if start_time < 0.1 and end_time >= total_duration - 0.1:
            print("[AudioTrim] No significant silence detected, using original")
            return audio_path
        
        # Step 3: トリミング実行
        trim_duration = end_time - start_time
        trim_cmd = [
            "ffmpeg", "-y", "-i", audio_path,
            "-ss", str(start_time),
            "-t", str(trim_duration),
            "-c", "copy",
            output_path
        ]
        subprocess.run(trim_cmd, capture_output=True, check=True)
        
        print(f"[AudioTrim] Trimmed: {start_time:.1f}s - {end_time:.1f}s ({trim_duration:.1f}s)")
        return output_path
        
    except Exception as e:
        print(f"[AudioTrim] Error: {e}, using original file")
        return audio_path



def get_openai_client(api_key: Optional[str] = None) -> OpenAI:
    """Get OpenAI client with provided or default API key"""
    key = api_key or OPENAI_API_KEY
    if not key:
        print("[OpenAI] No API key available in settings or request")
        raise ValueError("OpenAI API key is required. Please set it in settings.")
    return OpenAI(api_key=key)


def get_available_gemini_model(api_key: str) -> str:
    """Find an available Gemini model for content generation"""
    print(f"[Gemini] Configuring with key: {str(api_key)[:10]}...{str(api_key)[-4:]}")
    if not api_key:
        print("[Gemini] No API key provided to get_available_gemini_model")
        return "gemini-3-flash-preview"
    
    # Try to list available models
    try:
        genai.configure(api_key=api_key)
        available_models = []
        for model in genai.list_models():
            if 'generateContent' in str(model.supported_generation_methods):
                available_models.append(model.name)
        
        print(f"[Gemini] Available models: {available_models[:10]}")
        
        # Prefer gemini-3-flash-preview first for consistency
        preferred = ['gemini-3-flash-preview', 'gemini-2.0-flash', 'gemini-1.5-pro', 'gemini-pro']
        for pref in preferred:
            for avail in available_models:
                if pref in avail:
                    print(f"[Gemini] Selected model: {avail}")
                    return avail.replace('models/', '')
        
        # Return first available if no preference matches
        if available_models:
            model_name = available_models[0].replace('models/', '')
            print(f"[Gemini] Using first available: {model_name}")
            return model_name
            
    except Exception as e:
        print(f"[Gemini] Could not list models: {e}")
    
    # Fallback - try these in order
    return "gemini-pro"


def _transcribe_sync(audio_path: str, openai_key: Optional[str] = None) -> Dict[str, Any]:
    """Synchronous transcription (runs in thread pool)"""
    client = get_openai_client(openai_key)
    
    # Whisper API has a 25MB limit - compress if needed
    WHISPER_MAX_SIZE = 24 * 1024 * 1024  # 24MB (with safety margin)
    file_to_send = audio_path
    compressed_path = None
    
    file_size = os.path.getsize(audio_path)
    if file_size > WHISPER_MAX_SIZE:
        print(f"[Transcribe] Audio file too large ({file_size / 1024 / 1024:.1f}MB), compressing for Whisper...")
        compressed_path = audio_path.rsplit(".", 1)[0] + "_whisper.mp3"
        cmd = [
            "ffmpeg", "-y", "-i", audio_path,
            "-ac", "1",           # mono (transcription doesn't need stereo)
            "-ar", "16000",       # 16kHz is sufficient for speech
            "-b:a", "64k",        # low bitrate for smaller file
            compressed_path
        ]
        result = subprocess.run(cmd, capture_output=True, timeout=120)
        if result.returncode == 0 and os.path.exists(compressed_path):
            new_size = os.path.getsize(compressed_path)
            print(f"[Transcribe] Compressed: {file_size / 1024 / 1024:.1f}MB → {new_size / 1024 / 1024:.1f}MB")
            file_to_send = compressed_path
        else:
            print(f"[Transcribe] Compression failed, trying original file")
    
    try:
        with open(file_to_send, "rb") as audio_file:
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
    finally:
        # Cleanup compressed temp file
        if compressed_path and os.path.exists(compressed_path):
            try:
                os.remove(compressed_path)
            except:
                pass


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


async def polish_transcript(text: str, gemini_key: Optional[str] = None, original_script: Optional[str] = None, model_name: str = "gemini-3-flash-preview") -> str:
    """Polishes the transcript for readability and alignment with a reference script."""
    key = gemini_key or GEMINI_API_KEY
    
    def get_ts():
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if not key:
        print(f"[{get_ts()}] [Polish] No Gemini API key available")
        return text 

    try:
        # Use specified model or auto-detect
        if model_name != "gemini-3-flash-preview":
            actual_model = model_name
        else:
            actual_model = get_available_gemini_model(key)
        print(f"[{get_ts()}] [Polish] Starting with model: {actual_model}")
        
        reference_script = f"参考台本:\n{original_script}\n\n" if original_script else ""
    
        prompt = f"""以下の文字起こしテキストを読みやすく整形してください。
{reference_script}
要件:
- 「えー」「あー」などのフィラーを削除
- 文章を自然に区切る
- 明らかな言い間違いを修正
- 意味は変えない
- 敬体（です・ます調）を維持
- { "参考台本がある場合は、用語・漢字・固有名詞・表現スタイルなどを参考台本に寄せてください。" if original_script else "" }

元のテキスト:
{text}

整形後:"""
        
        # Use the robust shared utility
        result = await safe_gemini_generate(
            actual_model,
            prompt,
            key,
            config=None # Default config
        )
        
        print(f"[{get_ts()}] [Polish] Success!")
        return result

    except Exception as e:
        print(f"[{get_ts()}] [Polish] Error: {str(e)}")
        # Raise with a descriptive message for the UI
        raise ValueError(f"Gemini APIエラー: {str(e)}")

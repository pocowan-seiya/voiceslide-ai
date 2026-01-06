"""
VoiceSlide AI v3 - Video Composer
すべてのスライドを使用して動画を生成
"""

import os
import subprocess
from typing import List, Dict, Any, Optional

from config import VIDEO_WIDTH, VIDEO_HEIGHT


async def compose_video(
    audio_path: str,
    slide_images: List[str],
    timing_map: List[Dict[str, Any]],
    output_path: str
) -> str:
    """
    全スライドを使用して動画を生成
    
    重要: アップロードされたすべてのスライドを必ず使用する
    
    Args:
        audio_path: 音声ファイルパス
        slide_images: スライド画像パスのリスト
        timing_map: AI生成のタイミングマップ
        output_path: 出力動画パス
    
    Returns:
        生成された動画のパス
    """
    
    # 音声の長さを取得
    audio_duration = get_audio_duration(audio_path)
    
    # すべてのスライドを使用するタイミングを生成
    # timing_mapにないスライドも含める
    full_timing = ensure_all_slides_used(slide_images, timing_map, audio_duration)
    
    # 連結ファイルを作成
    concat_file = output_path.replace(".mp4", "_concat.txt")
    
    with open(concat_file, "w") as f:
        for timing in full_timing:
            slide_num = timing.get("slide_number", 1)
            duration = timing.get("duration", 0)
            
            # 対応する画像を取得
            if 0 < slide_num <= len(slide_images):
                image_path = slide_images[slide_num - 1]
            else:
                image_path = slide_images[-1] if slide_images else None
            
            if image_path and os.path.exists(image_path):
                f.write(f"file '{os.path.abspath(image_path)}'\n")
                f.write(f"duration {duration:.3f}\n")
        
        # FFmpegの要件: 最後の画像をもう一度追加
        if slide_images:
            f.write(f"file '{os.path.abspath(slide_images[-1])}'\n")
    
    # Step 1: 画像から動画を作成
    temp_video = output_path.replace(".mp4", "_temp.mp4")
    
    cmd_images = [
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", concat_file,
        "-vsync", "vfr",
        "-pix_fmt", "yuv420p",
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "23",
        temp_video
    ]
    
    result = subprocess.run(cmd_images, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"FFmpeg images error: {result.stderr}")
        raise Exception(f"動画生成エラー: {result.stderr[:200]}")
    
    # Step 2: 音声を追加
    cmd_final = [
        "ffmpeg", "-y",
        "-i", temp_video,
        "-i", audio_path,
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "128k",
        "-shortest",
        "-movflags", "+faststart",
        output_path
    ]
    
    result = subprocess.run(cmd_final, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"FFmpeg audio error: {result.stderr}")
        raise Exception(f"音声合成エラー: {result.stderr[:200]}")
    
    # 一時ファイルをクリーンアップ
    if os.path.exists(temp_video):
        os.remove(temp_video)
    if os.path.exists(concat_file):
        os.remove(concat_file)
    
    return output_path


def ensure_all_slides_used(
    slide_images: List[str],
    timing_map: List[Dict[str, Any]],
    audio_duration: float
) -> List[Dict[str, Any]]:
    """
    すべてのスライドが使用されることを保証
    
    - timing_mapにないスライドも追加
    - 時間を均等に再分配（必要な場合）
    """
    total_slides = len(slide_images)
    
    if total_slides == 0:
        return []
    
    # timing_mapに含まれるスライド番号を確認
    mapped_slides = set(t.get("slide_number", 0) for t in timing_map)
    
    # すべてのスライドがマッピングされている場合
    all_mapped = all(i+1 in mapped_slides for i in range(total_slides))
    
    if all_mapped and len(timing_map) == total_slides:
        # すでに全スライド使用 - 時間だけ調整
        return adjust_timing_durations(timing_map, audio_duration, total_slides)
    
    # 全スライドを使用するように新しいタイミングを生成
    print(f"📊 全{total_slides}枚のスライドを使用するようタイミングを再計算")
    
    # 音声の長さを全スライドで均等に分配
    duration_per_slide = audio_duration / total_slides
    
    # 最小時間 (5秒) を確保
    min_duration = 5.0
    if duration_per_slide < min_duration:
        duration_per_slide = min_duration
    
    full_timing = []
    current_time = 0.0
    
    for i in range(total_slides):
        slide_num = i + 1
        
        # 既存のタイミング情報を探す
        existing = next((t for t in timing_map if t.get("slide_number") == slide_num), None)
        
        if existing:
            # 既存のタイミングがある場合はその理由を保持
            duration = duration_per_slide
            reason = existing.get("match_reason") or existing.get("reason", "")
        else:
            # 新規追加
            duration = duration_per_slide
            reason = "全スライド使用のため追加"
        
        full_timing.append({
            "slide_number": slide_num,
            "start_time": current_time,
            "end_time": current_time + duration,
            "duration": duration,
            "match_reason": reason
        })
        
        current_time += duration
    
    # 最後のスライドの終了時刻を音声の長さに合わせる
    if full_timing:
        full_timing[-1]["end_time"] = audio_duration
        full_timing[-1]["duration"] = audio_duration - full_timing[-1]["start_time"]
    
    return full_timing


def adjust_timing_durations(
    timing_map: List[Dict[str, Any]],
    audio_duration: float,
    total_slides: int
) -> List[Dict[str, Any]]:
    """
    既存のタイミングマップの時間を調整
    """
    if not timing_map:
        return []
    
    # スライド番号でソート
    sorted_timing = sorted(timing_map, key=lambda x: x.get("slide_number", 0))
    
    # デバッグ: タイミング情報を表示
    print(f"[VideoComposer] Adjusting timing for {len(sorted_timing)} slides (audio: {audio_duration:.1f}s)")
    
    result = []
    for i, timing in enumerate(sorted_timing):
        start = timing.get("start_time", 0)
        end = timing.get("end_time", 0)
        duration = end - start
        
        # Safeguard: 最小1秒を確保
        if duration <= 0:
            # duration が 0 以下の場合、均等分配にフォールバック
            duration = audio_duration / len(sorted_timing)
            start = i * duration
            end = (i + 1) * duration
            print(f"  ⚠️ Slide {timing.get('slide_number', i+1)}: duration was {end-start:.1f}s, using fallback {duration:.1f}s")
        
        print(f"  📝 Slide {timing.get('slide_number', i+1)}: {start:.1f}s - {end:.1f}s ({duration:.1f}s)")
        
        result.append({
            "slide_number": timing.get("slide_number", i + 1),
            "start_time": start,
            "end_time": end,
            "duration": max(duration, 1.0),  # 最低1秒を保証
            "match_reason": timing.get("match_reason") or timing.get("reason", "")
        })
    
    return result


def get_audio_duration(audio_path: str) -> float:
    """FFprobeで音声の長さを取得"""
    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        audio_path
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    try:
        return float(result.stdout.strip())
    except ValueError:
        return 60.0  # デフォルト

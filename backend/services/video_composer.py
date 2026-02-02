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
    
    # デバッグ: 入力タイミングと最終タイミングを比較
    print(f"[VideoComposer] ===== TIMING DEBUG =====")
    print(f"[VideoComposer] Audio duration: {audio_duration:.1f}s")
    print(f"[VideoComposer] Slide images ({len(slide_images)} images):")
    for idx, img_path in enumerate(slide_images):
        print(f"  IMAGE[{idx}] = {os.path.basename(img_path)} (maps to slide_number {idx+1})")
    print(f"[VideoComposer] Input timing_map ({len(timing_map)} items):")
    for t in timing_map:  # すべて表示
        print(f"  IN:  Slide {t.get('slide_number')}: {t.get('start_time', 0):.1f}s - {t.get('end_time', 0):.1f}s")
    print(f"[VideoComposer] Final full_timing ({len(full_timing)} items):")
    for t in full_timing:  # すべて表示
        print(f"  OUT: Slide {t.get('slide_number')}: {t.get('start_time', 0):.1f}s - {t.get('end_time', 0):.1f}s, duration={t.get('duration', 0):.1f}s")
    print(f"[VideoComposer] ==========================")
    
    # 連結ファイルを作成（アトミック書き込み）
    concat_file = output_path.replace(".mp4", "_concat.txt")
    
    # Calculate total concat duration first
    total_concat_duration = sum(t.get("duration", 0) for t in full_timing)
    print(f"[Concat] Total duration from all slides: {total_concat_duration:.1f}s")
    
    # Build entire file content as a list first (then single write)
    concat_lines = []
    
    for timing in full_timing:
        slide_num = timing.get("slide_number", 1)
        duration = timing.get("duration", 0)
        
        # 対応する画像を取得
        if 0 < slide_num <= len(slide_images):
            image_path = slide_images[slide_num - 1]
        else:
            image_path = slide_images[-1] if slide_images else None
        
        if image_path and os.path.exists(image_path):
            abs_path = os.path.abspath(image_path)
            concat_lines.append(f"file '{abs_path}'")
            concat_lines.append(f"duration {duration:.3f}")
            print(f"[Concat] Slide {slide_num}: {os.path.basename(image_path)} duration {duration:.3f}s")
    
    # FFmpegの要件: 最後の画像をもう一度追加（duration無し）
    if slide_images:
        last_image = os.path.abspath(slide_images[-1])
        concat_lines.append(f"file '{last_image}'")
        print(f"[Concat] Final entry: {os.path.basename(slide_images[-1])} (no duration - just for last frame)")
    
    # Atomic write: 1回の書き込みで全コンテンツを出力
    concat_content = "\n".join(concat_lines) + "\n"
    with open(concat_file, "w") as f:
        f.write(concat_content)
        f.flush()  # Ensure all data is written
    
    # Debug: verify file contents
    print(f"[Concat] File contents ({len(concat_lines)} lines):")
    print(concat_content)
    
    # Step 1: 画像から動画を作成
    temp_video = output_path.replace(".mp4", "_temp.mp4")
    
    # Using explicit framerate to ensure proper slide switching
    cmd_images = [
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", concat_file,
        "-r", "30",  # Explicit output framerate for reliable switching
        # Ensure dimensions are even (required by H.264/libx264)
        # pad to nearest even dimensions using ceil
        "-vf", "fps=30,pad=ceil(iw/2)*2:ceil(ih/2)*2",
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
    
    重要: アウトラインからのタイムスタンプがある場合はそのまま使用
    """
    total_slides = len(slide_images)
    
    if total_slides == 0:
        return []
    
    # timing_mapに含まれるスライド番号を確認
    mapped_slides = set(t.get("slide_number", 0) for t in timing_map)
    
    # すべてのスライドがマッピングされている場合
    all_mapped = all(i+1 in mapped_slides for i in range(total_slides))
    
    if all_mapped and len(timing_map) == total_slides:
        # アウトラインからのタイムスタンプを使用（10秒遅延調整あり）
        # 話題が先に述べられ、10秒後にスライドが切り替わることでスムーズな視聴体験
        TRANSITION_DELAY = 10.0  # 秒
        print(f"[VideoComposer] ✓ Using outline timestamps with {TRANSITION_DELAY}s transition delay")
        
        sorted_timing = sorted(timing_map, key=lambda x: x.get("slide_number", 0))
        result = []
        
        for i, timing in enumerate(sorted_timing):
            original_start = timing.get("start_time", 0)
            original_end = timing.get("end_time", 0)
            
            if i == 0:
                # 最初のスライドは0秒から開始
                start = 0.0
            else:
                # 2枚目以降は元のstart_time + 10秒遅延
                start = min(original_start + TRANSITION_DELAY, audio_duration)
            
            if i == len(sorted_timing) - 1:
                # 最後のスライドは音声終了時刻で終了
                end = audio_duration
            else:
                # 次のスライドの開始時刻に合わせる
                next_original_start = sorted_timing[i + 1].get("start_time", 0)
                end = min(next_original_start + TRANSITION_DELAY, audio_duration)
            
            duration = end - start
            
            result.append({
                "slide_number": timing.get("slide_number", i + 1),
                "start_time": start,
                "end_time": end,
                "duration": max(duration, 0.5),  # 最低0.5秒を確保
                "match_reason": timing.get("match_reason", "アウトラインから取得") + f" (+{TRANSITION_DELAY}s delay)"
            })
            
            print(f"  Slide {i+1}: {original_start:.1f}s → {start:.1f}s, ends at {end:.1f}s, duration {duration:.1f}s")
        
        # Debug: verify total duration
        if result:
            total_slide_duration = sum(r.get("duration", 0) for r in result)
            last_slide_end = result[-1].get("end_time", 0)
            print(f"[VideoComposer] Total slide durations: {total_slide_duration:.1f}s, Last slide ends: {last_slide_end:.1f}s, Audio: {audio_duration:.1f}s")
        
        return result
    
    # 全スライドがマッピングされていない場合のみ均等分配
    print(f"📊 全{total_slides}枚のスライドを使用するようタイミングを再計算")
    
    duration_per_slide = audio_duration / total_slides
    min_duration = 5.0
    if duration_per_slide < min_duration:
        duration_per_slide = min_duration
    
    full_timing = []
    current_time = 0.0
    
    for i in range(total_slides):
        slide_num = i + 1
        duration = duration_per_slide
        
        full_timing.append({
            "slide_number": slide_num,
            "start_time": current_time,
            "end_time": current_time + duration,
            "duration": duration,
            "match_reason": "均等分配"
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
    
    IMPORTANT: タイミングの合計が音声より長い場合はスケーリングする
    """
    if not timing_map:
        return []
    
    # スライド番号でソート
    sorted_timing = sorted(timing_map, key=lambda x: x.get("slide_number", 0))
    
    # 計算: 現在のタイミングの合計時間
    last_timing = sorted_timing[-1]
    total_timing_duration = last_timing.get("end_time", 0)
    
    # デバッグ: タイミング情報を表示
    print(f"[VideoComposer] Adjusting timing for {len(sorted_timing)} slides (audio: {audio_duration:.1f}s, timing_total: {total_timing_duration:.1f}s)")
    
    # スケーリングが必要かどうかを判定
    needs_scaling = total_timing_duration > audio_duration + 1.0  # 1秒以上超過
    
    if needs_scaling:
        scale_factor = audio_duration / total_timing_duration
        print(f"  ⚠️ Timing exceeds audio duration! Scaling by factor {scale_factor:.3f}")
    else:
        scale_factor = 1.0
    
    result = []
    for i, timing in enumerate(sorted_timing):
        original_start = timing.get("start_time", 0)
        original_end = timing.get("end_time", 0)
        original_duration = original_end - original_start
        
        # スケーリング適用
        if needs_scaling:
            start = original_start * scale_factor
            end = original_end * scale_factor
            duration = end - start
        else:
            start = original_start
            end = original_end
            duration = original_duration
        
        # Safeguard: 最小1秒を確保
        if duration <= 0:
            # duration が 0 以下の場合、均等分配にフォールバック
            duration = audio_duration / len(sorted_timing)
            start = i * duration
            end = (i + 1) * duration
            print(f"  ⚠️ Slide {timing.get('slide_number', i+1)}: duration was <=0, using fallback {duration:.1f}s")
        
        print(f"  📝 Slide {timing.get('slide_number', i+1)}: {start:.1f}s - {end:.1f}s ({duration:.1f}s)")
        
        result.append({
            "slide_number": timing.get("slide_number", i + 1),
            "start_time": start,
            "end_time": end,
            "duration": max(duration, 1.0),  # 最低1秒を保証
            "match_reason": timing.get("match_reason") or timing.get("reason", "")
        })
    
    # 最後のスライドの終了時刻を音声の長さに正確に合わせる
    if result:
        last_slide = result[-1]
        if abs(last_slide["end_time"] - audio_duration) > 0.5:  # 0.5秒以上のズレ
            extra_duration = audio_duration - last_slide["end_time"]
            last_slide["end_time"] = audio_duration
            last_slide["duration"] = audio_duration - last_slide["start_time"]
            if extra_duration > 0:
                print(f"  🔧 Extended last slide to match audio end ({audio_duration:.1f}s, added {extra_duration:.1f}s)")
            else:
                print(f"  🔧 Trimmed last slide to match audio end ({audio_duration:.1f}s)")
    
    # 最終検証: 合計durationが音声長と一致するか確認
    total_duration = sum(t.get("duration", 0) for t in result)
    print(f"[VideoComposer] ✅ Final timing total: {total_duration:.1f}s (audio: {audio_duration:.1f}s, diff: {total_duration - audio_duration:.2f}s)")
    
    # 大きな差がある場合は警告
    if abs(total_duration - audio_duration) > 1.0:
        print(f"[VideoComposer] ⚠️ WARNING: Duration mismatch detected! Total slides: {total_duration:.1f}s vs Audio: {audio_duration:.1f}s")
    
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


# =============================================================================
# Opening/Ending Video Concatenation (OP/ED結合)
# =============================================================================

async def concatenate_with_intro_outro(
    main_video_path: str,
    output_path: str,
    intro_video_path: Optional[str] = None,
    outro_video_path: Optional[str] = None
) -> str:
    """
    メイン動画にオープニング・エンディング動画を結合
    
    Args:
        main_video_path: メインスライド動画のパス
        output_path: 出力動画のパス
        intro_video_path: オープニング動画（任意）
        outro_video_path: エンディング動画（任意）
    
    Returns:
        結合された動画のパス
    """
    import tempfile
    
    if not intro_video_path and not outro_video_path:
        # OP/EDがない場合はメイン動画をそのままコピー
        import shutil
        shutil.copy(main_video_path, output_path)
        print("[VideoComposer] No OP/ED provided, copying main video")
        return output_path
    
    # 結合する動画のリストを作成
    videos_to_concat = []
    
    if intro_video_path and os.path.exists(intro_video_path):
        videos_to_concat.append(intro_video_path)
        print(f"[VideoComposer] OP video: {intro_video_path}")
    
    videos_to_concat.append(main_video_path)
    print(f"[VideoComposer] Main video: {main_video_path}")
    
    if outro_video_path and os.path.exists(outro_video_path):
        videos_to_concat.append(outro_video_path)
        print(f"[VideoComposer] ED video: {outro_video_path}")
    
    if len(videos_to_concat) == 1:
        # 結合する動画が1つだけ（メインのみ）
        import shutil
        shutil.copy(main_video_path, output_path)
        return output_path
    
    # Step 1: すべての動画を同じフォーマットに変換（解像度・フレームレート統一）
    print(f"[VideoComposer] Normalizing {len(videos_to_concat)} videos...")
    
    normalized_videos = []
    temp_dir = os.path.dirname(output_path)
    
    for i, video_path in enumerate(videos_to_concat):
        normalized_path = os.path.join(temp_dir, f"_normalized_{i}.mp4")
        
        # 動画を1920x1080、30fps、同じコーデックに変換
        cmd_normalize = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-vf", f"scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:force_original_aspect_ratio=decrease,pad={VIDEO_WIDTH}:{VIDEO_HEIGHT}:(ow-iw)/2:(oh-ih)/2:black",
            "-r", "30",
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "23",
            "-c:a", "aac",
            "-b:a", "128k",
            "-ar", "44100",
            "-ac", "2",
            normalized_path
        ]
        
        result = subprocess.run(cmd_normalize, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"[VideoComposer] Normalize error for {video_path}: {result.stderr[:200]}")
            # エラーの場合はオリジナルを使用
            normalized_videos.append(video_path)
        else:
            normalized_videos.append(normalized_path)
            print(f"[VideoComposer] Normalized: {video_path} -> {normalized_path}")
    
    # Step 2: 連結ファイルを作成
    concat_file = os.path.join(temp_dir, "_concat_oped.txt")
    
    with open(concat_file, "w") as f:
        for video_path in normalized_videos:
            f.write(f"file '{os.path.abspath(video_path)}'\n")
    
    # Step 3: FFmpegで結合
    print(f"[VideoComposer] Concatenating {len(normalized_videos)} videos...")
    
    cmd_concat = [
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", concat_file,
        "-c", "copy",
        "-movflags", "+faststart",
        output_path
    ]
    
    result = subprocess.run(cmd_concat, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"[VideoComposer] Concat error: {result.stderr}")
        raise Exception(f"動画結合エラー: {result.stderr[:200]}")
    
    # クリーンアップ
    for normalized_path in normalized_videos:
        if "_normalized_" in normalized_path and os.path.exists(normalized_path):
            os.remove(normalized_path)
    if os.path.exists(concat_file):
        os.remove(concat_file)
    
    print(f"[VideoComposer] ✅ Concatenated video saved: {output_path}")
    return output_path


def get_video_info(video_path: str) -> Dict[str, Any]:
    """動画の情報を取得（解像度、長さなど）"""
    cmd = [
        "ffprobe",
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height,duration",
        "-of", "json",
        video_path
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    try:
        import json
        data = json.loads(result.stdout)
        stream = data.get("streams", [{}])[0]
        return {
            "width": stream.get("width", 1920),
            "height": stream.get("height", 1080),
            "duration": float(stream.get("duration", 0))
        }
    except:
        return {"width": 1920, "height": 1080, "duration": 0}


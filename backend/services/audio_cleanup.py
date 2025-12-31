"""
VoiceSlide AI v3 - オーディオクリーンアップサービス
無音区間とフィラーワードの除去
"""

import os
import subprocess
import tempfile
from typing import Dict, Any, List, Tuple
import json


# フィラーワードのパターン（日本語）
FILLER_PATTERNS = [
    "えっと", "えーっと", "えーと", "えー", "えっ",
    "あのー", "あの", "あー", "うーん", "うん",
    "まあ", "まぁ", "なんか", "そのー", "その",
    "ん？", "んー", "ええと", "ほら", "つまり",
]

# 無音と判定する閾値
SILENCE_THRESHOLD_DB = -40  # dB
SILENCE_MIN_DURATION = 0.5   # 秒


async def cleanup_audio(
    audio_path: str,
    segments: List[Dict[str, Any]],
    output_path: str = None
) -> Dict[str, Any]:
    """
    音声ファイルから無音区間とフィラーを除去
    
    Args:
        audio_path: 入力音声ファイルパス
        segments: Whisperからのセグメントデータ（タイムスタンプ付き）
        output_path: 出力ファイルパス（Noneの場合自動生成）
    
    Returns:
        クリーンアップ結果（新しい音声パス、変更点など）
    """
    if output_path is None:
        base, ext = os.path.splitext(audio_path)
        output_path = f"{base}_clean{ext}"
    
    # 1. 無音区間を検出
    silences = detect_silences(audio_path)
    
    # 2. フィラーワードを含むセグメントを特定
    filler_segments = detect_filler_segments(segments)
    
    # 3. カットすべき区間を決定（無音 + フィラー）
    cut_regions = merge_cut_regions(silences, filler_segments)
    
    # 4. カットしない区間（保持する区間）を計算
    audio_duration = get_audio_duration(audio_path)
    keep_regions = invert_regions(cut_regions, audio_duration)
    
    # 5. FFmpegで音声を再構成
    if keep_regions:
        cleaned_path = assemble_audio(audio_path, keep_regions, output_path)
    else:
        # カットするものがなければそのままコピー
        import shutil
        shutil.copy(audio_path, output_path)
        cleaned_path = output_path
    
    # 6. 新しいセグメント情報を更新
    new_segments = adjust_segment_timestamps(segments, cut_regions)
    
    return {
        "cleaned_audio_path": cleaned_path,
        "original_duration": audio_duration,
        "new_duration": get_audio_duration(cleaned_path),
        "removed_silences": len(silences),
        "removed_fillers": len(filler_segments),
        "total_removed_seconds": sum((r[1] - r[0]) for r in cut_regions),
        "new_segments": new_segments
    }


def detect_silences(audio_path: str) -> List[Tuple[float, float]]:
    """
    FFmpegのsilencedetectフィルタを使用して無音区間を検出
    """
    cmd = [
        "ffmpeg", "-i", audio_path, "-af",
        f"silencedetect=noise={SILENCE_THRESHOLD_DB}dB:d={SILENCE_MIN_DURATION}",
        "-f", "null", "-"
    ]
    
    try:
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            timeout=60
        )
        
        silences = []
        lines = result.stderr.split('\n')
        
        silence_start = None
        for line in lines:
            if "silence_start:" in line:
                try:
                    silence_start = float(line.split("silence_start:")[1].strip().split()[0])
                except:
                    pass
            elif "silence_end:" in line and silence_start is not None:
                try:
                    silence_end = float(line.split("silence_end:")[1].strip().split()[0])
                    # 長すぎる無音（3秒以上）は残す（意図的な間かもしれない）
                    duration = silence_end - silence_start
                    if duration < 3.0:
                        silences.append((silence_start, silence_end))
                    silence_start = None
                except:
                    pass
        
        return silences
    
    except Exception as e:
        print(f"Silence detection failed: {e}")
        return []


def detect_filler_segments(segments: List[Dict[str, Any]]) -> List[Tuple[float, float]]:
    """
    フィラーワードを含むセグメントの時間範囲を検出
    """
    filler_regions = []
    
    for segment in segments:
        text = segment.get("text", "").strip()
        start = segment.get("start", 0)
        end = segment.get("end", 0)
        
        # セグメント全体がフィラーかチェック
        text_lower = text.lower().strip()
        
        # 短いセグメント（2秒未満）でフィラーのみの場合はカット対象
        duration = end - start
        if duration < 2.0:
            is_filler_only = any(
                text_lower == filler or text_lower.startswith(filler + " ") or text_lower.endswith(" " + filler)
                for filler in FILLER_PATTERNS
            )
            if is_filler_only:
                filler_regions.append((start, end))
    
    return filler_regions


def merge_cut_regions(
    silences: List[Tuple[float, float]], 
    fillers: List[Tuple[float, float]]
) -> List[Tuple[float, float]]:
    """
    カット区間をマージして重複を解消
    """
    all_regions = silences + fillers
    if not all_regions:
        return []
    
    # ソート
    all_regions.sort(key=lambda x: x[0])
    
    # マージ
    merged = [all_regions[0]]
    for current in all_regions[1:]:
        last = merged[-1]
        if current[0] <= last[1] + 0.1:  # 0.1秒の余裕
            merged[-1] = (last[0], max(last[1], current[1]))
        else:
            merged.append(current)
    
    return merged


def invert_regions(
    cut_regions: List[Tuple[float, float]], 
    total_duration: float
) -> List[Tuple[float, float]]:
    """
    カット区間を反転して保持区間を取得
    """
    if not cut_regions:
        return [(0.0, total_duration)]
    
    keep_regions = []
    prev_end = 0.0
    
    for start, end in cut_regions:
        if start > prev_end:
            keep_regions.append((prev_end, start))
        prev_end = end
    
    if prev_end < total_duration:
        keep_regions.append((prev_end, total_duration))
    
    return keep_regions


def get_audio_duration(audio_path: str) -> float:
    """
    FFprobeで音声の長さを取得
    """
    cmd = [
        "ffprobe", "-v", "error", "-show_entries", 
        "format=duration", "-of", "json", audio_path
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        data = json.loads(result.stdout)
        return float(data["format"]["duration"])
    except Exception as e:
        print(f"Duration detection failed: {e}")
        return 0.0


def assemble_audio(
    audio_path: str, 
    keep_regions: List[Tuple[float, float]], 
    output_path: str
) -> str:
    """
    保持区間のみを結合して新しい音声ファイルを作成
    """
    # 一時ファイルリスト
    temp_files = []
    
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            # 各区間を抽出
            for i, (start, end) in enumerate(keep_regions):
                temp_file = os.path.join(temp_dir, f"part_{i:03d}.wav")
                
                cmd = [
                    "ffmpeg", "-y", "-i", audio_path,
                    "-ss", str(start), "-to", str(end),
                    "-c", "copy", temp_file
                ]
                subprocess.run(cmd, capture_output=True, timeout=60)
                temp_files.append(temp_file)
            
            # ファイルリストを作成
            list_file = os.path.join(temp_dir, "files.txt")
            with open(list_file, "w") as f:
                for temp_file in temp_files:
                    f.write(f"file '{temp_file}'\n")
            
            # 結合
            cmd = [
                "ffmpeg", "-y", "-f", "concat", "-safe", "0",
                "-i", list_file, "-c", "copy", output_path
            ]
            subprocess.run(cmd, capture_output=True, timeout=120)
        
        return output_path
    
    except Exception as e:
        print(f"Audio assembly failed: {e}")
        # 失敗時はオリジナルをコピー
        import shutil
        shutil.copy(audio_path, output_path)
        return output_path


def adjust_segment_timestamps(
    segments: List[Dict[str, Any]], 
    cut_regions: List[Tuple[float, float]]
) -> List[Dict[str, Any]]:
    """
    カットした時間分だけセグメントのタイムスタンプを調整
    """
    if not cut_regions:
        return segments
    
    def calculate_offset(time: float) -> float:
        """指定時刻までにカットされた合計時間を計算"""
        offset = 0.0
        for start, end in cut_regions:
            if start < time:
                if end <= time:
                    offset += (end - start)
                else:
                    offset += (time - start)
        return offset
    
    new_segments = []
    for seg in segments:
        start = seg.get("start", 0)
        end = seg.get("end", 0)
        
        # この区間がカット対象かチェック
        is_cut = any(
            cs <= start and ce >= end
            for cs, ce in cut_regions
        )
        
        if is_cut:
            continue  # カット対象は除外
        
        # タイムスタンプを調整
        new_start = start - calculate_offset(start)
        new_end = end - calculate_offset(end)
        
        new_segments.append({
            "id": seg.get("id", 0),
            "start": max(0, new_start),
            "end": max(new_start, new_end),
            "text": seg.get("text", "")
        })
    
    # IDを振り直し
    for i, seg in enumerate(new_segments):
        seg["id"] = i
    
    return new_segments

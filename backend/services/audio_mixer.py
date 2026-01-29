"""
Audio mixing service for combining speech with background music.
Uses pydub/ffmpeg for audio processing.
"""

import os
import subprocess
from typing import Optional
import tempfile


def mix_audio_with_bgm(
    speech_path: str,
    bgm_path: str,
    output_path: str,
    bgm_volume_reduction: float = -15,  # dB reduction for BGM
    fade_in_duration: float = 2.0,  # seconds
    fade_out_duration: float = 3.0,  # seconds
) -> str:
    """
    Mix speech audio with background music.
    
    Args:
        speech_path: Path to the main speech audio file
        bgm_path: Path to the background music file
        output_path: Path for the output mixed audio
        bgm_volume_reduction: How much to reduce BGM volume in dB (negative value)
        fade_in_duration: BGM fade-in duration in seconds
        fade_out_duration: BGM fade-out duration in seconds
    
    Returns:
        Path to the mixed audio file
    """
    # Get speech duration
    duration_cmd = [
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", speech_path
    ]
    duration_result = subprocess.run(duration_cmd, capture_output=True, text=True)
    speech_duration = float(duration_result.stdout.strip())
    
    print(f"[AudioMix] Speech duration: {speech_duration:.1f}s")
    print(f"[AudioMix] BGM volume reduction: {bgm_volume_reduction}dB")
    
    # Build complex filter:
    # 1. Loop BGM if needed and trim to speech length
    # 2. Apply volume reduction to BGM
    # 3. Apply fade in/out to BGM
    # 4. Mix with speech
    
    filter_complex = (
        f"[1:a]aloop=loop=-1:size=2e+09,atrim=0:{speech_duration},"
        f"volume={bgm_volume_reduction}dB,"
        f"afade=t=in:st=0:d={fade_in_duration},"
        f"afade=t=out:st={speech_duration - fade_out_duration}:d={fade_out_duration}[bgm];"
        f"[0:a][bgm]amix=inputs=2:duration=first:dropout_transition=2[out]"
    )
    
    # Run ffmpeg
    cmd = [
        "ffmpeg", "-y",
        "-i", speech_path,
        "-i", bgm_path,
        "-filter_complex", filter_complex,
        "-map", "[out]",
        "-c:a", "libmp3lame", "-q:a", "2",
        output_path
    ]
    
    print(f"[AudioMix] Running ffmpeg...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"[AudioMix] Error: {result.stderr}")
        raise Exception(f"FFmpeg error: {result.stderr}")
    
    print(f"[AudioMix] Success! Output: {output_path}")
    return output_path


def adjust_bgm_volume(
    mixed_path: str,
    original_speech_path: str,
    bgm_path: str,
    output_path: str,
    new_bgm_volume_reduction: float,
    fade_in_duration: float = 2.0,
    fade_out_duration: float = 3.0,
) -> str:
    """
    Re-mix audio with adjusted BGM volume.
    
    Args:
        mixed_path: Path to the previously mixed file (not used, we remix from scratch)
        original_speech_path: Path to the original speech file
        bgm_path: Path to the original BGM file
        output_path: Path for the new output
        new_bgm_volume_reduction: New BGM volume reduction in dB
        fade_in_duration: BGM fade-in duration
        fade_out_duration: BGM fade-out duration
    
    Returns:
        Path to the newly mixed audio file
    """
    return mix_audio_with_bgm(
        speech_path=original_speech_path,
        bgm_path=bgm_path,
        output_path=output_path,
        bgm_volume_reduction=new_bgm_volume_reduction,
        fade_in_duration=fade_in_duration,
        fade_out_duration=fade_out_duration,
    )


def parse_volume_feedback(feedback: str) -> float:
    """
    Parse user feedback text to determine volume adjustment.
    
    Args:
        feedback: User feedback like "BGMをもう少し小さく" or "もっと大きく"
    
    Returns:
        Suggested BGM volume reduction in dB (negative = quieter)
    """
    feedback_lower = feedback.lower()
    
    # Default: -15dB
    # Quieter requests
    if any(word in feedback_lower for word in ["小さく", "静かに", "もっと下げ", "聞こえにくい", "もう少し小さく"]):
        if "もっと" in feedback_lower or "かなり" in feedback_lower:
            return -25  # Much quieter
        return -20  # Quieter
    
    # Louder requests
    if any(word in feedback_lower for word in ["大きく", "上げ", "もっと聞こえ"]):
        if "もっと" in feedback_lower or "かなり" in feedback_lower:
            return -8  # Much louder
        return -12  # Louder
    
    # Subtle adjustments
    if "少し小さく" in feedback_lower or "ちょっと小さく" in feedback_lower:
        return -18
    if "少し大きく" in feedback_lower or "ちょっと大きく" in feedback_lower:
        return -13
    
    # Default if no match
    return -15

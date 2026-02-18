"""
VoiceSlide AI v3 - Hybrid Workflow Pipeline
10-step process with external slide creation and AI auto-sync
"""

import os
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime

from services.transcription import transcribe_audio, polish_transcript
from services.outline_generator import generate_outline, polish_outline
from services.slide_analyzer import analyze_slides
from services.slide_mapper import map_slides_to_audio
from services.video_composer import compose_video
from config import OUTPUT_DIR, UPLOAD_DIR


class HybridPipeline:
    """
    VoiceSlide AI v3 Pipeline
    
    Steps:
    1. Audio upload
    2. Transcription
    3. Transcription polish
    4. Outline generation
    5. Outline brush-up
    6. Output outline to user
    7. (User creates slides externally)
    8. Upload slides (PDF/images)
    9. AI auto-mapping
    10. Video generation
    """
    
    def __init__(self, job_id: str, audio_path: str):
        self.job_id = job_id
        self.audio_path = audio_path
        self.job_dir = os.path.join(OUTPUT_DIR, job_id)
        os.makedirs(self.job_dir, exist_ok=True)
        
        # State
        self.raw_transcript = None
        self.polished_transcript = None
        self.segments = None
        self.srt_path = None
        self.raw_outline = None
        self.polished_outline = None
        self.slide_images = []
        self.slide_contents = []
        self.timing_map = []
        self.video_path = None
        self.final_video = None  # Main generated video
        self.final_video_with_oped = None  # Video with OP/ED
    
    def _sync_segments_with_transcript(self, edited_transcript: str) -> List[Dict[str, Any]]:
        """
        Sync edited transcript with segment timestamps.
        Updates segment text while preserving timing information.
        """
        if not self.segments:
            return []
        
        # Split edited transcript into lines/sentences
        edited_lines = [line.strip() for line in edited_transcript.split('\n') if line.strip()]
        edited_text_full = ' '.join(edited_lines)
        
        # Create new segments with updated text
        synced_segments = []
        for seg in self.segments:
            synced_segments.append({
                "id": seg.get("id", 0),
                "start": seg.get("start", 0),
                "end": seg.get("end", 0),
                "text": seg.get("text", "")  # Keep original, outline uses full transcript
            })
        
        # Store the edited transcript for later use
        self.polished_transcript = edited_transcript
        print(f"[Pipeline] Synced {len(synced_segments)} segments with edited transcript")
        
        return synced_segments
    
    # Step 2: Transcription
    async def step_transcribe(self, openai_key: Optional[str] = None) -> Dict[str, Any]:
        """Transcribe audio to text with timestamps"""
        result = await transcribe_audio(self.audio_path, openai_key=openai_key)
        
        self.raw_transcript = result["full_text"]
        self.segments = result["segments"]
        self.srt_path = result["srt_path"]
        
        return {
            "step": 2,
            "status": "completed",
            "transcript": self.raw_transcript,
            "segments": self.segments
        }
    
    # Step 3: Transcription Polish
    async def step_polish_transcript(
        self, 
        edited_transcript: Optional[str] = None, 
        gemini_key: Optional[str] = None,
        original_script: Optional[str] = None
    ) -> Dict[str, Any]:
        """Polish and improve the transcript"""
        text_to_polish = edited_transcript or self.raw_transcript
        
        self.polished_transcript = await polish_transcript(
            text_to_polish, 
            gemini_key=gemini_key,
            original_script=original_script
        )
        
        return {
            "step": 3,
            "status": "completed",
            "polished_transcript": self.polished_transcript
        }
    
    # Step 4: Outline Generation
    async def step_generate_outline(
        self, 
        edited_transcript: Optional[str] = None, 
        gemini_key: Optional[str] = None,
        slide_count_mode: str = "auto",
        custom_slide_count: int = 10
    ) -> Dict[str, Any]:
        """Generate slide outline from transcript"""
        transcript = edited_transcript or self.polished_transcript or self.raw_transcript
        
        # Sync segments with edited transcript if provided
        segments_to_use = self.segments
        if edited_transcript and self.segments:
            segments_to_use = self._sync_segments_with_transcript(edited_transcript)
        
        # Get actual audio duration from file (not from segments)
        actual_audio_duration = None
        if self.audio_path:
            from services.video_composer import get_audio_duration
            actual_audio_duration = get_audio_duration(self.audio_path)
            print(f"[Pipeline] Actual audio duration from file: {actual_audio_duration:.1f}s")
        
        self.raw_outline = await generate_outline(
            transcript, 
            segments_to_use, 
            gemini_key=gemini_key,
            slide_count_mode=slide_count_mode,
            custom_slide_count=custom_slide_count,
            audio_duration=actual_audio_duration
        )
        
        return {
            "step": 4,
            "status": "completed",
            "outline": self.raw_outline
        }
    
    # Step 5: Outline Brush-up
    async def step_polish_outline(self, edited_outline: Optional[Dict] = None) -> Dict[str, Any]:
        """Brush up and improve the outline"""
        outline_to_polish = edited_outline or self.raw_outline
        
        self.polished_outline = await polish_outline(outline_to_polish)
        
        return {
            "step": 5,
            "status": "completed",
            "polished_outline": self.polished_outline
        }
    
    # Step 6: Output Outline (handled by frontend - just return data)
    def step_output_outline(self) -> Dict[str, Any]:
        """Return outline for user to copy/download"""
        return {
            "step": 6,
            "status": "completed",
            "outline": self.polished_outline or self.raw_outline,
            "transcript": self.polished_transcript or self.raw_transcript,
            "message": "アウトラインをコピーして、外部ツールでスライドを作成してください"
        }
    
    # Step 8: Upload Slides
    async def step_upload_slides(self, file_path: str, file_type: str) -> Dict[str, Any]:
        """
        Analyze uploaded slides (PDF or images)
        Returns slide contents for mapping
        """
        result = await analyze_slides(file_path, file_type, self.job_id)
        
        self.slide_images = result["images"]
        self.slide_contents = result["contents"]
        
        return {
            "step": 8,
            "status": "completed",
            "slide_count": len(self.slide_images),
            "slide_previews": [f"/outputs/{self.job_id}_slides/{os.path.basename(p)}" for p in self.slide_images],
            "slide_contents": self.slide_contents
        }
    
    # Step 9: AI Auto-Mapping (or use outline timestamps if available)
    async def step_map_slides(self) -> Dict[str, Any]:
        """Map slides to audio - uses outline timestamps if available, otherwise AI mapping"""
        
        # First, try to use timing from the outline (already determined during outline generation)
        outline = self.polished_outline or self.raw_outline
        
        if outline and "slides" in outline:
            slides_with_timing = outline.get("slides", [])
            
            # Check if outline has timestamp info
            if slides_with_timing and "timestamp_start" in slides_with_timing[0]:
                print("[Mapping] Using timestamps from outline (accurate to transcript)")
                
                self.timing_map = []
                for slide in slides_with_timing:
                    self.timing_map.append({
                        "slide_number": slide.get("number", len(self.timing_map) + 1),
                        "start_time": slide.get("timestamp_start", 0),
                        "end_time": slide.get("timestamp_end", 0),
                        "matched_segments": slide.get("segment_ids", []),
                        "match_reason": slide.get("timing_reason", "アウトラインから取得")
                    })
                
                return {
                    "step": 9,
                    "status": "completed",
                    "timing_map": self.timing_map,
                    "source": "outline_timestamps"
                }
        
        # Fallback: AI mapping (for uploaded slides without outline)
        print("[Mapping] Using AI mapping (outline has no timestamps)")
        self.timing_map = await map_slides_to_audio(
            slides=self.slide_contents,
            segments=self.segments,
            total_duration=self.segments[-1]["end"] if self.segments else 60.0
        )
        
        return {
            "step": 9,
            "status": "completed",
            "timing_map": self.timing_map,
            "source": "ai_mapping"
        }
    
    # Step 10: Video Generation
    async def step_generate_video(self, edited_timing: Optional[List] = None, audio_override: Optional[str] = None) -> Dict[str, Any]:
        """Generate final video with mapped timing
        
        Args:
            edited_timing: Optional custom timing map
            audio_override: Optional path to audio file (e.g., BGM-mixed audio)
        """
        timing = edited_timing or self.timing_map
        
        output_path = os.path.join(OUTPUT_DIR, f"{self.job_id}.mp4")
        
        # Use audio_override if provided, otherwise use original audio_path
        audio_path = audio_override or self.audio_path
        
        self.video_path = await compose_video(
            audio_path=audio_path,
            slide_images=self.slide_images,
            timing_map=timing,
            output_path=output_path,
            user_edited=edited_timing is not None
        )
        
        return {
            "step": 10,
            "status": "completed",
            "video_path": self.video_path,
            "video_url": f"/video/{self.job_id}"
        }


# Pipeline instances storage
pipelines: Dict[str, HybridPipeline] = {}


def get_or_create_pipeline(job_id: str, audio_path: Optional[str] = None) -> HybridPipeline:
    """Get existing pipeline or create new one"""
    if job_id not in pipelines:
        if audio_path is None:
            # Try to recover audio path from filesystem
            # Check for common audio file patterns for this job
            import os
            import glob
            from config import UPLOAD_DIR
            
            possible_patterns = [
                f"{UPLOAD_DIR}/{job_id}.*",          # Original upload
                f"{UPLOAD_DIR}/{job_id}_clean.*",    # Cleaned audio
                f"{UPLOAD_DIR}/{job_id}_clean_mixed.*",  # Mixed with BGM
                f"{UPLOAD_DIR}/{job_id}_trimmed.*",  # Trimmed audio
            ]
            
            recovered_path = None
            for pattern in possible_patterns:
                matches = glob.glob(pattern)
                if matches:
                    # Prefer mixed > clean > original
                    for match in matches:
                        if "_mixed" in match:
                            recovered_path = match
                            break
                        elif "_clean" in match and recovered_path is None:
                            recovered_path = match
                        elif recovered_path is None:
                            recovered_path = match
                    if recovered_path:
                        break
            
            if recovered_path and os.path.exists(recovered_path):
                print(f"[Pipeline] Recovered audio path for {job_id}: {recovered_path}")
                audio_path = recovered_path
            else:
                raise ValueError(f"audio_path required for new pipeline - no audio found for job {job_id}")
        
        pipelines[job_id] = HybridPipeline(job_id, audio_path)
    return pipelines[job_id]


def delete_pipeline(job_id: str):
    """Remove pipeline from storage"""
    if job_id in pipelines:
        del pipelines[job_id]

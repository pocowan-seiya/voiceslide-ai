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
    async def step_polish_transcript(self, edited_transcript: Optional[str] = None) -> Dict[str, Any]:
        """Polish and improve the transcript"""
        text_to_polish = edited_transcript or self.raw_transcript
        
        self.polished_transcript = await polish_transcript(text_to_polish)
        
        return {
            "step": 3,
            "status": "completed",
            "polished_transcript": self.polished_transcript
        }
    
    # Step 4: Outline Generation
    async def step_generate_outline(self, edited_transcript: Optional[str] = None) -> Dict[str, Any]:
        """Generate slide outline from transcript"""
        transcript = edited_transcript or self.polished_transcript or self.raw_transcript
        
        self.raw_outline = await generate_outline(transcript, self.segments)
        
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
    
    # Step 9: AI Auto-Mapping
    async def step_map_slides(self) -> Dict[str, Any]:
        """AI maps slides to audio segments"""
        self.timing_map = await map_slides_to_audio(
            slides=self.slide_contents,
            segments=self.segments,
            total_duration=self.segments[-1]["end"] if self.segments else 60.0
        )
        
        return {
            "step": 9,
            "status": "completed",
            "timing_map": self.timing_map
        }
    
    # Step 10: Video Generation
    async def step_generate_video(self, edited_timing: Optional[List] = None) -> Dict[str, Any]:
        """Generate final video with mapped timing"""
        timing = edited_timing or self.timing_map
        
        output_path = os.path.join(OUTPUT_DIR, f"{self.job_id}.mp4")
        
        self.video_path = await compose_video(
            audio_path=self.audio_path,
            slide_images=self.slide_images,
            timing_map=timing,
            output_path=output_path
        )
        
        return {
            "step": 10,
            "status": "completed",
            "video_path": self.video_path,
            "video_url": f"/outputs/{self.job_id}.mp4"
        }


# Pipeline instances storage
pipelines: Dict[str, HybridPipeline] = {}


def get_or_create_pipeline(job_id: str, audio_path: Optional[str] = None) -> HybridPipeline:
    """Get existing pipeline or create new one"""
    if job_id not in pipelines:
        if audio_path is None:
            raise ValueError("audio_path required for new pipeline")
        pipelines[job_id] = HybridPipeline(job_id, audio_path)
    return pipelines[job_id]


def delete_pipeline(job_id: str):
    """Remove pipeline from storage"""
    if job_id in pipelines:
        del pipelines[job_id]

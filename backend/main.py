"""
VoiceSlide AI v3 - FastAPI Backend
10-Step Hybrid Workflow with AI Auto-Sync
"""

from fastapi import FastAPI, UploadFile, File, HTTPException, Form, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uuid
import os
import shutil
from datetime import datetime
from typing import Dict, Any, List, Optional
import hashlib
import secrets

from config import UPLOAD_DIR, OUTPUT_DIR, ACCESS_PASSWORD
from services.pipeline import get_or_create_pipeline, delete_pipeline, pipelines
from services.outline_generator import format_outline_for_export


app = FastAPI(
    title="VoiceSlide AI v3",
    description="Hybrid Workflow - AI Auto-Sync Audio & Slides",
    version="3.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Directories
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Static files
app.mount("/outputs", StaticFiles(directory=OUTPUT_DIR), name="outputs")

# Job storage
jobs: Dict[str, Dict[str, Any]] = {}

# Session tokens (simple in-memory storage)
valid_tokens: Dict[str, datetime] = {}

# API keys storage (per-job)
api_keys: Dict[str, Dict[str, str]] = {}


# Request models
class TranscriptUpdate(BaseModel):
    transcript: str

class OutlineUpdate(BaseModel):
    outline: Dict[str, Any]

class TimingUpdate(BaseModel):
    timing_map: List[Dict[str, Any]]

class AuthRequest(BaseModel):
    password: str

class APIKeysRequest(BaseModel):
    openai_api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None


# ========== Authentication ==========

@app.post("/api/auth/login")
async def login(auth: AuthRequest):
    """Simple password authentication"""
    # If no password is set, allow access (local development)
    if not ACCESS_PASSWORD:
        token = secrets.token_urlsafe(32)
        valid_tokens[token] = datetime.now()
        return {"success": True, "token": token, "message": "認証不要（ローカル開発モード）"}
    
    # Check password
    if auth.password == ACCESS_PASSWORD:
        token = secrets.token_urlsafe(32)
        valid_tokens[token] = datetime.now()
        return {"success": True, "token": token}
    
    raise HTTPException(401, "パスワードが正しくありません")


@app.get("/api/auth/check")
async def check_auth(authorization: Optional[str] = Header(None)):
    """Check if user is authenticated"""
    # If no password is set, allow access
    if not ACCESS_PASSWORD:
        return {"authenticated": True, "password_required": False}
    
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
        if token in valid_tokens:
            return {"authenticated": True, "password_required": True}
    
    return {"authenticated": False, "password_required": True}


# ========== API Keys Management ==========

@app.post("/api/keys/{job_id}")
async def set_api_keys(job_id: str, keys: APIKeysRequest):
    """Store API keys for a job"""
    api_keys[job_id] = {
        "openai": keys.openai_api_key or "",
        "gemini": keys.gemini_api_key or ""
    }
    return {"success": True, "message": "APIキーを設定しました"}


def get_api_keys(job_id: str) -> Dict[str, str]:
    """Get API keys for a job"""
    return api_keys.get(job_id, {"openai": "", "gemini": ""})


@app.get("/")
async def root():
    return {"service": "VoiceSlide AI v3", "workflow": "10-step hybrid"}


# ========== STEP 1: Upload Audio ==========

@app.post("/api/upload-audio")
async def upload_audio(file: UploadFile = File(...)):
    """Step 1: Upload audio file"""
    allowed_ext = [".mp3", ".wav", ".m4a"]
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in allowed_ext:
        raise HTTPException(400, f"対応形式: MP3, WAV, M4A")
    
    job_id = str(uuid.uuid4())
    audio_path = os.path.join(UPLOAD_DIR, f"{job_id}{ext}")
    
    with open(audio_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    
    # Initialize job
    jobs[job_id] = {
        "id": job_id,
        "step": 1,
        "status": "uploaded",
        "audio_path": audio_path,
        "created_at": datetime.now().isoformat()
    }
    
    # Initialize pipeline
    get_or_create_pipeline(job_id, audio_path)
    
    return {"job_id": job_id, "message": "音声アップロード完了"}


# ========== STEP 2: Transcribe ==========

@app.post("/api/transcribe/{job_id}")
async def transcribe(
    job_id: str, 
    cleanup_audio: bool = True,
    x_openai_key: Optional[str] = Header(None),
    x_gemini_key: Optional[str] = Header(None)
):
    """Step 2: Transcribe audio (with optional cleanup)"""
    pipeline = get_or_create_pipeline(job_id)
    
    # Store API keys in job for later use
    if x_openai_key:
        jobs[job_id]["openai_key"] = x_openai_key
    if x_gemini_key:
        jobs[job_id]["gemini_key"] = x_gemini_key
    
    jobs[job_id]["step"] = 2
    jobs[job_id]["status"] = "processing"
    
    # Pass API key to transcription
    result = await pipeline.step_transcribe(openai_key=x_openai_key)
    
    # オプション: 無音・フィラーを除去
    cleanup_result = None
    if cleanup_audio:
        try:
            from services.audio_cleanup import cleanup_audio as do_cleanup
            audio_path = jobs[job_id].get("audio_path")
            if audio_path:
                cleanup_result = await do_cleanup(
                    audio_path,
                    result["segments"]
                )
                # クリーンアップ後の音声パスを更新
                if cleanup_result and cleanup_result.get("cleaned_audio_path"):
                    jobs[job_id]["audio_path"] = cleanup_result["cleaned_audio_path"]
                    jobs[job_id]["original_audio_path"] = audio_path
                    # セグメントも更新
                    if cleanup_result.get("new_segments"):
                        result["segments"] = cleanup_result["new_segments"]
                        pipeline.segments = cleanup_result["new_segments"]
        except Exception as e:
            print(f"Audio cleanup skipped: {e}")
            cleanup_result = {"error": str(e)}
    
    jobs[job_id]["status"] = "completed"
    jobs[job_id]["transcript"] = result["transcript"]
    
    response = {
        "job_id": job_id,
        "step": 2,
        "transcript": result["transcript"],
        "segments": result["segments"]
    }
    
    if cleanup_result:
        response["cleanup"] = {
            "removed_silences": cleanup_result.get("removed_silences", 0),
            "removed_fillers": cleanup_result.get("removed_fillers", 0),
            "total_removed_seconds": cleanup_result.get("total_removed_seconds", 0),
            "original_duration": cleanup_result.get("original_duration", 0),
            "new_duration": cleanup_result.get("new_duration", 0)
        }
    
    return response


# ========== STEP 3: Polish Transcript ==========

@app.post("/api/polish-transcript/{job_id}")
async def polish_transcript(
    job_id: str, 
    update: Optional[TranscriptUpdate] = None,
    x_gemini_key: Optional[str] = Header(None)
):
    """Step 3: Polish and improve transcript"""
    pipeline = get_or_create_pipeline(job_id)
    
    # Store API key for this job
    if x_gemini_key:
        jobs[job_id]["gemini_key"] = x_gemini_key
    
    jobs[job_id]["step"] = 3
    jobs[job_id]["status"] = "processing"
    
    edited = update.transcript if update else None
    result = await pipeline.step_polish_transcript(edited, gemini_key=x_gemini_key)
    
    jobs[job_id]["status"] = "completed"
    jobs[job_id]["polished_transcript"] = result["polished_transcript"]
    
    return {
        "job_id": job_id,
        "step": 3,
        "polished_transcript": result["polished_transcript"]
    }


# ========== STEP 4: Generate Outline ==========

@app.post("/api/generate-outline/{job_id}")
async def generate_outline(
    job_id: str, 
    update: Optional[TranscriptUpdate] = None,
    x_gemini_key: Optional[str] = Header(None)
):
    """Step 4: Generate slide outline"""
    pipeline = get_or_create_pipeline(job_id)
    
    # Store API key for this job
    if x_gemini_key:
        jobs[job_id]["gemini_key"] = x_gemini_key
    
    jobs[job_id]["step"] = 4
    jobs[job_id]["status"] = "processing"
    
    edited = update.transcript if update else None
    result = await pipeline.step_generate_outline(edited, gemini_key=x_gemini_key)
    
    jobs[job_id]["status"] = "completed"
    jobs[job_id]["outline"] = result["outline"]
    
    return {
        "job_id": job_id,
        "step": 4,
        "outline": result["outline"]
    }


# ========== STEP 5: Polish Outline ==========

@app.post("/api/polish-outline/{job_id}")
async def polish_outline(job_id: str, update: Optional[OutlineUpdate] = None):
    """Step 5: Brush up outline"""
    pipeline = get_or_create_pipeline(job_id)
    
    jobs[job_id]["step"] = 5
    jobs[job_id]["status"] = "processing"
    
    edited = update.outline if update else None
    result = await pipeline.step_polish_outline(edited)
    
    jobs[job_id]["status"] = "completed"
    jobs[job_id]["polished_outline"] = result["polished_outline"]
    
    return {
        "job_id": job_id,
        "step": 5,
        "polished_outline": result["polished_outline"]
    }


# ========== STEP 6: Export Outline ==========

@app.get("/api/export-outline/{job_id}")
async def export_outline(job_id: str, format: str = "json"):
    """Step 6: Export outline for user"""
    pipeline = get_or_create_pipeline(job_id)
    result = pipeline.step_output_outline()
    
    if format == "markdown":
        return {
            "job_id": job_id,
            "step": 6,
            "format": "markdown",
            "content": format_outline_for_export(result["outline"])
        }
    
    return {
        "job_id": job_id,
        "step": 6,
        "format": "json",
        "outline": result["outline"],
        "transcript": result["transcript"]
    }


# ========== STEP 7 (Full AI): Generate Slides ==========

@app.post("/api/generate-slides/{job_id}")
async def generate_slides_endpoint(
    job_id: str,
    x_gemini_key: Optional[str] = Header(None)
):
    """Step 7 (Full AI Mode): AI generates unique custom slides from outline"""
    pipeline = get_or_create_pipeline(job_id)
    
    jobs[job_id]["step"] = 7
    jobs[job_id]["status"] = "generating_slides"
    
    # アウトラインを取得
    outline = pipeline.polished_outline or pipeline.raw_outline
    if not outline:
        raise HTTPException(400, "アウトラインが見つかりません。先にアウトラインを生成してください。")
    
    try:
        from services.ai_slide_generator import generate_all_custom_slides
        
        slides = outline.get("slides", [])
        total_slides = len(slides)
        
        print(f"[Generate Slides] Generating {total_slides} unique custom slides with AI...")
        
        # Generate completely custom HTML/CSS for each slide using AI Design Architect
        image_paths = await generate_all_custom_slides(
            slides=slides,
            job_id=job_id,
            gemini_key=x_gemini_key,
            outline=outline  # Pass full outline for design strategy
        )
        
        # パイプラインに保存
        pipeline.slide_images = image_paths
        pipeline.slide_contents = slides
        
        # スライドプレビューURLを生成
        slide_previews = [f"/outputs/{job_id}_slides/{os.path.basename(p)}" for p in image_paths]
        
        jobs[job_id]["status"] = "completed"
        jobs[job_id]["slide_count"] = len(image_paths)
        
        return {
            "job_id": job_id,
            "step": 7,
            "slide_count": len(image_paths),
            "slide_previews": slide_previews,
            "message": "AIがユニークなスライドデザインを自動生成しました"
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        jobs[job_id]["status"] = "error"
        raise HTTPException(500, f"スライド生成エラー: {str(e)}")


# ========== STEP 8: Upload Slides ==========

@app.post("/api/upload-slides/{job_id}")
async def upload_slides(
    job_id: str,
    file: Optional[UploadFile] = File(None),
    files: Optional[List[UploadFile]] = File(None),
    file_type: str = Form("pdf")
):
    """Step 8: Upload slides (PDF or multiple images)"""
    pipeline = get_or_create_pipeline(job_id)
    
    # Create slides directory for this job
    slides_dir = os.path.join(UPLOAD_DIR, f"{job_id}_slides_input")
    os.makedirs(slides_dir, exist_ok=True)
    
    if file_type == "pdf" and file:
        # Single PDF file
        ext = os.path.splitext(file.filename)[1].lower()
        slides_path = os.path.join(UPLOAD_DIR, f"{job_id}_slides{ext}")
        
        with open(slides_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
    else:
        # Multiple image files
        file_list = files if files else ([file] if file else [])
        slides_path = slides_dir
        
        for i, upload_file in enumerate(file_list):
            if upload_file and upload_file.filename:
                ext = os.path.splitext(upload_file.filename)[1].lower()
                file_path = os.path.join(slides_dir, f"slide_{i+1:03d}{ext}")
                
                with open(file_path, "wb") as f:
                    shutil.copyfileobj(upload_file.file, f)
    
    jobs[job_id]["step"] = 8
    jobs[job_id]["status"] = "processing"
    
    result = await pipeline.step_upload_slides(slides_path, file_type)
    
    jobs[job_id]["status"] = "completed"
    jobs[job_id]["slide_count"] = result["slide_count"]
    
    return {
        "job_id": job_id,
        "step": 8,
        "slide_count": result["slide_count"],
        "slide_previews": result["slide_previews"],
        "slide_contents": result["slide_contents"]
    }


# ========== STEP 9: AI Auto-Mapping ==========

@app.post("/api/map-slides/{job_id}")
async def map_slides(job_id: str):
    """Step 9: AI automatically maps slides to audio"""
    pipeline = get_or_create_pipeline(job_id)
    
    jobs[job_id]["step"] = 9
    jobs[job_id]["status"] = "processing"
    
    result = await pipeline.step_map_slides()
    
    jobs[job_id]["status"] = "completed"
    jobs[job_id]["timing_map"] = result["timing_map"]
    
    return {
        "job_id": job_id,
        "step": 9,
        "timing_map": result["timing_map"]
    }


# ========== STEP 10: Generate Video ==========

@app.post("/api/generate-video/{job_id}")
async def generate_video(job_id: str, update: Optional[TimingUpdate] = None):
    """Step 10: Generate final video"""
    pipeline = get_or_create_pipeline(job_id)
    
    jobs[job_id]["step"] = 10
    jobs[job_id]["status"] = "processing"
    
    edited = update.timing_map if update else None
    result = await pipeline.step_generate_video(edited)
    
    jobs[job_id]["status"] = "completed"
    jobs[job_id]["video_url"] = result["video_url"]
    
    return {
        "job_id": job_id,
        "step": 10,
        "status": "completed",
        "video_url": result["video_url"]
    }


# ========== Utilities ==========

@app.get("/api/status/{job_id}")
async def get_status(job_id: str):
    """Get job status"""
    if job_id not in jobs:
        raise HTTPException(404, "Job not found")
    return jobs[job_id]


@app.get("/api/download/{job_id}")
async def download_video(job_id: str):
    """Download generated video"""
    if job_id not in jobs:
        raise HTTPException(404, "Job not found")
    
    video_path = os.path.join(OUTPUT_DIR, f"{job_id}.mp4")
    if not os.path.exists(video_path):
        raise HTTPException(404, "Video not found")
    
    return FileResponse(
        video_path,
        media_type="video/mp4",
        filename=f"voiceslide_{job_id}.mp4"
    )


@app.delete("/api/job/{job_id}")
async def delete_job(job_id: str):
    """Delete job and cleanup files"""
    if job_id in jobs:
        del jobs[job_id]
    delete_pipeline(job_id)
    
    # Cleanup files
    for f in [
        os.path.join(UPLOAD_DIR, f"{job_id}*"),
        os.path.join(OUTPUT_DIR, f"{job_id}*")
    ]:
        import glob
        for path in glob.glob(f):
            if os.path.isdir(path):
                shutil.rmtree(path)
            else:
                os.remove(path)
    
    return {"message": "Deleted"}


if __name__ == "__main__":
    import uvicorn
    from config import HOST, PORT
    print(f"Starting backend on {HOST}:{PORT}")
    uvicorn.run(app, host=HOST, port=PORT)

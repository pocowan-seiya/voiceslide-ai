"""
VoiceSlide AI v3 - FastAPI Backend
10-Step Hybrid Workflow with AI Auto-Sync
"""

from fastapi import FastAPI, UploadFile, File, HTTPException, Form, Header, BackgroundTasks
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

# Slide generation progress storage
slide_progress: Dict[str, Dict[str, Any]] = {}

# Slide history for undo (job_id -> slide_number -> list of previous versions)
slide_history: Dict[str, Dict[int, List[Dict[str, Any]]]] = {}

# Request models
class TranscriptUpdate(BaseModel):
    transcript: Optional[str] = None
    slide_count_mode: Optional[str] = "auto"  # auto, fewer, more, custom
    custom_slide_count: Optional[int] = 10

class OutlineUpdate(BaseModel):
    outline: Dict[str, Any]

class TimingUpdate(BaseModel):
    timing_map: List[Dict[str, Any]]

class AuthRequest(BaseModel):
    password: str

class APIKeysRequest(BaseModel):
    openai_api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None


# ========== Color Themes ==========

@app.get("/api/color-themes")
async def get_color_themes():
    """Get available color theme presets"""
    from services.ai_slide_generator import COLOR_THEMES
    themes = []
    for key, value in COLOR_THEMES.items():
        themes.append({
            "id": key,
            "name": value["name"],
            "description": value["description"],
            "colors": {
                "primary": value["primary"],
                "secondary": value["secondary"],
                "accent": value["accent"],
                "background": value["background_start"]
            }
        })
    return {"themes": themes}


# ========== Progress Tracking ==========

@app.get("/api/progress/{job_id}")
async def get_progress(job_id: str):
    """Get slide generation progress"""
    if job_id not in slide_progress:
        return {"current": 0, "total": 0, "percent": 0, "message": "開始待ち..."}
    
    progress = slide_progress[job_id]
    current = progress.get("current", 0)
    total = progress.get("total", 1)
    percent = int((current / total) * 100) if total > 0 else 0
    message = progress.get("message", "処理中...")
    
    return {
        "current": current,
        "total": total,
        "percent": percent,
        "message": message
    }


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


# ========== Slide Images Upload ==========

@app.post("/api/upload-slide-images/{job_id}")
async def upload_slide_images(
    job_id: str,
    files: List[UploadFile] = File(...)
):
    """Upload images to be used in slide generation"""
    from config import OUTPUT_DIR
    
    images_dir = os.path.join(OUTPUT_DIR, f"{job_id}_user_images")
    os.makedirs(images_dir, exist_ok=True)
    
    saved_paths = []
    allowed_ext = [".jpg", ".jpeg", ".png", ".gif", ".webp"]
    
    for i, file in enumerate(files):
        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in allowed_ext:
            continue
        
        filename = f"user_image_{i+1}{ext}"
        filepath = os.path.join(images_dir, filename)
        
        with open(filepath, "wb") as f:
            shutil.copyfileobj(file.file, f)
        
        saved_paths.append(filepath)
    
    # Store in pipeline
    pipeline = get_or_create_pipeline(job_id)
    pipeline.user_images = saved_paths
    
    print(f"[Upload Images] Saved {len(saved_paths)} images for job {job_id}")
    
    return {
        "success": True,
        "image_count": len(saved_paths),
        "paths": [f"/outputs/{job_id}_user_images/{os.path.basename(p)}" for p in saved_paths]
    }


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
    silence_threshold: float = 0.5,  # seconds
    x_openai_key: Optional[str] = Header(None),
    x_gemini_key: Optional[str] = Header(None)
):
    """Step 2: Transcribe audio (with optional cleanup)"""
    audio_path = jobs.get(job_id, {}).get("audio_path")
    pipeline = get_or_create_pipeline(job_id, audio_path)
    
    # Store API keys in job for later use
    if x_openai_key:
        jobs[job_id]["openai_key"] = x_openai_key
    if x_gemini_key:
        jobs[job_id]["gemini_key"] = x_gemini_key
    
    jobs[job_id]["step"] = 2
    jobs[job_id]["status"] = "processing"
    
    # Step 2a: 冒頭と末尾の無音をトリミング
    try:
        from services.transcription import trim_silence_from_audio
        original_audio_path = jobs[job_id].get("audio_path")
        if original_audio_path:
            trimmed_path = trim_silence_from_audio(original_audio_path)
            if trimmed_path != original_audio_path:
                jobs[job_id]["audio_path"] = trimmed_path
                jobs[job_id]["original_audio_path"] = original_audio_path
                pipeline.audio_path = trimmed_path
                print(f"[Transcribe] Audio trimmed: {original_audio_path} → {trimmed_path}")
    except Exception as e:
        print(f"[Transcribe] Silence trim failed: {e}")
    
    # Step 2b: Pass API key to transcription
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
                    result["segments"],
                    silence_threshold=silence_threshold  # Pass user-specified threshold
                )
                # クリーンアップ後の音声パスを更新
                if cleanup_result and cleanup_result.get("cleaned_audio_path"):
                    jobs[job_id]["audio_path"] = cleanup_result["cleaned_audio_path"]
                    jobs[job_id]["original_audio_path"] = audio_path
                    # ⚠️ パイプラインの音声パスも更新（動画生成で使用）
                    pipeline.audio_path = cleanup_result["cleaned_audio_path"]
                    print(f"[Cleanup] Updated audio path: {audio_path} → {cleanup_result['cleaned_audio_path']}")
                    print(f"[Cleanup] Duration: {cleanup_result.get('original_duration', 0):.1f}s → {cleanup_result.get('new_duration', 0):.1f}s")
                    # セグメントも更新（調整済みタイムスタンプ）
                    if cleanup_result.get("new_segments"):
                        result["segments"] = cleanup_result["new_segments"]
                        pipeline.segments = cleanup_result["new_segments"]
                        print(f"[Cleanup] Updated segments with adjusted timestamps")
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
    slide_count_mode = update.slide_count_mode if update else "auto"
    custom_slide_count = update.custom_slide_count if update else 10
    
    result = await pipeline.step_generate_outline(
        edited, 
        gemini_key=x_gemini_key,
        slide_count_mode=slide_count_mode,
        custom_slide_count=custom_slide_count
    )
    
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
    x_gemini_key: Optional[str] = Header(None),
    x_color_theme: Optional[str] = Header(None),  # Color theme: cosmic, warm, elegant, nature, ocean, mono
    x_font_style: Optional[str] = Header(None)    # Font style: gothic, mincho, pop, handwritten
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
        
        # Initialize progress tracking
        slide_progress[job_id] = {
            "current": 0,
            "total": total_slides + 1,  # +1 for design strategy step
            "message": "デザイン戦略を生成中..."
        }
        
        print(f"[Generate Slides] Generating {total_slides} unique custom slides with AI...")
        if x_color_theme:
            print(f"[Generate Slides] Using color theme: {x_color_theme}")
        
        # Progress update callback
        def update_progress(current: int, total: int, message: str):
            slide_progress[job_id] = {
                "current": current,
                "total": total,
                "message": message
            }
        
        # Generate completely custom HTML/CSS for each slide using AI Design Architect
        image_paths = await generate_all_custom_slides(
            slides=slides,
            job_id=job_id,
            gemini_key=x_gemini_key,
            outline=outline,
            color_theme=x_color_theme,
            font_style=x_font_style,
            progress_callback=update_progress
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


class BatchGenerateRequest(BaseModel):
    start_slide: int = 1  # 1-indexed
    batch_size: int = 5   # Increased with upgraded Railway memory
    design_preference: Optional[str] = None  # User design requirements
    text_density: str = "standard"  # "simple" (title+headline) or "standard" (full)


@app.post("/api/generate-slides-batch/{job_id}")
async def generate_slides_batch_endpoint(
    job_id: str,
    request: BatchGenerateRequest,
    background_tasks: BackgroundTasks,
    x_gemini_key: Optional[str] = Header(None),
    x_color_theme: Optional[str] = Header(None),
    x_font_style: Optional[str] = Header(None)
):
    """Batch slide generation: runs in background to avoid timeout"""
    pipeline = get_or_create_pipeline(job_id)
    
    # アウトラインを取得
    outline = pipeline.polished_outline or pipeline.raw_outline
    if not outline:
        raise HTTPException(400, "アウトラインが見つかりません。先にアウトラインを生成してください。")
    
    slides = outline.get("slides", [])
    total_slides = len(slides)
    
    start = request.start_slide
    end = min(start + request.batch_size - 1, total_slides)
    
    print(f"[Batch Generate] Starting background task for slides {start}-{end} of {total_slides}")
    
    # Initialize progress
    slide_progress[job_id] = {
        "current": 0,
        "total": end - start + 2,
        "message": f"バッチ生成開始 ({start}-{end})...",
        "status": "processing",
        "batch_start": start,
        "batch_end": end,
        "total_slides": total_slides
    }
    
    # Define background task
    async def generate_batch_async():
        try:
            from services.ai_slide_generator import generate_all_custom_slides
            
            def update_progress(current: int, total: int, message: str):
                slide_progress[job_id] = {
                    **slide_progress.get(job_id, {}),
                    "current": current,
                    "total": total,
                    "message": message,
                    "status": "processing"
                }
            
            # Generate batch of slides
            image_paths = await generate_all_custom_slides(
                slides=slides,
                job_id=job_id,
                gemini_key=x_gemini_key,
                outline=outline,
                color_theme=x_color_theme,
                font_style=x_font_style,
                user_images=getattr(pipeline, 'user_images', None),
                design_preference=request.design_preference,
                text_density=request.text_density,
                progress_callback=update_progress,
                start_slide=start,
                end_slide=end
            )
            
            # パイプラインに保存
            pipeline.slide_images = image_paths
            pipeline.slide_contents = slides
            
            # スライドプレビューURLを生成
            slide_previews = [f"/outputs/{job_id}_slides/{os.path.basename(p)}" for p in image_paths]
            
            # Calculate next batch
            next_start = end + 1
            is_complete = next_start > total_slides
            
            # Update progress with completion
            slide_progress[job_id] = {
                **slide_progress.get(job_id, {}),
                "status": "complete",
                "message": f"バッチ完了 ({start}-{end})",
                "slide_previews": slide_previews,
                "batch_start": start,
                "batch_end": end,
                "next_start": None if is_complete else next_start,
                "is_complete": is_complete,
                "total_slides": total_slides
            }
            print(f"[Batch Generate] Completed slides {start}-{end}")
            
        except Exception as e:
            print(f"[Batch Generate] Error: {e}")
            import traceback
            traceback.print_exc()
            slide_progress[job_id] = {
                **slide_progress.get(job_id, {}),
                "status": "error",
                "message": f"エラー: {str(e)}"
            }
    
    # Run in background using asyncio
    import asyncio
    asyncio.create_task(generate_batch_async())
    
    # Return immediately
    return {
        "job_id": job_id,
        "status": "processing",
        "message": f"バッチ生成開始 ({start}-{end})",
        "batch_start": start,
        "batch_end": end,
        "total_slides": total_slides
    }


@app.get("/api/batch-status/{job_id}")
async def get_batch_status(job_id: str):
    """Get batch generation status for polling"""
    progress = slide_progress.get(job_id, {})
    return {
        "job_id": job_id,
        "status": progress.get("status", "unknown"),
        "message": progress.get("message", ""),
        "current": progress.get("current", 0),
        "total": progress.get("total", 0),
        "slide_previews": progress.get("slide_previews", []),
        "batch_start": progress.get("batch_start"),
        "batch_end": progress.get("batch_end"),
        "next_start": progress.get("next_start"),
        "is_complete": progress.get("is_complete", False),
        "total_slides": progress.get("total_slides", 0)
    }



# ========== Slide Feedback & Editing ==========

class SlideFeedbackRequest(BaseModel):
    slide_number: int
    feedback: str
    feedback_type: str = "general"  # copy, layout, visual, general, add_image
    image_base64: Optional[str] = None  # Base64 encoded image data
    image_filename: Optional[str] = None  # Original filename


@app.post("/api/slides/{job_id}/feedback")
async def slide_feedback_endpoint(
    job_id: str,
    request: SlideFeedbackRequest,
    x_gemini_key: Optional[str] = Header(None)
):
    """Regenerate a slide based on user feedback"""
    if job_id not in jobs:
        raise HTTPException(404, "Job not found")
    
    try:
        from services.ai_slide_generator import regenerate_slide_with_feedback, load_html_contents
        
        # Save current slide to history before regeneration
        slide_num = request.slide_number
        if job_id not in slide_history:
            slide_history[job_id] = {}
        if slide_num not in slide_history[job_id]:
            slide_history[job_id][slide_num] = []
        
        # Get current HTML and image path
        html_contents = load_html_contents(job_id)
        slides_dir = os.path.join(OUTPUT_DIR, f"{job_id}_slides")
        current_image_path = os.path.join(slides_dir, f"slide_{slide_num:03d}.png")
        
        if slide_num <= len(html_contents):
            current_html = html_contents[slide_num - 1]
            # Save backup of current image
            backup_image_path = os.path.join(slides_dir, f"slide_{slide_num:03d}_v{len(slide_history[job_id][slide_num])}.png")
            if os.path.exists(current_image_path):
                shutil.copy(current_image_path, backup_image_path)
            
            slide_history[job_id][slide_num].append({
                "html": current_html,
                "image_path": backup_image_path,
                "timestamp": datetime.now().isoformat()
            })
            print(f"[History] Saved slide {slide_num} version {len(slide_history[job_id][slide_num])}")
        
        result = await regenerate_slide_with_feedback(
            job_id=job_id,
            slide_number=request.slide_number,
            feedback=request.feedback,
            feedback_type=request.feedback_type,
            gemini_key=x_gemini_key,
            image_base64=request.image_base64,
            image_filename=request.image_filename
        )
        
        if not result["success"]:
            raise HTTPException(500, result.get("error", "Regeneration failed"))
        
        # Add cache buster to URL and history count
        import time
        result["preview_url"] = f"{result['preview_url']}?t={int(time.time())}"
        result["history_count"] = len(slide_history.get(job_id, {}).get(slide_num, []))
        
        return {
            "job_id": job_id,
            **result,
            "message": f"スライド {request.slide_number} を更新しました",
            "can_undo": result["history_count"] > 0
        }
        
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(500, f"フィードバック処理エラー: {str(e)}")


@app.post("/api/slides/{job_id}/undo/{slide_number}")
async def undo_slide_endpoint(
    job_id: str,
    slide_number: int
):
    """Undo last slide change - restore previous version"""
    if job_id not in jobs:
        raise HTTPException(404, "Job not found")
    
    if job_id not in slide_history or slide_number not in slide_history[job_id]:
        raise HTTPException(400, "履歴がありません")
    
    history_list = slide_history[job_id][slide_number]
    if not history_list:
        raise HTTPException(400, "履歴がありません")
    
    try:
        from services.ai_slide_generator import load_html_contents, save_html_contents
        
        # Get last version from history
        prev_version = history_list.pop()
        prev_html = prev_version["html"]
        prev_image_path = prev_version["image_path"]
        
        # Restore HTML contents
        html_contents = load_html_contents(job_id)
        if slide_number <= len(html_contents):
            html_contents[slide_number - 1] = prev_html
            save_html_contents(job_id, html_contents)
        
        # Restore image
        slides_dir = os.path.join(OUTPUT_DIR, f"{job_id}_slides")
        current_image_path = os.path.join(slides_dir, f"slide_{slide_number:03d}.png")
        
        if os.path.exists(prev_image_path):
            shutil.copy(prev_image_path, current_image_path)
            os.remove(prev_image_path)  # Clean up backup
        
        # Add cache buster
        import time
        preview_url = f"/outputs/{job_id}_slides/slide_{slide_number:03d}.png?t={int(time.time())}"
        
        print(f"[History] Restored slide {slide_number} to version {len(history_list)}")
        
        return {
            "job_id": job_id,
            "slide_number": slide_number,
            "preview_url": preview_url,
            "can_undo": len(history_list) > 0,
            "history_count": len(history_list),
            "message": f"スライド {slide_number} を前のバージョンに戻しました"
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(500, f"元に戻す処理でエラー: {str(e)}")

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
    
    # If no timing provided and no timing_map exists, generate it from outline
    if not update and not pipeline.timing_map:
        print("[Video] Generating timing map from outline...")
        await pipeline.step_map_slides()
    
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


# =============================================================================
# Opening/Ending Video Concatenation API
# =============================================================================

@app.post("/api/concat-video/{job_id}")
async def concat_video_endpoint(
    job_id: str,
    intro_video: Optional[UploadFile] = File(None),
    outro_video: Optional[UploadFile] = File(None)
):
    """
    メイン動画にオープニング・エンディング動画を結合
    
    - intro_video: オープニング動画（任意）
    - outro_video: エンディング動画（任意）
    """
    from services.video_composer import concatenate_with_intro_outro
    
    # Find the main video file by pattern
    main_video_path = None
    potential_paths = [
        os.path.join(OUTPUT_DIR, f"{job_id}.mp4"),
        os.path.join(OUTPUT_DIR, f"{job_id}_video.mp4"),
        os.path.join(OUTPUT_DIR, f"{job_id}_final.mp4"),
    ]
    
    for path in potential_paths:
        if os.path.exists(path):
            main_video_path = path
            break
    
    if not main_video_path:
        raise HTTPException(400, f"動画ファイルが見つかりません。先に動画を生成してください。")
    
    # OP/ED動画を保存
    intro_path = None
    outro_path = None
    
    if intro_video and intro_video.filename:
        intro_path = os.path.join(UPLOAD_DIR, f"{job_id}_intro_{intro_video.filename}")
        with open(intro_path, "wb") as f:
            content = await intro_video.read()
            f.write(content)
        print(f"[API] Saved intro video: {intro_path}")
    
    if outro_video and outro_video.filename:
        outro_path = os.path.join(UPLOAD_DIR, f"{job_id}_outro_{outro_video.filename}")
        with open(outro_path, "wb") as f:
            content = await outro_video.read()
            f.write(content)
        print(f"[API] Saved outro video: {outro_path}")
    
    # 出力パス
    output_path = os.path.join(OUTPUT_DIR, f"{job_id}_final_with_oped.mp4")
    
    try:
        # 結合実行
        result_path = await concatenate_with_intro_outro(
            main_video_path=main_video_path,
            output_path=output_path,
            intro_video_path=intro_path,
            outro_video_path=outro_path
        )
        
        print(f"[API] Concatenated video saved to: {result_path}")
        
        return {
            "status": "success",
            "message": "OP/ED動画を結合しました",
            "video_url": f"/outputs/{os.path.basename(result_path)}",
            "has_intro": intro_path is not None,
            "has_outro": outro_path is not None
        }
        
    except Exception as e:
        raise HTTPException(500, f"動画結合エラー: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    from config import HOST, PORT
    print(f"Starting backend on {HOST}:{PORT}")
    uvicorn.run(app, host=HOST, port=PORT)


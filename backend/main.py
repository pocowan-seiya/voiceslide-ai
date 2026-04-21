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
import asyncio

from config import UPLOAD_DIR, OUTPUT_DIR, ASPECT_RATIO_PRESETS, get_video_dimensions, ACCESS_PASSWORD
from services.pipeline import get_or_create_pipeline, delete_pipeline, pipelines
from services.outline_generator import format_outline_for_export


app = FastAPI(
    title="VoiceSlide AI v3",
    description="Hybrid Workflow - AI Auto-Sync Audio & Slides",
    version="3.0.0"
)

# CORS - Include Railway URLs
cors_origins = [
    "http://localhost:3000",
    "http://localhost:8000",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:8000",
    "https://voiceslide-ai-development.up.railway.app",
    "https://voiceslide-ai-production.up.railway.app",
    "https://backend-api-development-58ec.up.railway.app",
    "https://backend-api-production-391c.up.railway.app",
    "https://voiceslide.movie",
]
# Add custom origins from environment variable
extra_origins = os.environ.get("CORS_ORIGINS", "")
if extra_origins:
    cors_origins.extend([o.strip() for o in extra_origins.split(",") if o.strip()])

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Directories
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Static files (for non-video assets like slide images)
app.mount("/outputs", StaticFiles(directory=OUTPUT_DIR), name="outputs")


@app.get("/video/{job_id}")
async def serve_video(job_id: str):
    """動画ファイルをキャッシュ無効化ヘッダー付きで配信
    
    StaticFilesのデフォルトではETag/Last-Modifiedにより304が返され、
    ブラウザが古いキャッシュ動画を再生してしまう問題を解決
    """
    from fastapi.responses import FileResponse
    
    video_path = os.path.join(OUTPUT_DIR, f"{job_id}.mp4")
    if not os.path.exists(video_path):
        raise HTTPException(404, "Video not found")
    
    return FileResponse(
        video_path,
        media_type="video/mp4",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
        }
    )

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

# Job timestamps for cleanup tracking
job_timestamps: Dict[str, datetime] = {}

# Cleanup configuration
CLEANUP_INTERVAL_HOURS = 1  # Run cleanup every hour
JOB_MAX_AGE_HOURS = 24  # Delete jobs older than 24 hours

async def cleanup_old_jobs():
    """Remove old job data from memory and disk to prevent resource accumulation"""
    import time
    while True:
        try:
            now = datetime.now()
            jobs_to_delete = []
            
            # Find old jobs
            for job_id, created_at in list(job_timestamps.items()):
                age_hours = (now - created_at).total_seconds() / 3600
                if age_hours > JOB_MAX_AGE_HOURS:
                    jobs_to_delete.append(job_id)
            
            # Delete old jobs
            # NOTE: this loop is the ONLY place that frees per-job state. If a
            # cache lives keyed by job_id, it MUST be popped here or memory
            # leaks linearly with usage (eventually OOMing the process).
            for job_id in jobs_to_delete:
                print(f"[Cleanup] Removing old job: {job_id}")

                # Clean memory caches in main.py
                jobs.pop(job_id, None)
                api_keys.pop(job_id, None)
                slide_progress.pop(job_id, None)
                slide_history.pop(job_id, None)
                job_timestamps.pop(job_id, None)

                # Clean memory caches in services/ai_slide_generator.py
                # (Previously these were never freed → memory leak. Discovered
                # during the Phase-1 architectural audit.)
                try:
                    from services.ai_slide_generator import (
                        _slide_data_cache,
                        _used_layouts_cache,
                        release_slide_data_lock,
                    )
                    _slide_data_cache.pop(job_id, None)
                    _used_layouts_cache.pop(job_id, None)
                    # The per-job mutex itself also leaks otherwise — Lock
                    # objects don't get GC'd because they live in the
                    # _slide_data_locks dict. Phase 2.1 added them.
                    release_slide_data_lock(job_id)
                except Exception as e:
                    print(f"[Cleanup] Failed to pop ai_slide_generator caches for {job_id}: {e}")

                # Clean pipeline (use specific Exception type so failures are visible
                # — bare `except: pass` was hiding genuine errors)
                try:
                    delete_pipeline(job_id)
                except Exception as e:
                    print(f"[Cleanup] delete_pipeline failed for {job_id}: {e}")

                # Clean disk (output files)
                for suffix in ["_slides", "_user_images", "_reference"]:
                    dir_path = os.path.join(OUTPUT_DIR, f"{job_id}{suffix}")
                    if os.path.exists(dir_path):
                        try:
                            shutil.rmtree(dir_path)
                            print(f"[Cleanup] Deleted directory: {dir_path}")
                        except Exception as e:
                            print(f"[Cleanup] Failed to delete {dir_path}: {e}")

                # Clean uploads
                upload_dir = os.path.join(UPLOAD_DIR, job_id)
                if os.path.exists(upload_dir):
                    try:
                        shutil.rmtree(upload_dir)
                    except Exception as e:
                        print(f"[Cleanup] Failed to delete uploads {upload_dir}: {e}")
            
            if jobs_to_delete:
                print(f"[Cleanup] Removed {len(jobs_to_delete)} old jobs")

        except Exception as e:
            print(f"[Cleanup] Error: {e}")

        # --- 48h video cache sweep (independent of in-memory job cleanup) ---
        # Wrapped in its own try block so a Supabase outage never kills the
        # parent loop. Orphan Storage objects are recoverable — we prioritize
        # clearing DB columns so resumes don't attempt stale paths.
        try:
            import httpx as _httpx
            from datetime import timezone as _tz, timedelta as _td
            from services.supabase_storage import (
                is_configured, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, delete_video,
            )
            if is_configured():
                cutoff = (datetime.now(_tz.utc) - _td(hours=48)).isoformat()
                async with _httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.get(
                        f"{SUPABASE_URL}/rest/v1/projects",
                        params={
                            "select": "id,video_storage_path,video_cached_at",
                            "video_cached_at": f"lt.{cutoff}",
                            "video_storage_path": "not.is.null",
                        },
                        headers={
                            "apikey": SUPABASE_SERVICE_ROLE_KEY,
                            "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
                        },
                    )
                    expired = resp.json() if resp.status_code == 200 else []
                    if expired:
                        print(f"[Cleanup] Found {len(expired)} expired video cache entries")
                    for row in expired:
                        pid = row.get("id")
                        path = row.get("video_storage_path")
                        if not pid or not path:
                            continue
                        try:
                            await delete_video(path)
                        except Exception as e:
                            print(f"[Cleanup] Storage delete failed for {pid}: {e}")
                            # still clear columns below so future restores don't point at it
                        try:
                            await client.patch(
                                f"{SUPABASE_URL}/rest/v1/projects",
                                params={"id": f"eq.{pid}"},
                                headers={
                                    "apikey": SUPABASE_SERVICE_ROLE_KEY,
                                    "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
                                    "Content-Type": "application/json",
                                    "Prefer": "return=minimal",
                                },
                                json={"video_storage_path": None, "video_cached_at": None},
                            )
                        except Exception as e:
                            print(f"[Cleanup] PATCH clear failed for {pid}: {e}")
        except Exception as e:
            print(f"[Cleanup] video cache sweep error (non-fatal): {e}")

        # Wait before next cleanup cycle
        await asyncio.sleep(CLEANUP_INTERVAL_HOURS * 3600)

@app.on_event("startup")
async def startup_event():
    """Start background cleanup task on server startup"""
    asyncio.create_task(cleanup_old_jobs())
    print("[Startup] Cleanup task started")


# Request models
class TranscriptUpdate(BaseModel):
    transcript: Optional[str] = None
    original_script: Optional[str] = None
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
    return {"service": "VoiSlide Movie v3", "workflow": "10-step hybrid"}


# ========== Slide Images ZIP Download ==========

@app.get("/api/download-slides/{job_id}")
async def download_slides_zip(job_id: str):
    """Download all slide images as ZIP file"""
    import zipfile
    import io
    from fastapi.responses import StreamingResponse
    from config import OUTPUT_DIR
    
    slides_dir = os.path.join(OUTPUT_DIR, f"{job_id}_slides")
    
    if not os.path.exists(slides_dir):
        raise HTTPException(404, "スライドが見つかりません")
    
    # Get all PNG files in slides directory
    slide_files = sorted([f for f in os.listdir(slides_dir) if f.endswith('.png')])
    
    if not slide_files:
        raise HTTPException(404, "スライド画像がありません")
    
    # Create ZIP in memory
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for filename in slide_files:
            filepath = os.path.join(slides_dir, filename)
            zip_file.write(filepath, filename)
    
    zip_buffer.seek(0)
    
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename=slides_{job_id[:8]}.zip"
        }
    )


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


# ========== Slide Add / Replace ==========

@app.post("/api/slides/{job_id}/add")
async def add_slide(
    job_id: str,
    position: int = Form(...),
    file: UploadFile = File(...)
):
    """タイムラインにスライドを追加"""
    import time
    import subprocess
    from config import VIDEO_WIDTH, VIDEO_HEIGHT
    
    pipeline = get_or_create_pipeline(job_id)
    
    allowed_ext = [".jpg", ".jpeg", ".png", ".gif", ".webp"]
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in allowed_ext:
        raise HTTPException(400, f"Unsupported file type: {ext}")
    
    # Save the image
    slides_dir = os.path.join(OUTPUT_DIR, job_id)
    os.makedirs(slides_dir, exist_ok=True)
    
    # Find a unique filename (always PNG for consistency)
    slide_num = position + 1
    filename = f"user_added_slide_{slide_num}_{int(time.time())}.png"
    filepath = os.path.join(slides_dir, filename)
    
    # Save uploaded file temporarily
    temp_upload = filepath + ".tmp"
    with open(temp_upload, "wb") as f:
        shutil.copyfileobj(file.file, f)
    
    # Resize/convert to match slide dimensions using FFmpeg
    cmd_resize = [
        "ffmpeg", "-y",
        "-i", temp_upload,
        "-vf", f"scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:force_original_aspect_ratio=decrease,pad={VIDEO_WIDTH}:{VIDEO_HEIGHT}:(ow-iw)/2:(oh-ih)/2:black",
        "-frames:v", "1",
        filepath
    ]
    
    result = subprocess.run(cmd_resize, capture_output=True, text=True)
    
    # Cleanup temp file
    if os.path.exists(temp_upload):
        os.remove(temp_upload)
    
    if result.returncode != 0:
        print(f"[AddSlide] FFmpeg resize error: {result.stderr[:200]}")
        raise HTTPException(500, "画像のリサイズに失敗しました")
    
    print(f"[AddSlide] Resized to {VIDEO_WIDTH}x{VIDEO_HEIGHT}: {filename}")
    
    # Insert into pipeline slide_images
    if hasattr(pipeline, 'slide_images') and pipeline.slide_images:
        if position <= len(pipeline.slide_images):
            pipeline.slide_images.insert(position, filepath)
        else:
            pipeline.slide_images.append(filepath)
    
    print(f"[AddSlide] Added slide at position {position} for job {job_id}: {filename}")
    
    return {
        "success": True,
        "position": position,
        "image_url": f"/outputs/{job_id}/{filename}"
    }


@app.post("/api/slides/{job_id}/replace")
async def replace_slide(
    job_id: str,
    slide_index: int = Form(...),
    file: UploadFile = File(...)
):
    """既存スライドの画像を差し替え"""
    import time
    import subprocess
    from config import VIDEO_WIDTH, VIDEO_HEIGHT
    
    pipeline = get_or_create_pipeline(job_id)
    
    allowed_ext = [".jpg", ".jpeg", ".png", ".gif", ".webp"]
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in allowed_ext:
        raise HTTPException(400, f"Unsupported file type: {ext}")
    
    # Save the replacement image (temporary)
    slides_dir = os.path.join(OUTPUT_DIR, job_id)
    os.makedirs(slides_dir, exist_ok=True)
    
    # Always save as PNG for consistency with AI-generated slides
    filename = f"user_replaced_slide_{slide_index + 1}_{int(time.time())}.png"
    filepath = os.path.join(slides_dir, filename)
    
    # Save uploaded file temporarily
    temp_upload = filepath + ".tmp"
    with open(temp_upload, "wb") as f:
        shutil.copyfileobj(file.file, f)
    
    # Resize/convert to match slide dimensions using FFmpeg
    # This ensures all slides in the concat file have identical dimensions
    cmd_resize = [
        "ffmpeg", "-y",
        "-i", temp_upload,
        "-vf", f"scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:force_original_aspect_ratio=decrease,pad={VIDEO_WIDTH}:{VIDEO_HEIGHT}:(ow-iw)/2:(oh-ih)/2:black",
        "-frames:v", "1",
        filepath
    ]
    
    result = subprocess.run(cmd_resize, capture_output=True, text=True)
    
    # Cleanup temp file
    if os.path.exists(temp_upload):
        os.remove(temp_upload)
    
    if result.returncode != 0:
        print(f"[ReplaceSlide] FFmpeg resize error: {result.stderr[:200]}")
        raise HTTPException(500, "画像のリサイズに失敗しました")
    
    print(f"[ReplaceSlide] Resized to {VIDEO_WIDTH}x{VIDEO_HEIGHT}: {filename}")
    
    # Replace in pipeline slide_images
    if hasattr(pipeline, 'slide_images') and pipeline.slide_images:
        if 0 <= slide_index < len(pipeline.slide_images):
            old_path = pipeline.slide_images[slide_index]
            pipeline.slide_images[slide_index] = filepath
            print(f"[ReplaceSlide] Replaced slide {slide_index} for job {job_id}: {os.path.basename(old_path)} → {filename}")
        else:
            raise HTTPException(400, f"Invalid slide_index: {slide_index}")
    else:
        raise HTTPException(400, "No slides found for this job")
    
    return {
        "success": True,
        "slide_index": slide_index,
        "image_url": f"/outputs/{job_id}/{filename}"
    }


@app.delete("/api/slides/{job_id}/{slide_index}")
async def delete_slide(job_id: str, slide_index: int):
    """バックエンドのpipeline.slide_imagesからスライドを削除"""
    pipeline = get_or_create_pipeline(job_id)
    
    if not hasattr(pipeline, 'slide_images') or not pipeline.slide_images:
        raise HTTPException(400, "No slides found for this job")
    
    if slide_index < 0 or slide_index >= len(pipeline.slide_images):
        raise HTTPException(400, f"Invalid slide_index: {slide_index} (total: {len(pipeline.slide_images)})")
    
    if len(pipeline.slide_images) <= 1:
        raise HTTPException(400, "Cannot delete the last remaining slide")
    
    removed_path = pipeline.slide_images.pop(slide_index)
    print(f"[DeleteSlide] Removed slide {slide_index} for job {job_id}: {os.path.basename(removed_path)}")
    print(f"[DeleteSlide] Remaining slides: {len(pipeline.slide_images)}")
    
    return {
        "success": True,
        "slide_index": slide_index,
        "remaining_slides": len(pipeline.slide_images)
    }


@app.post("/api/slides/{job_id}/duplicate/{slide_index}")
async def duplicate_slide(job_id: str, slide_index: int):
    """指定スライドを複製して直後に挿入"""
    pipeline = get_or_create_pipeline(job_id)

    if not hasattr(pipeline, 'slide_images') or not pipeline.slide_images:
        raise HTTPException(400, "No slides found for this job")

    if slide_index < 0 or slide_index >= len(pipeline.slide_images):
        raise HTTPException(400, f"Invalid slide_index: {slide_index} (total: {len(pipeline.slide_images)})")

    source_path = pipeline.slide_images[slide_index]

    if not os.path.exists(source_path):
        raise HTTPException(400, f"Source slide image not found: {os.path.basename(source_path)}")

    # コピー先ファイル名を生成
    base_dir = os.path.dirname(source_path)
    ext = os.path.splitext(source_path)[1]
    import time
    new_filename = f"slide_dup_{slide_index}_{int(time.time())}{ext}"
    new_path = os.path.join(base_dir, new_filename)

    shutil.copy2(source_path, new_path)

    # 複製元の直後に挿入
    insert_pos = slide_index + 1
    pipeline.slide_images.insert(insert_pos, new_path)

    # 公開URLを生成
    image_url = f"/outputs/{job_id}/{new_filename}"

    print(f"[DuplicateSlide] Duplicated slide {slide_index} -> {insert_pos} for job {job_id}")
    print(f"[DuplicateSlide] Total slides: {len(pipeline.slide_images)}")

    return {
        "success": True,
        "source_index": slide_index,
        "new_index": insert_pos,
        "image_url": image_url,
        "total_slides": len(pipeline.slide_images)
    }


@app.post("/api/upload-reference-image/{job_id}")
async def upload_reference_image(
    job_id: str,
    file: Optional[UploadFile] = File(None),
    illustration_request: Optional[str] = Form(None)
):
    """Upload reference image and/or illustration request for style guidance"""
    from config import OUTPUT_DIR
    
    pipeline = get_or_create_pipeline(job_id)
    
    # Handle reference image upload
    if file and file.filename:
        images_dir = os.path.join(OUTPUT_DIR, f"{job_id}_reference")
        os.makedirs(images_dir, exist_ok=True)
        
        allowed_ext = [".jpg", ".jpeg", ".png", ".gif", ".webp"]
        ext = os.path.splitext(file.filename)[1].lower()
        
        if ext not in allowed_ext:
            raise HTTPException(400, f"サポートされていない画像形式です: {ext}")
        
        filename = f"reference{ext}"
        filepath = os.path.join(images_dir, filename)
        
        with open(filepath, "wb") as f:
            shutil.copyfileobj(file.file, f)
        
        pipeline.reference_image = filepath
        print(f"[Reference Image] Saved reference image for job {job_id}: {filepath}")
    
    # Handle illustration request text
    if illustration_request:
        pipeline.illustration_request = illustration_request
        print(f"[Illustration Request] Saved request for job {job_id}: {illustration_request[:50]}...")
    
    return {
        "success": True,
        "has_reference_image": hasattr(pipeline, 'reference_image') and pipeline.reference_image is not None,
        "has_illustration_request": hasattr(pipeline, 'illustration_request') and pipeline.illustration_request is not None
    }



# ========== STEP 1: Upload Audio ==========

_AUDIO_STORAGE_RETRY_DELAYS_SEC = (1, 4, 12)  # exponential backoff between attempts


async def _upload_audio_to_storage_with_retry(
    audio_path: str,
    user_id: Optional[str],
    project_id: Optional[str],
    log_prefix: str = "[AudioStorage]",
) -> tuple:
    """Upload audio to Supabase Storage with explicit status reporting + retry.

    Returns (storage_path or None, status, detail) where status is one of:
      - 'persisted': uploaded successfully, path is set
      - 'skipped'  : intentionally not attempted (no creds / no headers)
      - 'failed'   : attempts exhausted; user should be warned

    The previous implementation just returned None on failure, which was
    indistinguishable from "intentionally skipped" — the frontend then
    silently saved a project with no audioStoragePath, and 24h later the
    restore couldn't recover audio. Now the frontend can show a clear
    warning when status == 'failed'.
    """
    import asyncio as _asyncio

    if not user_id or not project_id:
        return (None, "skipped", "missing_user_or_project_id")

    try:
        from services.supabase_storage import upload_audio as storage_upload, is_configured
    except Exception as e:
        print(f"{log_prefix} ✗ storage import failed: {e}")
        return (None, "failed", "import_error")

    if not is_configured():
        print(f"{log_prefix} skipped (Supabase not configured)")
        return (None, "skipped", "supabase_not_configured")

    last_err: Optional[str] = None
    for attempt, delay_before in enumerate(((0,) + _AUDIO_STORAGE_RETRY_DELAYS_SEC)):
        if delay_before:
            await _asyncio.sleep(delay_before)
        attempt_num = attempt + 1
        try:
            storage_path = await storage_upload(
                audio_path, user_id, project_id, ext=os.path.splitext(audio_path)[1]
            )
            if storage_path:
                print(f"{log_prefix} ✓ attempt {attempt_num}: persisted to {storage_path}")
                return (storage_path, "persisted", "")
            last_err = "upload_returned_none"
            print(f"{log_prefix} attempt {attempt_num} ✗ upload returned None")
        except Exception as e:
            last_err = f"{type(e).__name__}: {e}"
            print(f"{log_prefix} attempt {attempt_num} ✗ exception: {last_err}")

    print(
        f"{log_prefix} ✗ GAVE UP after {len(_AUDIO_STORAGE_RETRY_DELAYS_SEC) + 1} attempts: "
        f"last_err={last_err}. Audio is on local disk but NOT persisted — next "
        f"restore after Railway redeploy will fail to recover this audio."
    )
    return (None, "failed", last_err or "unknown")


@app.post("/api/upload-audio")
async def upload_audio(
    file: UploadFile = File(...),
    x_user_id: Optional[str] = Header(None),
    x_project_id: Optional[str] = Header(None),
):
    """Step 1: Upload audio or video file. For video, audio is auto-extracted.

    When `x-user-id` and `x-project-id` headers are provided, the extracted
    audio is also uploaded to Supabase Storage for persistence across
    Railway redeploys. The storage path is returned in the response as
    `audio_storage_path`.
    """
    audio_ext = [".mp3", ".wav", ".m4a"]
    video_ext = [".mp4", ".mov", ".webm", ".avi", ".mkv"]
    allowed_ext = audio_ext + video_ext
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in allowed_ext:
        raise HTTPException(400, f"対応形式: MP3, WAV, M4A, MP4, MOV, WebM")

    job_id = str(uuid.uuid4())
    upload_path = os.path.join(UPLOAD_DIR, f"{job_id}{ext}")

    with open(upload_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    is_video = ext in video_ext
    facecam_auto_set = False

    if is_video:
        # Extract audio from video using FFmpeg
        audio_path = os.path.join(UPLOAD_DIR, f"{job_id}.wav")
        import subprocess
        cmd = [
            "ffmpeg", "-y",
            "-i", upload_path,
            "-vn",  # No video
            "-acodec", "pcm_s16le",
            "-ar", "44100",
            "-ac", "1",
            audio_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"[Upload] FFmpeg audio extraction error: {result.stderr[:200]}")
            raise HTTPException(500, "動画から音声を抽出できませんでした")

        print(f"[Upload] Extracted audio from video: {audio_path}")
        facecam_auto_set = True
    else:
        audio_path = upload_path

    # Initialize job
    jobs[job_id] = {
        "id": job_id,
        "step": 1,
        "status": "uploaded",
        "audio_path": audio_path,
        "created_at": datetime.now().isoformat()
    }

    # Track job timestamp for cleanup
    job_timestamps[job_id] = datetime.now()

    # Initialize pipeline
    pipeline = get_or_create_pipeline(job_id, audio_path)

    # Auto-set face cam if video was uploaded
    if facecam_auto_set:
        pipeline.facecam_video_path = upload_path
        print(f"[Upload] Auto-set face cam video: {upload_path}")

    # Upload audio to Supabase Storage for persistence across redeploys.
    # We track WHY the upload didn't happen (vs just returning None) so the
    # frontend can show a clear warning if the user's work isn't durably saved.
    audio_storage_path, audio_storage_status, audio_storage_detail = (
        await _upload_audio_to_storage_with_retry(
            audio_path, x_user_id, x_project_id, log_prefix="[Upload]"
        )
    )
    jobs[job_id]["audio_storage_status"] = audio_storage_status

    return {
        "job_id": job_id,
        "message": "動画アップロード完了" if is_video else "音声アップロード完了",
        "is_video": is_video,
        "facecam_auto_set": facecam_auto_set,
        "audio_storage_path": audio_storage_path,  # None if Storage not configured
        "audio_storage_status": audio_storage_status,  # 'persisted' | 'failed' | 'skipped'
        "audio_storage_detail": audio_storage_detail,  # Why, if not 'persisted'
    }


@app.post("/api/reupload-audio/{job_id}")
async def reupload_audio(
    job_id: str,
    file: UploadFile = File(...),
    x_user_id: Optional[str] = Header(None),
    x_project_id: Optional[str] = Header(None),
):
    """Re-upload audio for a restored project whose original audio was lost
    (e.g. after Railway redeploy wiped the filesystem).

    Keeps the existing job_id so all other project state stays intact.
    Replaces any placeholder WAV with the real audio file.

    When user_id + project_id are provided, also uploads to Supabase Storage
    so the next restore won't need a manual re-upload.
    """
    audio_ext = [".mp3", ".wav", ".m4a"]
    video_ext = [".mp4", ".mov", ".webm", ".avi", ".mkv"]
    allowed_ext = audio_ext + video_ext
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in allowed_ext:
        raise HTTPException(400, "対応形式: MP3, WAV, M4A, MP4, MOV, WebM")

    # Job must already exist (from restore-project)
    if job_id not in jobs:
        raise HTTPException(404, "Job not found. Please restore the project first.")

    upload_path = os.path.join(UPLOAD_DIR, f"{job_id}{ext}")
    with open(upload_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    is_video = ext in video_ext
    if is_video:
        audio_path = os.path.join(UPLOAD_DIR, f"{job_id}.wav")
        import subprocess
        cmd = [
            "ffmpeg", "-y",
            "-i", upload_path,
            "-vn",
            "-acodec", "pcm_s16le",
            "-ar", "44100",
            "-ac", "1",
            audio_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"[Reupload] FFmpeg audio extraction error: {result.stderr[:200]}")
            raise HTTPException(500, "動画から音声を抽出できませんでした")
        print(f"[Reupload] Extracted audio from video: {audio_path}")
    else:
        audio_path = upload_path

    # Remove any placeholder WAV left over from restore
    placeholder = os.path.join(UPLOAD_DIR, f"{job_id}_placeholder.wav")
    if os.path.exists(placeholder):
        try:
            os.remove(placeholder)
            print(f"[Reupload] Removed placeholder: {placeholder}")
        except OSError:
            pass

    # Update pipeline to point at the new audio
    pipeline = get_or_create_pipeline(job_id)
    pipeline.audio_path = audio_path
    jobs[job_id]["audio_path"] = audio_path
    if is_video and not getattr(pipeline, "facecam_video_path", None):
        pipeline.facecam_video_path = upload_path
        print(f"[Reupload] Auto-set face cam video: {upload_path}")

    # Also push to Supabase Storage so future restores can recover this audio.
    audio_storage_path, audio_storage_status, audio_storage_detail = (
        await _upload_audio_to_storage_with_retry(
            audio_path, x_user_id, x_project_id, log_prefix="[Reupload]"
        )
    )
    jobs[job_id]["audio_storage_status"] = audio_storage_status

    print(f"[Reupload] ✓ Audio re-uploaded for job {job_id}: {audio_path}")
    return {
        "job_id": job_id,
        "message": "音声を再アップロードしました",
        "is_video": is_video,
        "audio_path": audio_path,
        "audio_storage_path": audio_storage_path,
        "audio_storage_status": audio_storage_status,
        "audio_storage_detail": audio_storage_detail,
    }


# ========== STEP 2: Transcribe ==========

@app.post("/api/transcribe/{job_id}")
async def transcribe(
    job_id: str,
    background_tasks: BackgroundTasks,
    cleanup_audio: bool = True,
    cleanup_mode: str = "natural",  # "strict" or "natural"
    silence_threshold: float = 0.5,  # user-adjustable
    speed_factor: float = 1.0,  # 1.0, 1.2, 1.5, 2.0
    x_openai_key: Optional[str] = Header(None),
    x_gemini_key: Optional[str] = Header(None),
    x_gemini_model: Optional[str] = Header(None),
    x_user_id: Optional[str] = Header(None, alias="x-user-id"),
    x_project_id: Optional[str] = Header(None, alias="x-project-id"),
):
    """Step 2: Start transcription (async background processing)"""
    audio_path = jobs.get(job_id, {}).get("audio_path")
    if not audio_path:
        raise HTTPException(404, "Job not found or no audio uploaded")

    # Store API keys and settings in job
    if x_openai_key:
        jobs[job_id]["openai_key"] = x_openai_key
    if x_gemini_key:
        jobs[job_id]["gemini_key"] = x_gemini_key
    if x_gemini_model:
        jobs[job_id]["gemini_model"] = x_gemini_model
    # Remember which Supabase project this job belongs to — needed so the
    # post-cleanup / post-speed audio can be uploaded to Storage and survive
    # a Railway redeploy. Without this, restore falls back to the ORIGINAL
    # uncut audio and the video ends up with the pre-cleanup duration.
    if x_user_id:
        jobs[job_id]["user_id"] = x_user_id
    if x_project_id:
        jobs[job_id]["project_id"] = x_project_id

    jobs[job_id]["step"] = 2
    jobs[job_id]["transcribe_status"] = "processing"
    jobs[job_id]["transcribe_progress"] = "開始中..."

    # Store settings for background task
    jobs[job_id]["cleanup_settings"] = {
        "cleanup_audio": cleanup_audio,
        "cleanup_mode": cleanup_mode,
        "silence_threshold": silence_threshold,
        "speed_factor": max(0.5, min(3.0, speed_factor))  # clamp to safe range
    }

    # Start background processing
    background_tasks.add_task(
        run_transcribe_background,
        job_id,
        x_openai_key
    )

    return {
        "job_id": job_id,
        "status": "processing",
        "message": "文字起こしを開始しました"
    }


async def run_transcribe_background(job_id: str, openai_key: Optional[str]):
    """Background task for transcription"""
    try:
        audio_path = jobs[job_id].get("audio_path")
        pipeline = get_or_create_pipeline(job_id, audio_path)
        settings = jobs[job_id].get("cleanup_settings", {})
        
        cleanup_audio = settings.get("cleanup_audio", True)
        cleanup_mode = settings.get("cleanup_mode", "natural")
        silence_threshold = settings.get("silence_threshold", 1.0)
        speed_factor = settings.get("speed_factor", 1.0)
        
        # Mode configuration
        mode_config = {
            "strict": {"threshold_db": -30, "min_duration": 0.5, "natural": False},
            "natural": {"threshold_db": -40, "min_duration": 0.8, "natural": True}
        }
        config = mode_config.get(cleanup_mode, mode_config["natural"])
        effective_min_duration = silence_threshold if silence_threshold > 0 else config["min_duration"]
        
        # Step 2a: Trim silence
        jobs[job_id]["transcribe_progress"] = "無音トリミング中..."
        try:
            from services.transcription import trim_silence_from_audio
            original_audio_path = jobs[job_id].get("audio_path")
            if original_audio_path:
                trimmed_path = trim_silence_from_audio(original_audio_path, threshold_db=-50, min_silence_duration=1.0)
                if trimmed_path != original_audio_path:
                    jobs[job_id]["audio_path"] = trimmed_path
                    jobs[job_id]["original_audio_path"] = original_audio_path
                    pipeline.audio_path = trimmed_path
                    print(f"[Transcribe] Audio trimmed: {original_audio_path} → {trimmed_path}")
        except Exception as e:
            print(f"[Transcribe] Silence trim failed: {e}")
        
        # Step 2b: Transcription
        jobs[job_id]["transcribe_progress"] = "AI文字起こし中..."
        result = await pipeline.step_transcribe(openai_key=openai_key)
        
        # Step 2c: Audio cleanup
        cleanup_result = None
        if cleanup_audio:
            jobs[job_id]["transcribe_progress"] = "無音・フィラー除去中..."
            try:
                from services.audio_cleanup import cleanup_audio as do_cleanup
                audio_path = jobs[job_id].get("audio_path")
                if audio_path:
                    cleanup_result = await do_cleanup(
                        audio_path=audio_path,
                        segments=result.get("segments", []),
                        silence_threshold=effective_min_duration,
                        silence_threshold_db=config["threshold_db"],
                        preserve_natural_pauses=config["natural"]
                    )
                    if cleanup_result and cleanup_result.get("cleaned_audio_path"):
                        # 過剰カット検出：20%以上カットされている場合はスキップ
                        orig_dur = cleanup_result.get('original_duration', 0)
                        removed = cleanup_result.get('total_removed_seconds', 0)
                        if orig_dur > 0 and removed / orig_dur > 0.20:
                            print(f"[Cleanup] WARNING: Would remove {removed:.1f}s ({removed/orig_dur*100:.0f}%) - exceeds 20% safety limit, skipping cleanup")
                            cleanup_result = {"error": "safety_limit", "skipped": True}
                        else:
                            jobs[job_id]["audio_path"] = cleanup_result["cleaned_audio_path"]
                            jobs[job_id]["original_audio_path"] = audio_path
                            pipeline.audio_path = cleanup_result["cleaned_audio_path"]
                            # Save keep_regions for facecam video sync
                            if cleanup_result.get("keep_regions"):
                                pipeline.audio_keep_regions = cleanup_result["keep_regions"]
                                print(f"[Cleanup] Saved {len(cleanup_result['keep_regions'])} keep_regions for facecam sync")
                            print(f"[Cleanup] Duration: {cleanup_result.get('original_duration', 0):.1f}s → {cleanup_result.get('new_duration', 0):.1f}s")
                            if cleanup_result.get("new_segments"):
                                result["segments"] = cleanup_result["new_segments"]
                                pipeline.segments = cleanup_result["new_segments"]
            except Exception as e:
                print(f"Audio cleanup failed: {e}")
                cleanup_result = {"error": str(e)}
        
        # Store results
        jobs[job_id]["transcribe_status"] = "completed"
        jobs[job_id]["transcribe_progress"] = "完了"
        jobs[job_id]["transcript"] = result["transcript"]
        jobs[job_id]["segments"] = result["segments"]
        
        if cleanup_result and not cleanup_result.get("error"):
            jobs[job_id]["cleanup_result"] = {
                "removed_silences": cleanup_result.get("removed_silences", 0),
                "removed_fillers": cleanup_result.get("removed_fillers", 0),
                "total_removed_seconds": cleanup_result.get("total_removed_seconds", 0),
                "original_duration": cleanup_result.get("original_duration", 0),
                "new_duration": cleanup_result.get("new_duration", 0)
            }
        
        # Step 2d: Speed processing (atempo)
        if speed_factor != 1.0:
            jobs[job_id]["transcribe_progress"] = f"倍速処理中 ({speed_factor}x)..."
            # Save pre-speed state for later re-processing
            jobs[job_id]["pre_speed_audio_path"] = jobs[job_id].get("audio_path")
            jobs[job_id]["pre_speed_segments"] = [dict(s) for s in (result.get("segments") or [])]
            try:
                import subprocess
                current_audio = jobs[job_id].get("audio_path")
                if current_audio:
                    base, ext = os.path.splitext(current_audio)
                    speed_output = f"{base}_speed{speed_factor}x{ext}"
                    # FFmpeg atempo filter (supports 0.5-2.0; chain for >2.0)
                    atempo_filters = []
                    remaining = speed_factor
                    while remaining > 2.0:
                        atempo_filters.append("atempo=2.0")
                        remaining /= 2.0
                    atempo_filters.append(f"atempo={remaining}")
                    filter_str = ",".join(atempo_filters)
                    
                    cmd = [
                        "ffmpeg", "-y", "-i", current_audio,
                        "-filter:a", filter_str,
                        speed_output
                    ]
                    proc = subprocess.run(cmd, capture_output=True, text=True)
                    if proc.returncode != 0:
                        print(f"[Speed] FFmpeg error: {proc.stderr}")
                        raise Exception(f"FFmpeg failed: {proc.stderr[:200]}")
                    jobs[job_id]["audio_path"] = speed_output
                    pipeline.audio_path = speed_output
                    
                    # Adjust segment timestamps
                    segments = result.get("segments", pipeline.segments or [])
                    for seg in segments:
                        seg["start"] = seg["start"] / speed_factor
                        seg["end"] = seg["end"] / speed_factor
                    result["segments"] = segments
                    pipeline.segments = segments
                    
                    # Adjust keep_regions if present
                    if hasattr(pipeline, 'audio_keep_regions') and pipeline.audio_keep_regions:
                        pipeline.audio_keep_regions = [
                            (start / speed_factor, end / speed_factor)
                            for start, end in pipeline.audio_keep_regions
                        ]
                    
                    print(f"[Speed] Applied {speed_factor}x speed: {current_audio} → {speed_output}")
                    pipeline.speed_factor = speed_factor
            except Exception as e:
                print(f"[Speed] Speed processing failed: {e}")
                # Continue without speed change
            
            # Mix BGM if pending (user uploaded BGM before cleanup was done)
            bgm_path = jobs[job_id].get("bgm_path")
            bgm_pending = jobs[job_id].get("bgm_pending", False)
            if bgm_path and bgm_pending and os.path.exists(bgm_path):
                jobs[job_id]["transcribe_progress"] = "BGMミックス中..."
                try:
                    from services.audio_mixer import mix_audio_with_bgm
                    
                    cleaned_audio = cleanup_result.get("cleaned_audio_path")
                    if cleaned_audio and os.path.exists(cleaned_audio):
                        base, ext = os.path.splitext(cleaned_audio)
                        output_path = f"{base}_mixed.mp3"
                        
                        # Use saved BGM settings or defaults
                        bgm_volume = jobs[job_id].get("bgm_volume", -27)
                        play_mode = jobs[job_id].get("bgm_play_mode", "loop")
                        fade_in = jobs[job_id].get("bgm_fade_in", True)
                        fade_out = jobs[job_id].get("bgm_fade_out", True)
                        
                        mix_audio_with_bgm(
                            speech_path=cleaned_audio,
                            bgm_path=bgm_path,
                            output_path=output_path,
                            bgm_volume_reduction=bgm_volume,
                            play_mode=play_mode,
                            enable_fade_in=fade_in,
                            enable_fade_out=fade_out,
                        )
                        
                        jobs[job_id]["mixed_path"] = output_path
                        jobs[job_id]["bgm_pending"] = False
                        print(f"[BGM Mix] Mixed BGM with cleaned audio: {output_path}")
                except Exception as e:
                    print(f"[BGM Mix] Failed: {e}")
        
        print(f"[Transcribe] Completed for job {job_id}")

        # Persist the post-cleanup / post-speed audio to Supabase Storage so
        # the user's cleanup choices survive restore. Without this, restore
        # would fall back to the ORIGINAL uncut audio and the re-generated
        # video would be longer than the user expected.
        #
        # Only upload when:
        #   (1) the final audio_path differs from the original upload
        #       (i.e. cleanup or speed actually changed something), and
        #   (2) we have a user/project id to route the upload.
        try:
            user_id = jobs[job_id].get("user_id")
            project_id = jobs[job_id].get("project_id")
            final_audio = jobs[job_id].get("audio_path")
            original_audio = jobs[job_id].get("original_audio_path")
            if (
                user_id and project_id
                and final_audio and original_audio
                and final_audio != original_audio
                and os.path.exists(final_audio)
            ):
                # Schedule fire-and-forget so we don't hold up the user.
                asyncio.create_task(
                    _upload_processed_audio_fire_and_forget(
                        final_audio, user_id, project_id, job_id
                    )
                )
            else:
                print(f"[ProcessedAudio] skipped for job={job_id} "
                      f"(user={bool(user_id)}, project={bool(project_id)}, "
                      f"changed={final_audio != original_audio if final_audio else False})")
        except Exception as e:
            print(f"[ProcessedAudio] scheduling failed: {e}")

    except Exception as e:
        print(f"[Transcribe] Error for job {job_id}: {e}")
        jobs[job_id]["transcribe_status"] = "error"
        jobs[job_id]["transcribe_error"] = str(e)


async def _upload_processed_audio_fire_and_forget(
    local_path: str,
    user_id: str,
    project_id: str,
    job_id: str,
):
    """Upload the post-cleanup audio with a small retry loop. Mirrors the
    video / slides cache helpers so failures are visible in Railway logs."""
    try:
        from services.supabase_storage import upload_processed_audio
    except Exception as e:
        print(f"[ProcessedAudio] ✗ import failed: {e}")
        return

    for attempt, delay in enumerate((0, 2, 8, 30)):
        if delay:
            await asyncio.sleep(delay)
        try:
            path = await upload_processed_audio(local_path, user_id, project_id)
            if path:
                print(f"[ProcessedAudio] ✓ attempt {attempt + 1}: cached {path} for project={project_id}")
                if job_id in jobs:
                    jobs[job_id]["processed_audio_status"] = "cached"
                return
        except Exception as e:
            print(f"[ProcessedAudio] attempt {attempt + 1} ✗ {type(e).__name__}: {e}")
    print(f"[ProcessedAudio] ✗ GAVE UP for project={project_id} — next restore will use the uncut original")
    if job_id in jobs:
        jobs[job_id]["processed_audio_status"] = "failed"


@app.get("/api/transcribe-status/{job_id}")
async def get_transcribe_status(job_id: str):
    """Get transcription status (for polling)"""
    if job_id not in jobs:
        raise HTTPException(404, "Job not found")
    
    job = jobs[job_id]
    status = job.get("transcribe_status", "unknown")
    
    response = {
        "job_id": job_id,
        "status": status,
        "progress": job.get("transcribe_progress", "")
    }
    
    if status == "completed":
        response["transcript"] = job.get("transcript", "")
        response["segments"] = job.get("segments", [])
        if job.get("cleanup_result"):
            response["cleanup"] = job["cleanup_result"]
    elif status == "error":
        response["error"] = job.get("transcribe_error", "Unknown error")
    
    return response


@app.get("/api/audio/{job_id}/trimmed")
async def get_trimmed_audio(job_id: str):
    """Download the processed audio file (includes speed processing if applied)"""
    if job_id not in jobs:
        raise HTTPException(404, "Job not found")
    
    job = jobs[job_id]
    audio_path = job.get("audio_path")
    
    if not audio_path or not os.path.exists(audio_path):
        raise HTTPException(404, "Audio file not found")
    
    ext = os.path.splitext(audio_path)[1]
    filename = f"{job_id}_processed{ext}"
    
    return FileResponse(
        audio_path,
        media_type="audio/mpeg",
        filename=filename,
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@app.post("/api/audio/{job_id}/apply-speed")
async def apply_speed(job_id: str, speed_factor: float = 1.0):
    """Re-apply speed processing to the audio"""
    if job_id not in jobs:
        raise HTTPException(404, "Job not found")
    
    job = jobs[job_id]
    
    # Save pre-speed state on first use
    if not job.get("pre_speed_audio_path"):
        job["pre_speed_audio_path"] = job.get("audio_path")
        if pipelines.get(job_id) and pipelines[job_id].segments:
            job["pre_speed_segments"] = [dict(s) for s in pipelines[job_id].segments]
    
    base_audio = job["pre_speed_audio_path"]
    
    if not base_audio or not os.path.exists(base_audio):
        raise HTTPException(404, "Audio file not found")
    
    speed_factor = max(0.5, min(3.0, speed_factor))
    
    if speed_factor == 1.0:
        # Reset to base audio
        job["audio_path"] = base_audio
        pipeline = pipelines.get(job_id)
        if pipeline:
            pipeline.audio_path = base_audio
            if job.get("pre_speed_segments"):
                pipeline.segments = [dict(s) for s in job["pre_speed_segments"]]
                job["segments"] = pipeline.segments
        return {"status": "ok", "speed_factor": 1.0, "message": "通常速度に戻しました"}
    
    try:
        import subprocess
        base, ext = os.path.splitext(base_audio)
        speed_output = f"{base}_speed{speed_factor}x{ext}"
        
        # FFmpeg atempo filter (supports 0.5-2.0; chain for >2.0)
        atempo_filters = []
        remaining = speed_factor
        while remaining > 2.0:
            atempo_filters.append("atempo=2.0")
            remaining /= 2.0
        atempo_filters.append(f"atempo={remaining}")
        filter_str = ",".join(atempo_filters)
        
        cmd = [
            "ffmpeg", "-y", "-i", base_audio,
            "-filter:a", filter_str,
            speed_output
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            print(f"[Speed] FFmpeg error: {proc.stderr}")
            raise Exception(f"FFmpeg failed: {proc.stderr[:200]}")
        
        job["audio_path"] = speed_output
        pipeline = pipelines.get(job_id)
        if pipeline:
            pipeline.audio_path = speed_output
            # Adjust segment timestamps from base
            if pipeline.segments:
                base_segments = job.get("pre_speed_segments") or pipeline.segments
                pipeline.segments = [
                    {**seg, "start": seg["start"] / speed_factor, "end": seg["end"] / speed_factor}
                    for seg in base_segments
                ]
                job["segments"] = pipeline.segments
            pipeline.speed_factor = speed_factor
        
        print(f"[Speed] Re-applied {speed_factor}x: {base_audio} → {speed_output}")
        return {"status": "ok", "speed_factor": speed_factor, "message": f"{speed_factor}x倍速を適用しました"}
    except Exception as e:
        print(f"[Speed] Error: {e}")
        raise HTTPException(500, f"Speed processing failed: {e}")


# ========== BGM MIXING ==========

from services.audio_mixer import mix_audio_with_bgm, adjust_bgm_volume, parse_volume_feedback

@app.post("/api/audio/{job_id}/upload-bgm")
async def upload_bgm(job_id: str, file: UploadFile = File(...)):
    """Upload a BGM file for a job"""
    if job_id not in jobs:
        raise HTTPException(404, "Job not found")
    
    # Save BGM file
    bgm_filename = f"{job_id}_bgm_{file.filename}"
    bgm_path = os.path.join(UPLOAD_DIR, bgm_filename)
    
    with open(bgm_path, "wb") as f:
        content = await file.read()
        f.write(content)
    
    jobs[job_id]["bgm_path"] = bgm_path
    print(f"[BGM] Uploaded: {bgm_path}")
    
    return {"success": True, "bgm_path": bgm_path}


@app.post("/api/audio/{job_id}/mix-bgm")
async def mix_bgm(
    job_id: str, 
    bgm_volume: float = -27,
    play_mode: str = "loop",
    fade_in: bool = True,
    fade_out: bool = True
):
    """Mix the trimmed audio with uploaded BGM"""
    if job_id not in jobs:
        raise HTTPException(404, "Job not found")
    
    job = jobs[job_id]
    audio_path = job.get("audio_path")
    bgm_path = job.get("bgm_path")
    
    if not audio_path:
        raise HTTPException(400, "No audio file found")
    if not bgm_path:
        raise HTTPException(400, "No BGM file uploaded")
    
    # Save BGM settings first (these will be used later if mixing is deferred)
    jobs[job_id]["bgm_volume"] = bgm_volume
    jobs[job_id]["bgm_play_mode"] = play_mode
    jobs[job_id]["bgm_fade_in"] = fade_in
    jobs[job_id]["bgm_fade_out"] = fade_out
    
    # Check if cleanup has completed - use cleaned version if available
    base, ext = os.path.splitext(audio_path)
    clean_path = f"{base}_clean{ext}"
    trimmed_path = f"{base}_trimmed{ext}"
    
    # Priority: cleaned > trimmed > original
    if os.path.exists(clean_path):
        speech_path = clean_path
        print(f"[BGM Mix] Using cleaned audio: {speech_path}")
    elif os.path.exists(trimmed_path):
        speech_path = trimmed_path
        print(f"[BGM Mix] Using trimmed audio: {speech_path}")
    else:
        # Transcription/cleanup not done yet - defer mixing
        jobs[job_id]["bgm_pending"] = True
        print(f"[BGM Mix] Deferring mix - cleanup not complete yet. Settings saved.")
        return {
            "success": True,
            "deferred": True,
            "message": "BGM設定を保存しました。文字起こし・クリーンアップ完了後に自動でミックスされます。",
            "bgm_volume": bgm_volume,
            "play_mode": play_mode,
        }
    
    # Output path
    output_path = f"{base}_mixed.mp3"
    
    print(f"[BGM Mix] Volume: {bgm_volume}dB, Mode: {play_mode}, FadeIn: {fade_in}, FadeOut: {fade_out}")
    
    try:
        mix_audio_with_bgm(
            speech_path=speech_path,
            bgm_path=bgm_path,
            output_path=output_path,
            bgm_volume_reduction=bgm_volume,
            play_mode=play_mode,
            enable_fade_in=fade_in,
            enable_fade_out=fade_out,
        )
        
        jobs[job_id]["mixed_path"] = output_path
        jobs[job_id]["bgm_pending"] = False
        
        return {
            "success": True,
            "mixed_path": output_path,
            "bgm_volume": bgm_volume,
            "play_mode": play_mode,
        }
    except Exception as e:
        print(f"[BGM Mix] Error: {e}")
        raise HTTPException(500, f"Mixing failed: {str(e)}")


@app.post("/api/audio/{job_id}/adjust-bgm")
async def adjust_bgm(job_id: str, feedback: str = None, bgm_volume: float = None):
    """Adjust BGM volume based on feedback or direct value"""
    if job_id not in jobs:
        raise HTTPException(404, "Job not found")
    
    job = jobs[job_id]
    audio_path = job.get("audio_path")
    bgm_path = job.get("bgm_path")
    
    if not audio_path or not bgm_path:
        raise HTTPException(400, "Audio or BGM file not found")
    
    # Determine new volume
    if bgm_volume is not None:
        new_volume = bgm_volume
    elif feedback:
        new_volume = parse_volume_feedback(feedback)
        print(f"[BGM Adjust] Feedback: '{feedback}' -> Volume: {new_volume}dB")
    else:
        raise HTTPException(400, "Provide either feedback or bgm_volume")
    
    # Use trimmed version if exists
    base, ext = os.path.splitext(audio_path)
    speech_path = f"{base}_trimmed{ext}" if os.path.exists(f"{base}_trimmed{ext}") else audio_path
    output_path = f"{base}_mixed.mp3"
    
    try:
        adjust_bgm_volume(
            mixed_path=output_path,
            original_speech_path=speech_path,
            bgm_path=bgm_path,
            output_path=output_path,
            new_bgm_volume_reduction=new_volume,
        )
        
        jobs[job_id]["mixed_path"] = output_path
        jobs[job_id]["bgm_volume"] = new_volume
        
        return {
            "success": True,
            "mixed_path": output_path,
            "bgm_volume": new_volume,
        }
    except Exception as e:
        print(f"[BGM Adjust] Error: {e}")
        raise HTTPException(500, f"Adjustment failed: {str(e)}")


@app.get("/api/audio/{job_id}/mixed")
async def get_mixed_audio(job_id: str):
    """Download the mixed audio file (with BGM)"""
    if job_id not in jobs:
        raise HTTPException(404, "Job not found")
    
    job = jobs[job_id]
    mixed_path = job.get("mixed_path")
    
    if not mixed_path or not os.path.exists(mixed_path):
        raise HTTPException(404, "Mixed audio not found")
    
    return FileResponse(
        mixed_path,
        media_type="audio/mpeg",
        filename=f"{job_id}_mixed.mp3",
        headers={"Content-Disposition": f"attachment; filename={job_id}_mixed.mp3"}
    )


# ========== STEP 3: Polish Transcript ==========

@app.post("/api/polish-transcript/{job_id}")
async def polish_transcript(
    job_id: str,
    update: Optional[TranscriptUpdate] = None,
    x_gemini_key: Optional[str] = Header(None),
    x_gemini_model: Optional[str] = Header(None),
    x_openrouter_key: Optional[str] = Header(None),
    x_openrouter_model: Optional[str] = Header(None),
):
    """Step 3: Polish and improve transcript"""
    pipeline = get_or_create_pipeline(job_id)

    # Store API key and model for this job
    if x_gemini_key:
        jobs[job_id]["gemini_key"] = x_gemini_key
    if x_gemini_model:
        jobs[job_id]["gemini_model"] = x_gemini_model
    if x_openrouter_key:
        jobs[job_id]["openrouter_key"] = x_openrouter_key
    if x_openrouter_model:
        jobs[job_id]["openrouter_model"] = x_openrouter_model

    jobs[job_id]["step"] = 3
    jobs[job_id]["status"] = "processing"

    edited = update.transcript if update else None
    original_script = update.original_script if update else None
    gemini_model = jobs[job_id].get("gemini_model", "gemini-3-flash-preview")
    result = await pipeline.step_polish_transcript(edited, gemini_key=x_gemini_key, original_script=original_script, model_name=gemini_model, openrouter_key=x_openrouter_key, openrouter_model=x_openrouter_model or "google/gemini-3-flash-preview")
    
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
    background_tasks: BackgroundTasks,
    update: Optional[TranscriptUpdate] = None,
    x_gemini_key: Optional[str] = Header(None),
    x_gemini_model: Optional[str] = Header(None),
    x_openrouter_key: Optional[str] = Header(None),
    x_openrouter_model: Optional[str] = Header(None),
):
    """Step 4: Start outline generation (async background processing)"""
    if job_id not in jobs:
        raise HTTPException(404, "Job not found")

    # Store API key, model and settings
    if x_gemini_key:
        jobs[job_id]["gemini_key"] = x_gemini_key
    if x_gemini_model:
        jobs[job_id]["gemini_model"] = x_gemini_model
    if x_openrouter_key:
        jobs[job_id]["openrouter_key"] = x_openrouter_key
    if x_openrouter_model:
        jobs[job_id]["openrouter_model"] = x_openrouter_model

    jobs[job_id]["step"] = 4
    jobs[job_id]["outline_status"] = "processing"
    jobs[job_id]["outline_progress"] = "アウトライン生成開始..."

    # Store settings for background task
    jobs[job_id]["outline_settings"] = {
        "transcript": update.transcript if update else None,
        "slide_count_mode": update.slide_count_mode if update else "auto",
        "custom_slide_count": update.custom_slide_count if update else 10
    }

    # Start background processing
    gemini_model = jobs[job_id].get("gemini_model", "gemini-3-flash-preview")
    background_tasks.add_task(
        run_outline_background,
        job_id,
        x_gemini_key,
        gemini_model,
        x_openrouter_key,
        x_openrouter_model,
    )

    return {
        "job_id": job_id,
        "status": "processing",
        "message": "アウトライン生成を開始しました"
    }


async def run_outline_background(job_id: str, gemini_key: Optional[str], model_name: str = "gemini-3-flash-preview", openrouter_key: Optional[str] = None, openrouter_model: Optional[str] = None):
    """Background task for outline generation"""
    try:
        pipeline = get_or_create_pipeline(job_id)
        settings = jobs[job_id].get("outline_settings", {})

        edited = settings.get("transcript")
        slide_count_mode = settings.get("slide_count_mode", "auto")
        custom_slide_count = settings.get("custom_slide_count", 10)

        jobs[job_id]["outline_progress"] = "AIでアウトライン作成中..."

        result = await pipeline.step_generate_outline(
            edited,
            gemini_key=gemini_key,
            slide_count_mode=slide_count_mode,
            custom_slide_count=custom_slide_count,
            model_name=model_name,
            openrouter_key=openrouter_key,
            openrouter_model=openrouter_model or "google/gemini-3-flash-preview",
        )
        
        jobs[job_id]["outline_status"] = "completed"
        jobs[job_id]["outline_progress"] = "完了"
        jobs[job_id]["outline"] = result["outline"]
        
        print(f"[Outline] Completed for job {job_id}")
        
    except Exception as e:
        print(f"[Outline] Error for job {job_id}: {e}")
        jobs[job_id]["outline_status"] = "error"
        jobs[job_id]["outline_error"] = str(e)


@app.get("/api/outline-status/{job_id}")
async def get_outline_status(job_id: str):
    """Get outline generation status (for polling)"""
    if job_id not in jobs:
        raise HTTPException(404, "Job not found")
    
    job = jobs[job_id]
    status = job.get("outline_status", "unknown")
    
    response = {
        "job_id": job_id,
        "status": status,
        "progress": job.get("outline_progress", "")
    }
    
    if status == "completed":
        response["outline"] = job.get("outline", [])
    elif status == "error":
        response["error"] = job.get("outline_error", "Unknown error")
    
    return response


# ========== STEP 5: Polish Outline ==========

@app.post("/api/polish-outline/{job_id}")
async def polish_outline(
    job_id: str,
    update: Optional[OutlineUpdate] = None,
    x_openrouter_key: Optional[str] = Header(None),
    x_openrouter_model: Optional[str] = Header(None),
    x_gemini_key: Optional[str] = Header(None),
    x_gemini_model: Optional[str] = Header(None),
):
    """Step 5: Brush up outline"""
    pipeline = get_or_create_pipeline(job_id)

    jobs[job_id]["step"] = 5
    jobs[job_id]["status"] = "processing"

    # Store Gemini key/model for this job
    if x_gemini_key:
        jobs[job_id]["gemini_key"] = x_gemini_key
    if x_gemini_model:
        jobs[job_id]["gemini_model"] = x_gemini_model

    # Store in api_keys dict
    if x_gemini_key:
        if job_id not in api_keys:
            api_keys[job_id] = {"openai": "", "gemini": ""}
        api_keys[job_id]["gemini"] = x_gemini_key

    # OpenRouter params from header or stored in job
    openrouter_key = x_openrouter_key or jobs.get(job_id, {}).get("openrouter_key", "")
    openrouter_model = x_openrouter_model or jobs.get(job_id, {}).get("openrouter_model", "google/gemini-3-flash-preview")

    # Gemini params from header or stored in job
    gemini_key = x_gemini_key or jobs.get(job_id, {}).get("gemini_key", "")
    gemini_model = x_gemini_model or jobs.get(job_id, {}).get("gemini_model", "gemini-3-flash-preview")

    edited = update.outline if update else None
    result = await pipeline.step_polish_outline(
        edited,
        model_name=gemini_model,
        openrouter_key=openrouter_key if openrouter_key else None,
        openrouter_model=openrouter_model,
        gemini_key=gemini_key if gemini_key else None,
    )

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
    x_gemini_model: Optional[str] = Header(None),
    x_color_theme: Optional[str] = Header(None),  # Color theme: cosmic, warm, elegant, nature, ocean, mono
    x_font_style: Optional[str] = Header(None),   # Font style: gothic, mincho, pop, handwritten
    x_openrouter_key: Optional[str] = Header(None),
    x_openrouter_model: Optional[str] = Header(None),
    x_openrouter_design_model: Optional[str] = Header(None),
    x_user_id: Optional[str] = Header(None, alias="x-user-id"),
    x_project_id: Optional[str] = Header(None, alias="x-project-id"),
):
    """Step 7 (Full AI Mode): AI generates unique custom slides from outline"""
    pipeline = get_or_create_pipeline(job_id)

    jobs[job_id]["step"] = 7
    jobs[job_id]["status"] = "generating_slides"

    # Sprint A: collect OpenRouter fallback events for the UI. Reset the
    # context list at the start of every request; openrouter_generate will
    # append to it when it swaps to the safe fallback model (invalid model
    # id). We read it back after generation and stash on the job so the
    # status endpoint can return it to the frontend.
    from services.openrouter_utils import _openrouter_warnings
    _openrouter_warnings.set([])

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
        gemini_model = x_gemini_model or jobs.get(job_id, {}).get("gemini_model", "gemini-3-flash-preview")
        openrouter_key = x_openrouter_key or jobs.get(job_id, {}).get("openrouter_key", "")
        openrouter_model = x_openrouter_model or jobs.get(job_id, {}).get("openrouter_model", "google/gemini-3-flash-preview")
        openrouter_design_model = x_openrouter_design_model or jobs.get(job_id, {}).get("openrouter_design_model", "google/gemini-3-flash-preview")
        image_paths = await generate_all_custom_slides(
            slides=slides,
            job_id=job_id,
            gemini_key=x_gemini_key,
            outline=outline,
            color_theme=x_color_theme,
            font_style=x_font_style,
            progress_callback=update_progress,
            model_name=gemini_model,
            openrouter_key=openrouter_key if openrouter_key else None,
            openrouter_model=openrouter_model,
            openrouter_design_model=openrouter_design_model,
        )
        
        # パイプラインに保存
        pipeline.slide_images = image_paths
        pipeline.slide_contents = slides
        
        # スライドプレビューURLを生成
        slide_previews = [f"/outputs/{job_id}_slides/{os.path.basename(p)}" for p in image_paths]
        
        jobs[job_id]["status"] = "completed"
        jobs[job_id]["slide_count"] = len(image_paths)

        # Capture any OpenRouter fallback warnings collected during this
        # request so /api/status can surface them to the UI. De-dup by
        # (requested_model, fallback_model) since many slide calls in one
        # batch would otherwise spam the same entry.
        warnings = _openrouter_warnings.get() or []
        if warnings:
            seen = set()
            deduped = []
            for w in warnings:
                key = (w.get("requested_model"), w.get("fallback_model"))
                if key not in seen:
                    seen.add(key)
                    deduped.append(w)
            jobs[job_id]["warnings"] = (jobs[job_id].get("warnings") or []) + deduped

        # Fire-and-forget upload to Supabase Storage so the slides survive
        # Railway redeploys. User is actively on the page here, so we skip
        # the debounce and schedule immediately.
        _schedule_slides_cache_immediate(job_id, x_user_id, x_project_id)

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
    copy_style_request: Optional[str] = None  # User copy/writing style (e.g., "話し言葉をそのまま使って")
    text_density: str = "standard"  # "simple" (title+headline) or "standard" (full)
    add_illustrations: bool = False  # Whether to add AI-generated illustrations
    illustration_percentage: int = 50  # Percentage of slides to add illustrations (10-100)
    facecam_position: Optional[str] = None  # PiP overlay position: top-left, top-right, bottom-left, bottom-right
    facecam_size: Optional[int] = None  # PiP overlay size in px
    # Sprint C: design mode. "flash_standard" (default) or "pro". Body takes
    # precedence over the x-design-mode header when both are sent.
    design_mode: Optional[str] = None


@app.post("/api/generate-slides-batch/{job_id}")
async def generate_slides_batch_endpoint(
    job_id: str,
    request: BatchGenerateRequest,
    background_tasks: BackgroundTasks,
    x_gemini_key: Optional[str] = Header(None),
    x_gemini_model: Optional[str] = Header(None),
    x_color_theme: Optional[str] = Header(None),
    x_font_style: Optional[str] = Header(None),
    x_openrouter_key: Optional[str] = Header(None),
    x_openrouter_model: Optional[str] = Header(None),
    x_openrouter_design_model: Optional[str] = Header(None),
    x_user_id: Optional[str] = Header(None, alias="x-user-id"),
    x_project_id: Optional[str] = Header(None, alias="x-project-id"),
    x_design_mode: Optional[str] = Header(None, alias="x-design-mode"),
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
        # Sprint A: isolate OpenRouter fallback warnings to this batch.
        # ContextVar.set is local to this task's context; the warnings list
        # is read back at the end so /api/status surfaces a dedup'd view.
        from services.openrouter_utils import _openrouter_warnings
        _openrouter_warnings.set([])
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
            
            # Get video dimensions from pipeline's aspect ratio
            video_w, video_h = get_video_dimensions(getattr(pipeline, 'aspect_ratio', 'landscape'))
            
            # Generate batch of slides
            gemini_model = x_gemini_model or jobs.get(job_id, {}).get("gemini_model", "gemini-3-flash-preview")
            openrouter_key = x_openrouter_key or jobs.get(job_id, {}).get("openrouter_key", "")
            openrouter_model = x_openrouter_model or jobs.get(job_id, {}).get("openrouter_model", "google/gemini-3-flash-preview")
            openrouter_design_model = x_openrouter_design_model or jobs.get(job_id, {}).get("openrouter_design_model", "google/gemini-3-flash-preview")

            # Sprint C: resolve design_mode with this precedence:
            #   body (request.design_mode) > header (x-design-mode) >
            #   job-memoized > default "flash_standard"
            # Unknown values normalize back to "flash_standard" so a client
            # bug can't accidentally flip every project to Pro mode.
            resolved_design_mode = (
                request.design_mode
                or x_design_mode
                or jobs.get(job_id, {}).get("design_mode")
                or "flash_standard"
            )
            if resolved_design_mode not in ("flash_standard", "pro"):
                print(f"[Batch Generate] Unknown design_mode={resolved_design_mode!r}, normalizing to flash_standard")
                resolved_design_mode = "flash_standard"
            jobs[job_id]["design_mode"] = resolved_design_mode
            print(f"[Batch Generate] design_mode={resolved_design_mode}")

            image_paths = await generate_all_custom_slides(
                slides=slides,
                job_id=job_id,
                gemini_key=x_gemini_key,
                outline=outline,
                color_theme=x_color_theme,
                font_style=x_font_style,
                user_images=getattr(pipeline, 'user_images', None),
                design_preference=request.design_preference,
                copy_style_request=request.copy_style_request,
                text_density=request.text_density,
                progress_callback=update_progress,
                start_slide=start,
                end_slide=end,
                reference_image_path=getattr(pipeline, 'reference_image', None),
                illustration_request=getattr(pipeline, 'illustration_request', None),
                add_illustrations=request.add_illustrations,
                illustration_percentage=request.illustration_percentage,
                video_width=video_w,
                video_height=video_h,
                facecam_position=request.facecam_position,
                facecam_size=request.facecam_size,
                model_name=gemini_model,
                openrouter_key=openrouter_key if openrouter_key else None,
                openrouter_model=openrouter_model,
                openrouter_design_model=openrouter_design_model,
                design_mode=resolved_design_mode,
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

            # Capture dedup'd OpenRouter fallback warnings onto the job so
            # /api/status surfaces them in the UI. Same shape as the
            # non-batch endpoint above.
            warnings = _openrouter_warnings.get() or []
            if warnings:
                seen = set()
                deduped = []
                for w in warnings:
                    key = (w.get("requested_model"), w.get("fallback_model"))
                    if key not in seen:
                        seen.add(key)
                        deduped.append(w)
                jobs[job_id]["warnings"] = (jobs[job_id].get("warnings") or []) + deduped

            # Only cache after the final batch — intermediate batches would
            # waste bandwidth re-uploading the same early slides on every pass.
            if is_complete:
                _schedule_slides_cache_immediate(job_id, x_user_id, x_project_id)
            
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
    # Sprint A: include OpenRouter fallback warnings captured during this
    # job so the UI can toast them. Empty list is fine — the frontend just
    # ignores it when empty. These are set by generate_slides_batch_endpoint
    # and generate_slides_endpoint after the generate call returns.
    warnings = jobs.get(job_id, {}).get("warnings") or []
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
        "total_slides": progress.get("total_slides", 0),
        "warnings": warnings,
    }


@app.get("/api/queue-status/{job_id}")
async def get_queue_status(job_id: str):
    """Get queue position and estimated wait time for a job"""
    from services.ai_slide_generator import get_queue_position
    queue_info = get_queue_position(job_id)
    return {
        "job_id": job_id,
        "position": queue_info.get("position", -1),
        "status": queue_info.get("status", "unknown"),
        "estimated_wait_minutes": queue_info.get("estimated_wait", 0),
        "active_count": queue_info.get("active_count", 0),
        "waiting_count": queue_info.get("waiting_count", 0)
    }



# ========== Slide Direct Text Editing ==========

@app.get("/api/slides/{job_id}/text/{slide_number}")
async def get_slide_text(job_id: str, slide_number: int):
    """Extract ALL visible text content from a slide's HTML"""
    if job_id not in jobs:
        raise HTTPException(404, "Job not found")
    
    from services.ai_slide_generator import get_html_content
    from bs4 import BeautifulSoup, NavigableString
    
    html = get_html_content(job_id, slide_number)
    if not html:
        raise HTTPException(404, f"Slide {slide_number} not found")
    
    try:
        soup = BeautifulSoup(html, 'html.parser')
        
        # Remove script, style, and meta elements
        for tag in soup.find_all(['script', 'style', 'meta', 'link']):
            tag.decompose()
        
        # Find all text-containing elements in body
        body = soup.find('body') or soup
        
        # Collect all leaf text elements (elements that directly contain text)
        text_items = []
        seen_texts = set()
        
        # Classes that indicate decorative/non-editable content
        SKIP_CLASSES = {'slide-number', 'footer', 'page-number', 'slide-count', 'watermark', 'branding'}
        # Classes that identify a semantic text element (should be captured as whole unit)
        SEMANTIC_CLASSES = {
            'title': 'title', 'main-title': 'title', 'heading': 'title',
            'subtitle': 'subtitle', 'sub-title': 'subtitle', 'subheading': 'subtitle',
            'key-message': 'key_message', 'key_message': 'key_message',
            'highlight': 'key_message', 'message': 'key_message', 'quote': 'key_message',
            'point': 'point', 'card': 'point', 'card-title': 'point', 'card-text': 'point',
            'bullet': 'point', 'feature': 'point', 'item': 'point',
        }
        
        import re
        slide_number_pattern = re.compile(r'^\d{1,2}\s*/\s*\d{1,2}$')
        
        def get_element_type(element):
            """Check if element has a semantic class and return its type."""
            tag = element.name
            classes = element.get('class', [])
            class_str = ' '.join(classes).lower() if classes else ''
            
            # Check tag first
            if tag == 'h1':
                return 'title'
            elif tag in ['h2', 'h3']:
                return 'subtitle'
            elif tag == 'li':
                return 'point'
            
            # Check classes
            for cls in classes:
                cls_lower = cls.lower()
                if cls_lower in SEMANTIC_CLASSES:
                    return SEMANTIC_CLASSES[cls_lower]
                # Partial match for compound classes like "main-title-text"
                for key, val in SEMANTIC_CLASSES.items():
                    if key in cls_lower:
                        return val
            
            return None
        
        def should_skip(element):
            """Check if element is decorative and should be skipped."""
            classes = element.get('class', [])
            for cls in classes:
                if cls.lower() in SKIP_CLASSES:
                    return True
                for skip in SKIP_CLASSES:
                    if skip in cls.lower():
                        return True
            return False
        
        def extract_text_elements(element, depth=0):
            """Recursively find all elements with direct text content"""
            if isinstance(element, NavigableString):
                return
            
            # Skip invisible/structural elements
            style = element.get('style', '')
            if 'display: none' in style or 'visibility: hidden' in style:
                return
            if element.name in ['script', 'style', 'meta', 'link', 'img', 'svg', 'path', 'br', 'hr']:
                return
            
            # Skip decorative elements
            if should_skip(element):
                return
            
            # Get full text of this element
            full_text = element.get_text(strip=True)
            
            # Skip empty or very short elements
            if not full_text or len(full_text) <= 1:
                return
            
            # Skip slide number patterns
            if slide_number_pattern.match(full_text):
                return
            
            # Check if this element has a semantic type
            el_type = get_element_type(element)
            
            if el_type:
                # This element has a semantic class — capture its FULL text as a single unit
                if full_text not in seen_texts:
                    seen_texts.add(full_text)
                    text_items.append({
                        "text": full_text,
                        "type": el_type,
                        "tag": element.name,
                    })
                return  # Don't recurse into semantic elements
            
            # No semantic class — check if this is a leaf element
            child_texts = []
            for child in element.children:
                if hasattr(child, 'get_text'):
                    ct = child.get_text(strip=True)
                    if ct and len(ct) > 1:
                        child_texts.append(ct)
            
            if not child_texts or (len(child_texts) == 1 and child_texts[0] == full_text):
                # Leaf element — add as generic text
                if full_text not in seen_texts:
                    seen_texts.add(full_text)
                    text_items.append({
                        "text": full_text,
                        "type": "text",
                        "tag": element.name,
                    })
            else:
                # Has children — recurse
                for child in element.children:
                    extract_text_elements(child, depth + 1)
        
        extract_text_elements(body)
        
        # Organize by type
        title = ""
        subtitle = ""
        key_message = ""
        points = []
        other_texts = []
        
        for item in text_items:
            if item["type"] == "title" and not title:
                title = item["text"]
            elif item["type"] == "subtitle" and not subtitle:
                subtitle = item["text"]
            elif item["type"] == "key_message" and not key_message:
                key_message = item["text"]
            elif item["type"] == "point":
                points.append(item["text"])
            else:
                # Filter out remaining slide-number-like text and very short text
                t = item["text"]
                if not slide_number_pattern.match(t) and len(t) > 2:
                    other_texts.append(t)
        
        # If no points found, promote other_texts to points
        if not points and other_texts:
            points = other_texts
            other_texts = []
        
        return {
            "slide_number": slide_number,
            "title": title,
            "subtitle": subtitle,
            "key_message": key_message,
            "points": points,
            "other_texts": other_texts
        }
    except Exception as e:
        raise HTTPException(500, f"Failed to extract text: {str(e)}")


class TextChange(BaseModel):
    original: str
    edited: str

class SlideTextUpdateRequest(BaseModel):
    text_changes: List[TextChange]


@app.put("/api/slides/{job_id}/text/{slide_number}")
async def update_slide_text(
    job_id: str,
    slide_number: int,
    request: SlideTextUpdateRequest,
    x_gemini_key: Optional[str] = Header(None),
    x_gemini_model: Optional[str] = Header(None),
    x_user_id: Optional[str] = Header(None, alias="x-user-id"),
    x_project_id: Optional[str] = Header(None, alias="x-project-id"),
):
    """Update slide text directly (no AI) and re-render"""
    if job_id not in jobs:
        raise HTTPException(404, "Job not found")
    
    from services.ai_slide_generator import (
        get_html_content, update_html_content, update_html_text_content,
        fix_body_dimensions
    )
    from playwright.async_api import async_playwright
    
    html = get_html_content(job_id, slide_number)
    if not html:
        raise HTTPException(404, f"Slide {slide_number} not found")
    
    try:
        # Save to history before editing
        if job_id not in slide_history:
            slide_history[job_id] = {}
        if slide_number not in slide_history[job_id]:
            slide_history[job_id][slide_number] = []
        
        slides_dir = os.path.join(OUTPUT_DIR, f"{job_id}_slides")
        current_image_path = os.path.join(slides_dir, f"slide_{slide_number:03d}.png")
        backup_image_path = os.path.join(slides_dir, f"slide_{slide_number:03d}_v{len(slide_history[job_id][slide_number])}.png")
        if os.path.exists(current_image_path):
            shutil.copy(current_image_path, backup_image_path)
        
        slide_history[job_id][slide_number].append({
            "html": html,
            "image_path": backup_image_path,
            "timestamp": datetime.now().isoformat()
        })
        
        # Apply text changes via BeautifulSoup (preserves layout)
        from bs4 import BeautifulSoup, NavigableString
        soup = BeautifulSoup(html, 'html.parser')
        
        for change in request.text_changes:
            if change.original == change.edited:
                continue  # No change
            
            # Walk all text nodes in the HTML and replace matching text
            for text_node in soup.find_all(string=True):
                if isinstance(text_node, NavigableString) and change.original in text_node.strip():
                    # Replace the text while preserving surrounding whitespace
                    new_text = str(text_node).replace(change.original, change.edited)
                    text_node.replace_with(NavigableString(new_text))
                    break  # Only replace first occurrence
        
        new_html = str(soup)
        
        # Fix body dimensions for portrait mode
        pipeline = get_or_create_pipeline(job_id)
        video_w, video_h = get_video_dimensions(getattr(pipeline, 'aspect_ratio', 'landscape'))
        new_html = fix_body_dimensions(new_html, video_w, video_h)
        
        # Save updated HTML
        update_html_content(job_id, slide_number, new_html)
        
        # Re-render screenshot
        async with async_playwright() as p:
            browser = await p.chromium.launch(args=['--no-sandbox', '--disable-dev-shm-usage'])
            page = await browser.new_page(viewport={"width": video_w, "height": video_h})
            await page.set_content(new_html)
            await page.wait_for_timeout(800)
            
            new_image_path = os.path.join(slides_dir, f"slide_{slide_number:03d}.png")
            await page.screenshot(path=new_image_path, type="png")
            await page.close()
            await browser.close()
        
        import time
        # Debounced re-sync of the slides bundle to Supabase Storage.
        # Collapses rapid successive edits into a single upload (~5s window).
        _schedule_slides_cache_debounced(job_id, x_user_id, x_project_id)
        return {
            "success": True,
            "preview_url": f"/outputs/{job_id}_slides/slide_{slide_number:03d}.png?t={int(time.time())}",
            "can_undo": True,
            "history_count": len(slide_history[job_id][slide_number])
        }

    except Exception as e:
        print(f"[Text Edit] Error: {e}")
        raise HTTPException(500, f"Failed to update text: {str(e)}")


# ========== Direct Slide HTML Editor ==========

@app.get("/api/slides/{job_id}/html/{slide_number}")
async def get_slide_html(job_id: str, slide_number: int):
    """Get raw HTML content of a slide for direct editing"""
    if job_id not in jobs:
        raise HTTPException(404, "Job not found")
    
    from services.ai_slide_generator import get_html_content
    
    html = get_html_content(job_id, slide_number)
    if not html:
        raise HTTPException(404, f"Slide {slide_number} not found")
    
    # Get dimensions for the iframe
    pipeline = get_or_create_pipeline(job_id)
    video_w, video_h = get_video_dimensions(getattr(pipeline, 'aspect_ratio', 'landscape'))
    
    return {
        "html": html,
        "width": video_w,
        "height": video_h
    }


class SlideHtmlUpdateRequest(BaseModel):
    html: str


@app.put("/api/slides/{job_id}/html/{slide_number}")
async def update_slide_html(
    job_id: str,
    slide_number: int,
    request: SlideHtmlUpdateRequest,
    x_gemini_key: Optional[str] = Header(None),
    x_gemini_model: Optional[str] = Header(None),
    x_user_id: Optional[str] = Header(None, alias="x-user-id"),
    x_project_id: Optional[str] = Header(None, alias="x-project-id"),
):
    """Update slide with directly edited HTML and re-render screenshot"""
    if job_id not in jobs:
        raise HTTPException(404, "Job not found")
    
    from services.ai_slide_generator import (
        get_html_content, update_html_content, fix_body_dimensions
    )
    from playwright.async_api import async_playwright
    
    old_html = get_html_content(job_id, slide_number)
    if not old_html:
        raise HTTPException(404, f"Slide {slide_number} not found")
    
    try:
        # Save to history before editing
        if job_id not in slide_history:
            slide_history[job_id] = {}
        if slide_number not in slide_history[job_id]:
            slide_history[job_id][slide_number] = []
        
        slides_dir = os.path.join(OUTPUT_DIR, f"{job_id}_slides")
        current_image_path = os.path.join(slides_dir, f"slide_{slide_number:03d}.png")
        backup_image_path = os.path.join(slides_dir, f"slide_{slide_number:03d}_v{len(slide_history[job_id][slide_number])}.png")
        if os.path.exists(current_image_path):
            shutil.copy(current_image_path, backup_image_path)
        
        slide_history[job_id][slide_number].append({
            "html": old_html,
            "image_path": backup_image_path,
            "timestamp": datetime.now().isoformat()
        })
        
        # Fix body dimensions
        pipeline = get_or_create_pipeline(job_id)
        video_w, video_h = get_video_dimensions(getattr(pipeline, 'aspect_ratio', 'landscape'))
        new_html = fix_body_dimensions(request.html, video_w, video_h)
        
        # Save updated HTML
        update_html_content(job_id, slide_number, new_html)
        
        # Re-render screenshot
        async with async_playwright() as p:
            browser = await p.chromium.launch(args=['--no-sandbox', '--disable-dev-shm-usage'])
            page = await browser.new_page(viewport={"width": video_w, "height": video_h})
            await page.set_content(new_html)
            await page.wait_for_timeout(800)
            
            new_image_path = os.path.join(slides_dir, f"slide_{slide_number:03d}.png")
            await page.screenshot(path=new_image_path, type="png")
            await page.close()
            await browser.close()
        
        import time
        _schedule_slides_cache_debounced(job_id, x_user_id, x_project_id)
        return {
            "success": True,
            "preview_url": f"/outputs/{job_id}_slides/slide_{slide_number:03d}.png?t={int(time.time())}",
            "can_undo": True,
            "history_count": len(slide_history[job_id][slide_number])
        }

    except Exception as e:
        print(f"[HTML Edit] Error: {e}")
        raise HTTPException(500, f"Failed to update HTML: {str(e)}")



class SlideFeedbackRequest(BaseModel):
    slide_number: int
    feedback: str
    feedback_type: str = "general"  # copy, layout, visual, general, add_image
    image_base64: Optional[str] = None  # Base64 encoded image data
    image_filename: Optional[str] = None  # Original filename
    facecam_position: Optional[str] = None  # PiP position for text avoidance
    facecam_size: Optional[int] = None  # PiP size in pixels


@app.post("/api/slides/{job_id}/feedback")
async def slide_feedback_endpoint(
    job_id: str,
    request: SlideFeedbackRequest,
    x_gemini_key: Optional[str] = Header(None),
    x_gemini_model: Optional[str] = Header(None),
    x_user_id: Optional[str] = Header(None, alias="x-user-id"),
    x_project_id: Optional[str] = Header(None, alias="x-project-id"),
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
        
        # Get video dimensions from pipeline
        pipeline = get_or_create_pipeline(job_id)
        video_w, video_h = get_video_dimensions(getattr(pipeline, 'aspect_ratio', 'landscape'))
        
        gemini_model = x_gemini_model or jobs.get(job_id, {}).get("gemini_model", "gemini-3-flash-preview")
        result = await regenerate_slide_with_feedback(
            job_id=job_id,
            slide_number=request.slide_number,
            feedback=request.feedback,
            feedback_type=request.feedback_type,
            gemini_key=x_gemini_key,
            image_base64=request.image_base64,
            image_filename=request.image_filename,
            video_width=video_w,
            video_height=video_h,
            facecam_position=request.facecam_position,
            facecam_size=request.facecam_size,
            model_name=gemini_model
        )
        
        if not result["success"]:
            raise HTTPException(500, result.get("error", "Regeneration failed"))
        
        # Add cache buster to URL and history count
        import time
        result["preview_url"] = f"{result['preview_url']}?t={int(time.time())}"
        result["history_count"] = len(slide_history.get(job_id, {}).get(slide_num, []))
        
        _schedule_slides_cache_debounced(job_id, x_user_id, x_project_id)
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


class ImageRegenerateRequest(BaseModel):
    slide_number: int
    feedback: str  # e.g., "もっと明るく", "キャラクターを増やして"


@app.post("/api/slides/{job_id}/regenerate-image")
async def regenerate_image_endpoint(
    job_id: str,
    request: ImageRegenerateRequest,
    x_gemini_key: Optional[str] = Header(None),
    x_gemini_model: Optional[str] = Header(None),
    x_user_id: Optional[str] = Header(None, alias="x-user-id"),
    x_project_id: Optional[str] = Header(None, alias="x-project-id"),
):
    """Regenerate only the AI-generated illustration for a specific slide"""
    if job_id not in jobs:
        raise HTTPException(404, "Job not found")

    try:
        from services.ai_slide_generator import regenerate_slide_illustration

        # Get video dimensions from pipeline
        pipeline = get_or_create_pipeline(job_id)
        video_w, video_h = get_video_dimensions(getattr(pipeline, 'aspect_ratio', 'landscape'))

        gemini_model = x_gemini_model or jobs.get(job_id, {}).get("gemini_model", "gemini-3-flash-preview")
        result = await regenerate_slide_illustration(
            job_id=job_id,
            slide_number=request.slide_number,
            feedback=request.feedback,
            gemini_key=x_gemini_key,
            video_width=video_w,
            video_height=video_h,
            model_name=gemini_model
        )
        
        if not result["success"]:
            raise HTTPException(500, result.get("error", "Image regeneration failed"))
        
        # Add cache buster to URL
        import time
        result["preview_url"] = f"{result['preview_url']}?t={int(time.time())}"
        
        _schedule_slides_cache_debounced(job_id, x_user_id, x_project_id)
        return {
            "job_id": job_id,
            **result,
            "message": f"スライド {request.slide_number} の画像を再生成しました"
        }

    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(500, f"画像再生成エラー: {str(e)}")

@app.post("/api/slides/{job_id}/undo/{slide_number}")
async def undo_slide_endpoint(
    job_id: str,
    slide_number: int,
    x_user_id: Optional[str] = Header(None, alias="x-user-id"),
    x_project_id: Optional[str] = Header(None, alias="x-project-id"),
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
        _schedule_slides_cache_debounced(job_id, x_user_id, x_project_id)

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

    # Populate _slide_data_cache so post-restore slide edits work.
    # Hybrid slides have no AI-generated HTML (the "slide" is the user's own
    # image), but the cache entry is still required so get_slide_data() doesn't
    # return None. Strategy is minimal; slides carry just the index + content.
    try:
        from services.ai_slide_generator import save_slide_data
        hybrid_slides = [
            {"number": i + 1, "content": c if isinstance(c, str) else str(c)}
            for i, c in enumerate(result.get("slide_contents", []))
        ]
        save_slide_data(
            job_id,
            hybrid_slides,
            {"mode": "hybrid", "file_type": file_type, "slide_count": result["slide_count"]},
        )
    except Exception as e:
        print(f"[UploadSlides] save_slide_data failed (non-fatal): {e}")

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


# ========== Video Settings (Face Cam & Aspect Ratio) ==========

class VideoSettingsRequest(BaseModel):
    aspect_ratio: Optional[str] = None  # "landscape" or "portrait"
    facecam_position: Optional[str] = None  # top-left, top-right, bottom-left, bottom-right
    facecam_size: Optional[int] = None  # 150, 200, 280


@app.get("/api/aspect-ratios")
async def get_aspect_ratios():
    """Get available aspect ratio presets"""
    return {"presets": ASPECT_RATIO_PRESETS}


@app.post("/api/settings/{job_id}")
async def update_video_settings(job_id: str, settings: VideoSettingsRequest):
    """Update video settings (aspect ratio, face cam position/size)"""
    pipeline = get_or_create_pipeline(job_id)
    
    if settings.aspect_ratio and settings.aspect_ratio in ASPECT_RATIO_PRESETS:
        pipeline.aspect_ratio = settings.aspect_ratio
        print(f"[Settings] Aspect ratio set to: {settings.aspect_ratio}")
    
    if settings.facecam_position:
        pipeline.facecam_position = settings.facecam_position
        print(f"[Settings] Face cam position set to: {settings.facecam_position}")
    
    if settings.facecam_size:
        pipeline.facecam_size = settings.facecam_size
        print(f"[Settings] Face cam size set to: {settings.facecam_size}px")
    
    return {
        "job_id": job_id,
        "aspect_ratio": pipeline.aspect_ratio,
        "facecam_position": pipeline.facecam_position,
        "facecam_size": pipeline.facecam_size,
        "facecam_video": pipeline.facecam_video_path is not None
    }


@app.post("/api/upload-facecam/{job_id}")
async def upload_facecam(job_id: str, file: UploadFile = File(...)):
    """Upload face cam video for PiP overlay"""
    pipeline = get_or_create_pipeline(job_id)
    
    allowed_ext = [".mp4", ".mov", ".webm", ".avi", ".mkv"]
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in allowed_ext:
        raise HTTPException(400, f"対応形式: MP4, MOV, WebM, AVI, MKV")
    
    # Save face cam video
    facecam_path = os.path.join(UPLOAD_DIR, f"{job_id}_facecam{ext}")
    with open(facecam_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    
    pipeline.facecam_video_path = facecam_path
    print(f"[FaceCam] Uploaded: {facecam_path}")
    
    return {
        "job_id": job_id,
        "facecam_path": facecam_path,
        "message": "顔カメラ動画をアップロードしました"
    }


@app.delete("/api/facecam/{job_id}")
async def delete_facecam(job_id: str):
    """Remove face cam video from job"""
    pipeline = get_or_create_pipeline(job_id)
    
    if pipeline.facecam_video_path and os.path.exists(pipeline.facecam_video_path):
        os.remove(pipeline.facecam_video_path)
    
    pipeline.facecam_video_path = None
    print(f"[FaceCam] Removed for job {job_id}")
    
    return {"job_id": job_id, "message": "顔カメラ動画を削除しました"}


# ========== STEP 10: Generate Video ==========

_VIDEO_CACHE_RETRY_DELAYS_SEC = (2, 8, 30)  # exponential backoff between retry attempts


async def _cache_video_to_storage(
    local_mp4: str,
    user_id: str,
    project_id: str,
    job_id: Optional[str] = None,
):
    """Upload the generated video to Supabase Storage for the 48h cache,
    then PATCH projects.video_storage_path / video_cached_at.

    Runs as a background task (fire-and-forget from caller's perspective)
    so video generation latency isn't impacted, but internally retries up to
    3 times with exponential backoff on transient errors. Every attempt is
    logged with a structured `[VideoCache]` prefix so failures are auditable
    in Railway logs (the previous version silently swallowed failures, which
    was the root cause of the "video disappears after 48h" reports).

    `jobs[job_id]["video_cache_status"]` is updated when known so other
    endpoints can report cache health.
    """
    import asyncio as _asyncio
    import httpx as _httpx
    from datetime import timezone as _tz

    def _set_status(status: str, detail: str = ""):
        if job_id and job_id in jobs:
            jobs[job_id]["video_cache_status"] = status
            if detail:
                jobs[job_id]["video_cache_detail"] = detail

    try:
        from services.supabase_storage import (
            upload_video, is_configured, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY,
        )
    except Exception as e:
        print(f"[VideoCache] ✗ import failed for project={project_id}: {e}")
        _set_status("error", "import_failed")
        return

    if not is_configured():
        print(f"[VideoCache] skipped (Supabase not configured) for project={project_id}")
        _set_status("skipped", "not_configured")
        return

    _set_status("uploading")
    last_err: Optional[str] = None

    for attempt, delay_before in enumerate(((0,) + _VIDEO_CACHE_RETRY_DELAYS_SEC)):
        if delay_before:
            await _asyncio.sleep(delay_before)
        attempt_num = attempt + 1
        try:
            storage_path = await upload_video(local_mp4, user_id, project_id)
            if not storage_path:
                last_err = "upload_returned_none"
                print(f"[VideoCache] attempt {attempt_num} ✗ upload returned None for project={project_id}")
                continue

            now_iso = datetime.now(_tz.utc).isoformat()
            async with _httpx.AsyncClient(timeout=30.0) as client:
                r = await client.patch(
                    f"{SUPABASE_URL}/rest/v1/projects",
                    params={"id": f"eq.{project_id}"},
                    headers={
                        "apikey": SUPABASE_SERVICE_ROLE_KEY,
                        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
                        "Content-Type": "application/json",
                        "Prefer": "return=minimal",
                    },
                    json={"video_storage_path": storage_path, "video_cached_at": now_iso},
                )
            if r.status_code in (200, 204):
                print(f"[VideoCache] ✓ attempt {attempt_num}: cached {storage_path} for project={project_id}")
                _set_status("cached", storage_path)
                return
            else:
                last_err = f"patch_status_{r.status_code}"
                print(
                    f"[VideoCache] attempt {attempt_num} ✗ PATCH failed for project={project_id}: "
                    f"{r.status_code} — {r.text[:200]}"
                )
                # Non-2xx PATCH usually means project_id wrong / RLS blocked / bad payload.
                # Retrying won't help for those cases — bail early instead of burning attempts.
                if r.status_code in (400, 403, 404, 422):
                    break
        except Exception as e:
            last_err = f"{type(e).__name__}: {e}"
            print(f"[VideoCache] attempt {attempt_num} ✗ exception for project={project_id}: {last_err}")

    print(
        f"[VideoCache] ✗ GAVE UP after {len(_VIDEO_CACHE_RETRY_DELAYS_SEC) + 1} attempts for "
        f"project={project_id}: last_err={last_err}. Video stays playable from local disk; "
        f"DB cache columns remain NULL so next restore will prompt regeneration."
    )
    _set_status("failed", last_err or "unknown")


# ---------------------------------------------------------------------------
# Slides Supabase Storage cache (permanent — no retention window)
# ---------------------------------------------------------------------------
# Slides are the core project artifact, so we upload PNGs + slide_data.json
# to Supabase Storage and keep them for the lifetime of the project. This
# keeps Railway redeploys from wiping users' slide previews.
#
# Design choice: generation-end uploads fire immediately (user is watching);
# edit-endpoint uploads go through a 5-second debounce so rapid edits don't
# thrash the bucket. Debounce state is project-scoped, not job-scoped, because
# restore creates a new job_id but keeps the same project_id.

_SLIDES_CACHE_RETRY_DELAYS_SEC = (2, 8, 30)
_SLIDES_CACHE_DEBOUNCE_SEC = 5.0
_slides_cache_debounce: Dict[str, asyncio.Task] = {}


async def _cache_slides_to_storage(
    job_id: str,
    user_id: str,
    project_id: str,
):
    """Upload the on-disk slides dir (PNG + slide_data.json) for this job to
    Supabase Storage, then PATCH projects.slides_storage_prefix /
    slides_cached_at. Retries transient errors up to 3 times. Failures are
    logged with a [SlidesCache] prefix and tracked in
    jobs[job_id]["slides_cache_status"] for diagnostics.

    Runs as a background task — never blocks the user's generate/edit
    response, never raises.
    """
    import httpx as _httpx
    from datetime import timezone as _tz

    slides_dir = os.path.join(OUTPUT_DIR, f"{job_id}_slides")

    def _set_status(status: str, detail: str = ""):
        if job_id in jobs:
            jobs[job_id]["slides_cache_status"] = status
            if detail:
                jobs[job_id]["slides_cache_detail"] = detail

    try:
        from services.supabase_storage import (
            upload_slides_bundle, is_configured, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY,
        )
    except Exception as e:
        print(f"[SlidesCache] ✗ import failed for project={project_id}: {e}")
        _set_status("error", "import_failed")
        return

    if not is_configured():
        print(f"[SlidesCache] skipped (Supabase not configured) for project={project_id}")
        _set_status("skipped", "not_configured")
        return

    if not os.path.isdir(slides_dir):
        print(f"[SlidesCache] skipped: slides_dir missing for job={job_id}")
        _set_status("skipped", "no_slides_dir")
        return

    _set_status("uploading")
    last_err: Optional[str] = None

    for attempt, delay_before in enumerate(((0,) + _SLIDES_CACHE_RETRY_DELAYS_SEC)):
        if delay_before:
            await asyncio.sleep(delay_before)
        attempt_num = attempt + 1
        try:
            prefix = await upload_slides_bundle(slides_dir, user_id, project_id)
            if not prefix:
                last_err = "upload_returned_none"
                print(f"[SlidesCache] attempt {attempt_num} ✗ upload returned None for project={project_id}")
                continue

            now_iso = datetime.now(_tz.utc).isoformat()
            async with _httpx.AsyncClient(timeout=30.0) as client:
                r = await client.patch(
                    f"{SUPABASE_URL}/rest/v1/projects",
                    params={"id": f"eq.{project_id}"},
                    headers={
                        "apikey": SUPABASE_SERVICE_ROLE_KEY,
                        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
                        "Content-Type": "application/json",
                        "Prefer": "return=minimal",
                    },
                    json={"slides_storage_prefix": prefix, "slides_cached_at": now_iso},
                )
            if r.status_code in (200, 204):
                print(f"[SlidesCache] ✓ attempt {attempt_num}: cached {prefix} for project={project_id}")
                _set_status("cached", prefix)
                return
            else:
                last_err = f"patch_status_{r.status_code}"
                print(
                    f"[SlidesCache] attempt {attempt_num} ✗ PATCH failed for project={project_id}: "
                    f"{r.status_code} — {r.text[:200]}"
                )
                # Same reasoning as video cache: retrying a 4xx won't help.
                if r.status_code in (400, 403, 404, 422):
                    break
        except Exception as e:
            last_err = f"{type(e).__name__}: {e}"
            print(f"[SlidesCache] attempt {attempt_num} ✗ exception for project={project_id}: {last_err}")

    print(
        f"[SlidesCache] ✗ GAVE UP after {len(_SLIDES_CACHE_RETRY_DELAYS_SEC) + 1} attempts for "
        f"project={project_id}: last_err={last_err}. Slides remain on local disk; "
        f"next restore will fall back to local copy or prompt regeneration."
    )
    _set_status("failed", last_err or "unknown")


def _schedule_slides_cache_immediate(job_id: str, user_id: Optional[str], project_id: Optional[str]):
    """Fire-and-forget, no debounce. Called right after slide generation —
    the user is actively watching, so we want the "saved" state visible ASAP.
    """
    if not user_id or not project_id:
        # Anonymous / legacy session — cache silently skipped
        print(f"[SlidesCache] skipped for job={job_id}: missing user_id={bool(user_id)} project_id={bool(project_id)}")
        return
    if job_id in jobs:
        jobs[job_id]["slides_cache_status"] = "pending"
    asyncio.create_task(_cache_slides_to_storage(job_id, user_id, project_id))


def _schedule_slides_cache_debounced(
    job_id: str,
    user_id: Optional[str],
    project_id: Optional[str],
):
    """Called from slide-edit endpoints. Cancels any pending task for the
    same project_id and schedules a new one after _SLIDES_CACHE_DEBOUNCE_SEC.

    This avoids re-uploading 20 PNGs every time the user tweaks a single
    character in a slide. The penalty is that a crash during the debounce
    window loses the most recent edit from Storage — acceptable because
    (a) the edit is still on local disk for the current container, and
    (b) slide_data.json carries the HTML source, so next restore would
    regenerate a fresh PNG anyway.
    """
    if not user_id or not project_id:
        return

    key = project_id
    existing = _slides_cache_debounce.get(key)
    if existing and not existing.done():
        existing.cancel()

    async def _delayed():
        try:
            await asyncio.sleep(_SLIDES_CACHE_DEBOUNCE_SEC)
        except asyncio.CancelledError:
            return
        try:
            await _cache_slides_to_storage(job_id, user_id, project_id)
        finally:
            _slides_cache_debounce.pop(key, None)

    if job_id in jobs:
        jobs[job_id]["slides_cache_status"] = "pending"
    _slides_cache_debounce[key] = asyncio.create_task(_delayed())


@app.post("/api/generate-video/{job_id}")
async def generate_video(
    job_id: str,
    update: Optional[TimingUpdate] = None,
    x_user_id: Optional[str] = Header(None, alias="x-user-id"),
    x_project_id: Optional[str] = Header(None, alias="x-project-id"),
):
    """Step 10: Generate final video"""
    pipeline = get_or_create_pipeline(job_id)
    
    # === DEBUG: Log incoming request ===
    print(f"[Video] === generate_video called for {job_id} ===")
    print(f"[Video] update received: {update is not None}")
    if update:
        print(f"[Video] timing_map entries: {len(update.timing_map)}")
        for t in update.timing_map[:3]:
            print(f"  slide {t.get('slide_number')}: {t.get('start_time')}s - {t.get('end_time')}s")
        if len(update.timing_map) > 3:
            print(f"  ... and {len(update.timing_map) - 3} more")
    
    print(f"[Video] pipeline.slide_images: {len(pipeline.slide_images)} items")
    print(f"[Video] pipeline.timing_map: {len(pipeline.timing_map)} items")
    
    jobs[job_id]["step"] = 10
    jobs[job_id]["status"] = "processing"
    
    # Auto-recover slide_images from filesystem if empty
    if not pipeline.slide_images:
        print(f"[Video] ⚠️ slide_images is empty, attempting recovery from filesystem...")
        slides_dir = os.path.join(OUTPUT_DIR, f"{job_id}_slides")
        if os.path.isdir(slides_dir):
            import glob
            slide_files = sorted(glob.glob(os.path.join(slides_dir, "slide_*.png")))
            if slide_files:
                pipeline.slide_images = slide_files
                print(f"[Video] ✓ Recovered {len(slide_files)} slide images from {slides_dir}")
            else:
                print(f"[Video] ✗ No slide_*.png files found in {slides_dir}")
        else:
            print(f"[Video] ✗ Slides directory not found: {slides_dir}")
    
    if not pipeline.slide_images:
        raise HTTPException(500, "スライド画像が見つかりません。スライドを先に生成してください。")

    # Refuse to generate a broken video if the audio is just a placeholder.
    # Placeholder audio is created by restore-project when the original
    # audio file is no longer on disk (e.g. after Railway redeploy).
    # Rather than producing a silent 60s video that looks "complete",
    # return a clear error so the frontend can prompt the user to re-upload.
    if pipeline.audio_path and "_placeholder.wav" in pipeline.audio_path and os.path.exists(pipeline.audio_path):
        raise HTTPException(
            status_code=409,
            detail={
                "error_code": "audio_placeholder",
                "message": "音声ファイルが失われています。プロジェクト再開後の動画生成には音声の再アップロードが必要です。",
                "action": "reupload_audio",
            },
        )

    # If no timing provided and no timing_map exists, generate it from outline
    if not update and not pipeline.timing_map:
        print("[Video] Generating timing map from outline...")
        await pipeline.step_map_slides()
    
    edited = update.timing_map if update else None
    
    # Use BGM-mixed audio if available, otherwise use original/trimmed
    job = jobs.get(job_id, {})
    mixed_path = job.get("mixed_path")
    
    if mixed_path and os.path.exists(mixed_path):
        print(f"[Video] Using BGM-mixed audio: {mixed_path}")
        audio_to_use = mixed_path
    else:
        # Check for trimmed version
        base, ext = os.path.splitext(pipeline.audio_path)
        trimmed_path = f"{base}_trimmed{ext}"
        if os.path.exists(trimmed_path):
            print(f"[Video] Using trimmed audio: {trimmed_path}")
            audio_to_use = trimmed_path
        else:
            print(f"[Video] Using original audio: {pipeline.audio_path}")
            audio_to_use = pipeline.audio_path
    
    print(f"[Video] Calling step_generate_video with edited={'YES' if edited else 'NO'}, slides={len(pipeline.slide_images)}")
    result = await pipeline.step_generate_video(edited, audio_override=audio_to_use)
    
    jobs[job_id]["status"] = "completed"
    jobs[job_id]["video_url"] = result["video_url"]

    # Background 48h Supabase Storage cache (with internal retry). Failures
    # are logged loudly via [VideoCache] prefix and tracked in
    # jobs[job_id]["video_cache_status"] for diagnosis. We don't await here
    # because a failed cache shouldn't block the user from playing/downloading
    # the video that's already on local disk.
    if x_user_id and x_project_id:
        local_mp4 = os.path.join(OUTPUT_DIR, f"{job_id}.mp4")
        if os.path.exists(local_mp4):
            jobs[job_id]["video_cache_status"] = "pending"
            asyncio.create_task(
                _cache_video_to_storage(local_mp4, x_user_id, x_project_id, job_id=job_id)
            )
        else:
            print(f"[VideoCache] ✗ cannot cache: local file missing at {local_mp4}")
            jobs[job_id]["video_cache_status"] = "skipped"
            jobs[job_id]["video_cache_detail"] = "local_file_missing"
    elif x_user_id is None or x_project_id is None:
        # Anonymous/legacy session — caching silently skipped, but log it
        # so we know how often this path is hit.
        print(f"[VideoCache] skipped for job={job_id}: missing user_id={bool(x_user_id)} project_id={bool(x_project_id)}")

    # Get timing map for frontend timeline editor
    timing_map_data = None
    if edited:
        # ユーザー編集済み: そのまま返す（すでに実際の切替時間）
        timing_map_data = edited
    elif pipeline.timing_map:
        # 初回生成: +10秒遅延を適用した「実際の切替時間」を返す
        # フロントの表示とユーザー編集を正確にするため
        from services.video_composer import get_audio_duration
        audio_dur = get_audio_duration(audio_to_use)
        TRANSITION_DELAY = 10.0
        raw = sorted(pipeline.timing_map, key=lambda x: x.get("slide_number", 0))
        adjusted = []
        for idx, t in enumerate(raw):
            if idx == 0:
                s = 0.0
            else:
                s = min(t.get("start_time", 0) + TRANSITION_DELAY, audio_dur)
            if idx == len(raw) - 1:
                e = audio_dur
            else:
                next_start = raw[idx + 1].get("start_time", 0)
                e = min(next_start + TRANSITION_DELAY, audio_dur)
            adjusted.append({
                "slide_number": t.get("slide_number", idx + 1),
                "start_time": round(s, 1),
                "end_time": round(e, 1),
                "match_reason": t.get("match_reason", "")
            })
        timing_map_data = adjusted
    
    print(f"[Video] === generate_video completed, returning timing_map: {len(timing_map_data) if timing_map_data else 0} items ===")
    
    response = {
        "job_id": job_id,
        "step": 10,
        "status": "completed",
        "video_url": result["video_url"]
    }
    
    if timing_map_data:
        response["timing_map"] = timing_map_data
    
    return response


# ========== Project Restore ==========

def _create_silent_wav(path: str, duration: float = 60.0):
    """Create a valid silent WAV file with the given duration.
    Uses raw PCM format: 16-bit, mono, 44100 Hz."""
    import struct
    sample_rate = 44100
    num_channels = 1
    bits_per_sample = 16
    num_samples = int(sample_rate * duration)
    data_size = num_samples * num_channels * (bits_per_sample // 8)

    with open(path, "wb") as f:
        # RIFF header
        f.write(b"RIFF")
        f.write(struct.pack("<I", 36 + data_size))  # file size - 8
        f.write(b"WAVE")
        # fmt chunk
        f.write(b"fmt ")
        f.write(struct.pack("<I", 16))  # chunk size
        f.write(struct.pack("<H", 1))   # PCM format
        f.write(struct.pack("<H", num_channels))
        f.write(struct.pack("<I", sample_rate))
        f.write(struct.pack("<I", sample_rate * num_channels * bits_per_sample // 8))  # byte rate
        f.write(struct.pack("<H", num_channels * bits_per_sample // 8))  # block align
        f.write(struct.pack("<H", bits_per_sample))
        # data chunk
        f.write(b"data")
        f.write(struct.pack("<I", data_size))
        # Silence = all zeros
        f.write(b"\x00" * data_size)


class RestoreProjectRequest(BaseModel):
    """Request body for restoring a project from saved state"""
    transcript: str = ""
    polished_transcript: str = ""
    outline: Optional[dict] = None
    polished_outline: Optional[dict] = None
    timing_map: Optional[list] = None
    aspect_ratio: Optional[str] = "landscape"
    step: Optional[int] = None
    slide_previews: Optional[List[str]] = None  # Slide preview URLs from frontend
    audio_storage_path: Optional[str] = None  # Phase 2: Supabase Storage path for audio
    # 48h video cache — present if the project's last generation was cached.
    # video_expired vs video_recovered is determined server-side by comparing
    # video_cached_at against a 48h window.
    video_storage_path: Optional[str] = None
    video_cached_at: Optional[str] = None  # ISO8601 UTC
    # Signal that the frontend's DB row had a video_url (i.e. the user reached
    # step 10 at some point). Needed because the cache-write race can leave
    # the DB in a state where video_url is set but video_storage_path is null
    # (fire-and-forget upload hadn't landed before the user navigated away).
    # When step==10 and this is non-empty but video_storage_path is falsy,
    # we treat the project as "video expired" so the UI rewinds + banners.
    video_url_hint: Optional[str] = None
    # Persistent slide cache prefix (see supabase_migration_slides_storage.sql).
    # Present whenever slides have ever been successfully uploaded. Used as a
    # fallback when the local old_job_id slides dir is gone (Railway redeploy).
    slides_storage_prefix: Optional[str] = None

@app.post("/api/restore-project")
async def restore_project(
    request: RestoreProjectRequest,
    x_openai_key: Optional[str] = Header(None),
    x_gemini_key: Optional[str] = Header(None),
    x_gemini_model: Optional[str] = Header(None),
    x_openrouter_key: Optional[str] = Header(None),
):
    """Restore a pipeline from saved project data (no audio file needed for slide generation)"""
    import re as _re
    import glob as _glob

    job_id = str(uuid.uuid4())

    # --- Extract old_job_id from slide preview URLs ---
    old_job_id = None
    if request.slide_previews and len(request.slide_previews) > 0:
        old_job_match = _re.search(
            r'/outputs/([0-9a-f-]{36})_slides/',
            request.slide_previews[0]
        )
        if old_job_match:
            old_job_id = old_job_match.group(1)

    # --- Recover audio file (priority: Supabase Storage → old job_id copy → placeholder) ---
    audio_path = None
    audio_recovered = False  # True if real user audio was found; False if placeholder

    # Priority 1: Supabase Storage (Phase 2 — survives Railway redeploys)
    #
    # We download TWO files when they exist:
    #   - the ORIGINAL upload under `{user}/{project}/audio.{ext}` → placed at
    #     `{job_id}{ext}` so pipeline.audio_path points at the original
    #   - the POST-CLEANUP version under `{user}/{project}/audio_processed.{ext}`
    #     → placed at `{job_id}_trimmed{ext}` so the video generator's
    #     existing "prefer _trimmed" logic picks it up and the regenerated
    #     video matches the user's cleanup duration (not the raw length).
    #
    # If processed is absent (old project or cleanup was skipped), we just
    # use the original — the video will match the original audio length,
    # which is the existing legacy behavior.
    if request.audio_storage_path:
        try:
            from services.supabase_storage import download_audio as storage_download, storage_path_ext
            ext = storage_path_ext(request.audio_storage_path)
            candidate = os.path.join(UPLOAD_DIR, f"{job_id}{ext}")
            ok = await storage_download(request.audio_storage_path, candidate)
            if ok and os.path.exists(candidate) and os.path.getsize(candidate) > 100:
                audio_path = candidate
                audio_recovered = True
                print(f"[Restore] ✓ Recovered audio from Supabase Storage: {request.audio_storage_path}")

                # Also try to fetch the processed (post-cleanup) version.
                # Path convention: replace `/audio.` with `/audio_processed.`.
                if "/audio." in request.audio_storage_path:
                    processed_path = request.audio_storage_path.replace(
                        "/audio.", "/audio_processed.", 1
                    )
                    trimmed_candidate = os.path.join(UPLOAD_DIR, f"{job_id}_trimmed{ext}")
                    try:
                        proc_ok = await storage_download(processed_path, trimmed_candidate)
                        if (
                            proc_ok
                            and os.path.exists(trimmed_candidate)
                            and os.path.getsize(trimmed_candidate) > 100
                        ):
                            print(
                                f"[Restore] ✓ Recovered processed audio from Supabase Storage: "
                                f"{processed_path} → {os.path.basename(trimmed_candidate)}"
                            )
                        else:
                            # Not an error — processed version is optional. Most common reason
                            # is a project that was transcribed before this change landed, or
                            # one where cleanup was disabled so nothing got uploaded.
                            print(f"[Restore] (no processed audio at {processed_path}, using original length)")
                    except Exception as e:
                        print(f"[Restore] processed audio download failed (ignored): {e}")
        except Exception as e:
            print(f"[Restore] Storage download failed (will fall back): {e}")

    # Priority 2: Old job_id on same Railway container (Phase 1 fallback)
    if not audio_path and old_job_id:
        # Try common audio extensions in the old job's uploads
        for ext in [".wav", ".mp3", ".m4a"]:
            candidate = os.path.join(UPLOAD_DIR, f"{old_job_id}{ext}")
            if os.path.exists(candidate):
                # Copy to new job_id so pipeline references are correct
                new_audio = os.path.join(UPLOAD_DIR, f"{job_id}{ext}")
                shutil.copy2(candidate, new_audio)
                audio_path = new_audio
                audio_recovered = True
                print(f"[Restore] ✓ Recovered audio from {old_job_id}{ext} → {job_id}{ext}")
                break
            # Also try _trimmed variant
            trimmed = os.path.join(UPLOAD_DIR, f"{old_job_id}_trimmed{ext}")
            if os.path.exists(trimmed):
                new_audio = os.path.join(UPLOAD_DIR, f"{job_id}_trimmed{ext}")
                shutil.copy2(trimmed, new_audio)
                # Also need a base audio — use trimmed as base too
                base_audio = os.path.join(UPLOAD_DIR, f"{job_id}{ext}")
                shutil.copy2(trimmed, base_audio)
                audio_path = base_audio
                audio_recovered = True
                print(f"[Restore] ✓ Recovered trimmed audio from {old_job_id} → {job_id}")
                break

    if not audio_path:
        # Fallback: create a PLACEHOLDER WAV (marked by filename suffix).
        # The video-generation endpoint will refuse to proceed with a placeholder
        # and prompt the user to re-upload audio. We create a valid WAV so the
        # pipeline doesn't crash on construction, but we mark it clearly.
        total_duration = 60.0
        if request.timing_map:
            max_end = max(
                (t.get("end_time", 0) for t in request.timing_map),
                default=60.0
            )
            if max_end > 0:
                total_duration = max_end + 1.0

        audio_path = os.path.join(UPLOAD_DIR, f"{job_id}_placeholder.wav")
        _create_silent_wav(audio_path, total_duration)
        audio_recovered = False
        print(f"[Restore] ⚠ No old audio found, created PLACEHOLDER WAV ({total_duration:.1f}s) - user must re-upload")

    # --- Recover video (48h Supabase Storage cache) ---
    # UI-facing: we tell users "videos are NOT saved". This silent cache is a
    # recovery mechanism only; if it expired or is missing, we rewind the step
    # to 9 so the frontend renders the "動画を再生成" flow.
    video_recovered = False
    video_url_out: Optional[str] = None
    video_expired = False
    if request.video_storage_path:
        from datetime import timezone as _tz
        age_ok = False
        if request.video_cached_at:
            try:
                cached = datetime.fromisoformat(request.video_cached_at.replace("Z", "+00:00"))
                age_hours = (datetime.now(_tz.utc) - cached).total_seconds() / 3600
                age_ok = age_hours <= 48
            except Exception as e:
                print(f"[Restore] Could not parse video_cached_at={request.video_cached_at!r}: {e}")

        if age_ok:
            try:
                from services.supabase_storage import download_video as storage_download_video
                candidate_mp4 = os.path.join(OUTPUT_DIR, f"{job_id}.mp4")
                if await storage_download_video(request.video_storage_path, candidate_mp4):
                    if os.path.exists(candidate_mp4) and os.path.getsize(candidate_mp4) > 1024:
                        video_recovered = True
                        video_url_out = f"/video/{job_id}"
                        print(f"[Restore] ✓ Recovered video from Supabase Storage: {request.video_storage_path}")
                    else:
                        print(f"[Restore] ⚠ Video downloaded but file looks empty/corrupt: {candidate_mp4}")
            except Exception as e:
                print(f"[Restore] Video download failed (will fall through to regenerate): {e}")

        if not video_recovered:
            # Cache was present but unusable (expired or download failed)
            video_expired = True

    # Race-window fallback: the user reached step 10 (video_url_hint is set)
    # but no storage path landed in the DB. This happens when the background
    # cache upload hadn't completed before the user navigated away, or when
    # it silently failed. Either way the DB's video_url points at an old
    # job_id whose MP4 is gone — so we treat this identically to an expired
    # cache, letting the frontend rewind + show the "再生成してください" banner.
    if (
        not video_recovered
        and not video_expired
        and request.step == 10
        and request.video_url_hint
    ):
        video_expired = True
        print(
            f"[Restore] ⚠ step=10 with video_url_hint={request.video_url_hint!r} "
            f"but no storage path — marking expired (cache-write race or failure)"
        )

    # Initialize pipeline with saved state
    pipeline = get_or_create_pipeline(job_id, audio_path)
    pipeline.raw_transcript = request.transcript
    pipeline.polished_transcript = request.polished_transcript
    pipeline.raw_outline = request.outline
    pipeline.polished_outline = request.polished_outline
    if request.timing_map:
        pipeline.timing_map = request.timing_map
    if request.aspect_ratio:
        pipeline.aspect_ratio = request.aspect_ratio

    # Determine restore step: use frontend-provided step if valid, otherwise default to 5
    restore_step = 5
    if request.step is not None and 1 <= request.step <= 10:
        restore_step = request.step

    # NOTE: we intentionally do NOT coerce restore_step when the video cache is
    # expired. The frontend knows the workflow_mode (hybrid vs full-ai) and
    # rewinds to the appropriate "slides complete" step itself: step 8 for
    # hybrid, step 6 for full-ai. Backend just signals `video_expired`.

    # Initialize job tracking with API keys
    jobs[job_id] = {
        "id": job_id,
        "step": restore_step,
        "status": "restored",
        "created_at": datetime.now().isoformat(),
        "gemini_key": x_gemini_key or "",
        "gemini_model": x_gemini_model or "gemini-3-flash-preview",
        "openrouter_key": x_openrouter_key or "",
    }
    if video_recovered and video_url_out:
        jobs[job_id]["video_url"] = video_url_out
        jobs[job_id]["status"] = "completed"
    job_timestamps[job_id] = datetime.now()

    # Store API keys for this job
    api_keys[job_id] = {
        "openai": x_openai_key or "",
        "gemini": x_gemini_key or "",
    }

    # --- Recover slide images + slide metadata from old job ---
    # Slide editing (feedback endpoint) needs the in-memory _slide_data_cache
    # populated for the NEW job_id. We persist that cache to JSON alongside
    # the images and copy+rehydrate it here so post-restore edits work.
    recovered_slides = 0
    if old_job_id:
        old_slides_dir = os.path.join(OUTPUT_DIR, f"{old_job_id}_slides")
        new_slides_dir = os.path.join(OUTPUT_DIR, f"{job_id}_slides")

        if os.path.isdir(old_slides_dir):
            os.makedirs(new_slides_dir, exist_ok=True)
            slide_files = sorted(_glob.glob(os.path.join(old_slides_dir, "slide_*.png")))
            for src in slide_files:
                dst = os.path.join(new_slides_dir, os.path.basename(src))
                shutil.copy2(src, dst)
                pipeline.slide_images.append(dst)
            recovered_slides = len(slide_files)
            print(f"[Restore] ✓ Copied {recovered_slides} slide images from {old_job_id} → {job_id}")

            # Copy the slide_data.json (slides metadata + strategy + HTML contents)
            # so the feedback/edit endpoints can find it under the new job_id.
            old_slide_data = os.path.join(old_slides_dir, "slide_data.json")
            if os.path.exists(old_slide_data):
                new_slide_data = os.path.join(new_slides_dir, "slide_data.json")
                try:
                    shutil.copy2(old_slide_data, new_slide_data)
                    from services.ai_slide_generator import load_slide_data_from_disk
                    if load_slide_data_from_disk(job_id):
                        print(f"[Restore] ✓ Recovered slide_data.json and rehydrated cache for {job_id}")
                    else:
                        print(f"[Restore] ⚠ Copied slide_data.json but failed to rehydrate cache")
                except Exception as e:
                    print(f"[Restore] ⚠ Failed to copy slide_data.json: {e}")
            else:
                # Older jobs predate disk persistence — edits on those restores won't work
                # until the user regenerates slides. Fine as a graceful degradation.
                print(f"[Restore] ⚠ No slide_data.json in old job (pre-persistence job)")
        else:
            print(f"[Restore] ⚠ Old slides dir not found: {old_slides_dir}")
    elif request.slide_previews:
        print(f"[Restore] ⚠ Could not parse old job_id from slide_previews: {request.slide_previews[0][:80]}")

    # Fallback: if the local old_job_id copy produced no slides AND the project
    # has a persistent Supabase Storage prefix (Sprint 2), download the bundle
    # from Storage. This is the path that rescues projects after a Railway
    # redeploy. See services/supabase_storage.download_slides_bundle.
    if recovered_slides == 0 and request.slides_storage_prefix:
        new_slides_dir = os.path.join(OUTPUT_DIR, f"{job_id}_slides")
        try:
            from services.supabase_storage import download_slides_bundle as _dl_slides
            downloaded = await _dl_slides(request.slides_storage_prefix, new_slides_dir)
        except Exception as e:
            print(f"[Restore] Slides storage download raised: {type(e).__name__}: {e}")
            downloaded = 0

        if downloaded > 0:
            png_files = sorted(_glob.glob(os.path.join(new_slides_dir, "slide_*.png")))
            for p in png_files:
                pipeline.slide_images.append(p)
            recovered_slides = len(png_files)
            print(f"[Restore] ✓ Recovered {recovered_slides} slides from Supabase Storage "
                  f"({request.slides_storage_prefix})")

            # Rehydrate slide_data.json cache so feedback/edit endpoints work.
            # download_slides_bundle would have placed slide_data.json into
            # new_slides_dir if it existed in Storage.
            try:
                from services.ai_slide_generator import load_slide_data_from_disk
                if load_slide_data_from_disk(job_id):
                    print(f"[Restore] ✓ Rehydrated slide_data.json cache from Storage for {job_id}")
                else:
                    print(f"[Restore] ⚠ slide_data.json rehydration from Storage skipped or failed")
            except Exception as e:
                print(f"[Restore] ⚠ slide_data.json rehydration raised: {type(e).__name__}: {e}")
        else:
            print(f"[Restore] ⚠ No slides in Supabase Storage at {request.slides_storage_prefix}")

    # Build the authoritative slide_previews list for the NEW job_id.
    # IMPORTANT: this supersedes whatever the frontend had stored. The previous
    # approach relied on the frontend HEAD-checking saved URLs (which pointed at
    # the OLD job_id on potentially-recycled container disk), producing a flaky
    # "some 404, some 200" result → "4 slides became 2". Now we return the
    # ground truth from what was just copied into new_slides_dir.
    new_slides_dir_path = os.path.join(OUTPUT_DIR, f"{job_id}_slides")
    restored_slide_previews: List[str] = []
    if os.path.isdir(new_slides_dir_path):
        for p in sorted(_glob.glob(os.path.join(new_slides_dir_path, "slide_*.png"))):
            restored_slide_previews.append(f"/outputs/{job_id}_slides/{os.path.basename(p)}")

    print(f"[Restore] Project restored as job {job_id} at step={restore_step} (has_gemini_key={bool(x_gemini_key)}, has_openrouter_key={bool(x_openrouter_key)}, slides={recovered_slides}, previews_returned={len(restored_slide_previews)}, audio={'recovered' if audio_recovered else 'placeholder'}, storage_restore={bool(request.slides_storage_prefix)})")

    return {
        "job_id": job_id,
        "status": "restored",
        "message": "Project restored successfully",
        "step": restore_step,  # may have been coerced down to 9 if video cache expired
        "slides_recovered": recovered_slides,
        "slide_previews": restored_slide_previews,  # Authoritative URLs under the new job_id
        "audio_recovered": audio_recovered,  # False if placeholder — frontend should prompt re-upload
        "video_recovered": video_recovered,
        "video_url": video_url_out,  # None if not recovered — frontend must regenerate
        "video_expired": video_expired,  # True only if project had a cache but it's gone
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


# ========== AI Support Chat ==========

class SupportChatRequest(BaseModel):
    message: str
    context: Optional[Dict[str, Any]] = None
    history: Optional[List[Dict[str, str]]] = None

# FAQ Knowledge Base - loaded from file
_faq_cache = {"content": None, "loaded_at": None}

def load_support_faq() -> str:
    """Load FAQ content from docs/support-faq.md with caching (refresh every 5 minutes)"""
    import time
    
    now = time.time()
    
    # Return cached content if fresh (within 5 minutes)
    if _faq_cache["content"] and _faq_cache["loaded_at"]:
        if now - _faq_cache["loaded_at"] < 300:  # 5 minutes
            return _faq_cache["content"]
    
    # Try to load from file
    faq_paths = [
        os.path.join(os.path.dirname(__file__), "..", "docs", "support-faq.md"),
        os.path.join(os.path.dirname(__file__), "docs", "support-faq.md"),
        "/app/docs/support-faq.md",  # Docker/Railway path
    ]
    
    for faq_path in faq_paths:
        try:
            if os.path.exists(faq_path):
                with open(faq_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    _faq_cache["content"] = content
                    _faq_cache["loaded_at"] = now
                    print(f"[Support FAQ] Loaded from {faq_path}")
                    return content
        except Exception as e:
            print(f"[Support FAQ] Failed to load {faq_path}: {e}")
    
    print("[Support FAQ] No FAQ file found, using fallback")
    return ""

SUPPORT_SYSTEM_PROMPT = """あなたはVoiSlide Movieのサポートアシスタントです。
ユーザーがエラーや問題に遭遇した際に、丁寧で分かりやすいサポートを提供してください。

## VoiSlide Movieについて
VoiSlide Movieは音声からスライド動画を自動生成するサービスです。
主なステップ:
1. 音声アップロード
2. 文字起こし (OpenAI Whisper)
3. ブラッシュアップ (Gemini)
4. アウトライン生成 (Gemini)
5. スライド生成 (Gemini)
6. 動画生成

## 公式FAQ（以下の情報を優先して回答してください）

{faq_content}

## 回答のルール
1. 日本語で丁寧に回答
2. 上記FAQに該当する内容があれば、その対応方法を案内
3. 具体的な解決手順を提示
4. システム側の問題の可能性がある場合は正直に伝える
5. 不明な場合は開発チームへの問い合わせを案内"""

@app.post("/support/chat")
async def support_chat(
    request: SupportChatRequest,
    x_gemini_key: Optional[str] = Header(None),
    x_gemini_model: Optional[str] = Header(None)
):
    """AI-powered support chat using Gemini"""
    import google.generativeai as genai

    # Get API key from header or environment
    gemini_key = x_gemini_key or os.environ.get("GEMINI_API_KEY")

    if not gemini_key:
        return {
            "reply": "申し訳ございません。サポートチャットを利用するにはGemini APIキーが必要です。\n\n画面上部の「API設定」からGemini APIキーを設定してください。\n\nAPIキーは https://aistudio.google.com/app/apikey で無料で取得できます。"
        }
    
    try:
        genai.configure(api_key=gemini_key)
        support_model = x_gemini_model or "gemini-3-flash-preview"
        model = genai.GenerativeModel(support_model)

        # Build conversation context
        messages = []
        
        # Add history
        if request.history:
            for msg in request.history[-10:]:  # Last 10 messages for context
                messages.append(f"{msg['role']}: {msg['content']}")
        
        # Add current message with context
        user_message = request.message
        if request.context:
            context_str = f"\n\n[エラーコンテキスト]\nステップ: {request.context.get('step', '不明')}\nエラー: {request.context.get('errorMessage', '不明')}\nモード: {request.context.get('workflowMode', '不明')}"
            user_message += context_str
        
        messages.append(f"user: {user_message}")
        
        # Load FAQ and inject into prompt
        faq_content = load_support_faq()
        system_prompt = SUPPORT_SYSTEM_PROMPT.format(faq_content=faq_content if faq_content else "(FAQファイルが見つかりません)")
        
        # Generate response
        prompt = f"{system_prompt}\n\n## 会話履歴\n" + "\n".join(messages) + "\n\nassistant:"
        
        response = model.generate_content(prompt)
        reply = response.text.strip()
        
        return {"reply": reply}
        
    except Exception as e:
        error_str = str(e)
        print(f"[Support Chat] Error: {error_str}")
        
        # Provide helpful error messages
        if "API key not valid" in error_str or "API_KEY_INVALID" in error_str:
            return {
                "reply": "Gemini APIキーが無効です。\n\n以下をご確認ください:\n1. Google AI Studio (https://aistudio.google.com/app/apikey) でキーが有効か確認\n2. 「API設定」から正しいキーを再入力\n\n新しいキーを発行して再度お試しください。"
            }
        elif "quota" in error_str.lower():
            return {
                "reply": "APIの利用制限に達しました。\n\nしばらく時間をおいてから再度お試しください。または、Google Cloud Consoleで利用上限を確認してください。"
            }
        else:
            return {
                "reply": f"一時的にサポートに接続できませんでした。\n\nしばらくしてから再度お試しいただくか、以下のエラー情報を開発チームにお伝えください:\n\n```\n{error_str[:200]}\n```"
            }

# ========== Feedback Notification ==========

def send_discord_notification(category: str, message: str, context: Optional[Dict[str, Any]] = None) -> bool:
    """Send feedback notification to Discord via webhook"""
    import httpx
    
    discord_webhook = os.environ.get("DISCORD_WEBHOOK_URL")
    
    if not discord_webhook:
        print("[Feedback] Discord webhook not configured, skipping")
        return False
    
    # Category labels with emoji
    category_labels = {
        "error": "🚨 エラー報告",
        "request": "💡 機能リクエスト",
        "feedback": "📝 フィードバック"
    }
    category_label = category_labels.get(category, "📩 お問い合わせ")
    
    # Build Discord embed
    from datetime import timezone
    embed = {
        "title": f"{category_label}",
        "description": message[:2000] if message else "(内容なし)",
        "color": {
            "error": 0xFF4444,      # Red
            "request": 0xFFAA00,    # Orange
            "feedback": 0x00AAFF    # Blue
        }.get(category, 0x888888),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "footer": {"text": "VoiSlide Movie"}
    }
    
    # Add context fields if available
    if context:
        embed["fields"] = [
            {"name": "ステップ", "value": str(context.get("step") or "不明"), "inline": True},
            {"name": "モード", "value": str(context.get("workflowMode") or "不明"), "inline": True},
        ]
        if context.get("errorMessage"):
            embed["fields"].append({
                "name": "エラー内容",
                "value": f"```{str(context.get('errorMessage', ''))[:500]}```",
                "inline": False
            })
    
    try:
        response = httpx.post(
            discord_webhook,
            json={"embeds": [embed]},
            timeout=10.0
        )
        
        if response.status_code in [200, 204]:
            print(f"[Feedback] Discord notification sent: {category}")
            return True
        else:
            print(f"[Feedback] Discord error: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"[Feedback] Discord notification failed: {e}")
        return False


class FeedbackRequest(BaseModel):
    category: str  # "error", "request", "feedback"
    message: str
    context: Optional[Dict[str, Any]] = None

def send_feedback_email(category: str, message: str, context: Optional[Dict[str, Any]] = None) -> bool:
    """Send feedback notification email via SMTP"""
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    
    smtp_host = os.environ.get("SMTP_HOST")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_user = os.environ.get("SMTP_USER")
    smtp_pass = os.environ.get("SMTP_PASS")
    notify_email = os.environ.get("NOTIFY_EMAIL")
    
    if not all([smtp_host, smtp_user, smtp_pass, notify_email]):
        print("[Feedback] SMTP not configured, skipping email")
        return False
    
    # Category labels
    category_labels = {
        "error": "🚨 エラー報告",
        "request": "💡 機能リクエスト",
        "feedback": "📝 フィードバック"
    }
    category_label = category_labels.get(category, "📩 お問い合わせ")
    
    # Build email
    subject = f"[VoiSlide] {category_label}"
    
    body = f"""VoiSlide Movieからフィードバックがありました。

■ カテゴリ: {category_label}

■ 内容:
{message}
"""
    
    if context:
        body += f"""
■ コンテキスト:
- ステップ: {context.get('step', '不明')}
- エラー: {context.get('errorMessage', 'なし')}
- モード: {context.get('workflowMode', '不明')}
- 時刻: {context.get('timestamp', '不明')}
"""
    
    try:
        msg = MIMEMultipart()
        msg["From"] = smtp_user
        msg["To"] = notify_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain", "utf-8"))
        
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
        
        print(f"[Feedback] Email sent: {category}")
        return True
        
    except Exception as e:
        print(f"[Feedback] Email failed: {e}")
        return False

@app.post("/support/feedback")
async def submit_feedback(request: FeedbackRequest):
    """Submit user feedback with Discord and email notification"""
    
    # Validate category
    if request.category not in ["error", "request", "feedback"]:
        raise HTTPException(400, "Invalid category")
    
    # Try Discord notification first (preferred)
    discord_sent = send_discord_notification(
        category=request.category,
        message=request.message,
        context=request.context
    )
    
    # Fallback to email if Discord fails
    email_sent = False
    if not discord_sent:
        email_sent = send_feedback_email(
            category=request.category,
            message=request.message,
            context=request.context
        )
    
    return {
        "success": True,
        "discord_sent": discord_sent,
        "email_sent": email_sent,
        "message": "フィードバックを送信しました。ありがとうございます！"
    }


# ========== Support Escalation ==========

class EscalationRequest(BaseModel):
    user_email: str
    conversation: List[Dict[str, str]]
    context: Optional[Dict[str, Any]] = None
    issue_summary: Optional[str] = None

@app.post("/support/escalate")
async def escalate_to_email(request: EscalationRequest):
    """Escalate support issue via Discord (primary) or email (fallback)"""
    import httpx
    from datetime import timezone
    
    # Format conversation for display
    conversation_text = "\n".join([
        f"**{'ユーザー' if m.get('role') == 'user' else 'AI'}**: {m.get('content', '')[:200]}"
        for m in request.conversation[-5:]  # Last 5 messages
    ])
    
    # Try Discord first
    discord_webhook = os.environ.get("DISCORD_WEBHOOK_URL")
    
    if discord_webhook:
        try:
            embed = {
                "title": "🆘 サポートエスカレーション",
                "description": f"**問題の概要:**\n{request.issue_summary or '（未入力）'}",
                "color": 0xFF4444,  # Red for urgency
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "footer": {"text": "VoiSlide Movie"},
                "fields": [
                    {"name": "📧 ユーザーメール", "value": request.user_email, "inline": True},
                ]
            }
            
            # Add context if available
            if request.context:
                embed["fields"].append({
                    "name": "📍 コンテキスト",
                    "value": f"ステップ: {request.context.get('step', '不明')}\nモード: {request.context.get('workflowMode', '不明')}",
                    "inline": True
                })
                if request.context.get('errorMessage'):
                    embed["fields"].append({
                        "name": "⚠️ エラー",
                        "value": f"```{str(request.context.get('errorMessage', ''))[:300]}```",
                        "inline": False
                    })
            
            # Add conversation summary
            if conversation_text:
                embed["fields"].append({
                    "name": "💬 会話履歴（直近5件）",
                    "value": conversation_text[:1000],
                    "inline": False
                })
            
            response = httpx.post(
                discord_webhook,
                json={"embeds": [embed]},
                timeout=10.0
            )
            
            if response.status_code in [200, 204]:
                print(f"[Escalation] Discord notification sent for: {request.user_email}")
                return {
                    "success": True, 
                    "message": "サポートチームに通知しました。メールで回答いたします。"
                }
                
        except Exception as e:
            print(f"[Escalation] Discord failed: {e}")
    
    # Fallback to email if Discord fails or not configured
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    
    smtp_host = os.environ.get("SMTP_HOST")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_user = os.environ.get("SMTP_USER")
    smtp_pass = os.environ.get("SMTP_PASS")
    notify_email = os.environ.get("NOTIFY_EMAIL")
    
    if not all([smtp_host, smtp_user, smtp_pass, notify_email]):
        print("[Escalation] Neither Discord nor SMTP configured")
        return {"success": False, "message": "通知設定が未完了です。しばらくお待ちください。"}
    
    # Format full conversation for email
    full_conversation = "\n\n".join([
        f"[{'ユーザー' if m.get('role') == 'user' else 'AI'}]\n{m.get('content', '')}"
        for m in request.conversation
    ])
    
    subject = f"[VoiSlide] 🆘 サポートエスカレーション"
    
    body = f"""VoiSlideのサポートチャットからエスカレーションがありました。

■ ユーザーメールアドレス: {request.user_email}

■ 問題の概要:
{request.issue_summary or "（未入力）"}
"""
    
    if request.context:
        body += f"""
■ エラーコンテキスト:
- ステップ: {request.context.get('step', '不明')}
- エラー: {request.context.get('errorMessage', 'なし')}
- モード: {request.context.get('workflowMode', '不明')}
- 時刻: {request.context.get('timestamp', '不明')}
"""
    
    body += f"""
■ 会話履歴:
{full_conversation}

---
このメールに返信すると、ユーザー（{request.user_email}）に直接届きます。
"""
    
    try:
        msg = MIMEMultipart()
        msg["From"] = smtp_user
        msg["To"] = notify_email
        msg["Reply-To"] = request.user_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain", "utf-8"))
        
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
        
        print(f"[Escalation] Email sent for: {request.user_email}")
        return {
            "success": True, 
            "message": "サポートチームにエスカレーションしました。メールで回答いたします。"
        }
        
    except Exception as e:
        print(f"[Escalation] Email failed: {e}")
        return {"success": False, "message": "エスカレーションに失敗しました"}


if __name__ == "__main__":
    import uvicorn
    from config import HOST, PORT
    print(f"Starting backend on {HOST}:{PORT}")
    uvicorn.run(app, host=HOST, port=PORT)


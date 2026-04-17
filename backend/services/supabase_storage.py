"""
Supabase Storage helper for persisting audio files.

Why this exists: Railway containers are ephemeral — files in /app/uploads
are wiped on every redeploy. By uploading audio to Supabase Storage at
upload time, we can download them back on project restore even after
a redeploy.

Uses the Supabase Storage REST API directly (no SDK) via httpx. The backend
authenticates as the service role, which bypasses RLS. Path convention:
    {bucket}/{user_id}/{project_id}/audio.{ext}
"""
from __future__ import annotations

import os
import asyncio
from typing import Optional, Tuple

import httpx

SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
AUDIOS_BUCKET = "audios"

_TIMEOUT = httpx.Timeout(connect=10.0, read=120.0, write=120.0, pool=10.0)


def is_configured() -> bool:
    """True if both SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are set."""
    return bool(SUPABASE_URL) and bool(SUPABASE_SERVICE_ROLE_KEY)


def _service_headers(extra: Optional[dict] = None) -> dict:
    headers = {
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
    }
    if extra:
        headers.update(extra)
    return headers


def _safe_ext(filename_or_ext: str) -> str:
    ext = filename_or_ext.lower()
    if not ext.startswith("."):
        ext = os.path.splitext(ext)[1].lower() or ".wav"
    # whitelist allowed extensions
    allowed = {".mp3", ".wav", ".m4a", ".mp4", ".mov", ".webm", ".avi", ".mkv"}
    if ext not in allowed:
        ext = ".wav"
    return ext


def build_audio_path(user_id: str, project_id: str, ext: str) -> str:
    """Path inside the `audios` bucket. E.g. `{user_id}/{project_id}/audio.wav`."""
    ext = _safe_ext(ext)
    # sanitize — these are UUIDs but be defensive
    safe_user = "".join(c for c in user_id if c.isalnum() or c in "-_")
    safe_project = "".join(c for c in project_id if c.isalnum() or c in "-_")
    return f"{safe_user}/{safe_project}/audio{ext}"


async def upload_audio(
    local_path: str,
    user_id: str,
    project_id: str,
    ext: Optional[str] = None,
) -> Optional[str]:
    """Upload a local audio file to Supabase Storage.

    Returns the object path (e.g. "user_id/project_id/audio.wav") on success,
    or None if storage is not configured or the upload fails.
    """
    if not is_configured():
        print("[Storage] SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY not set, skipping upload")
        return None
    if not os.path.exists(local_path):
        print(f"[Storage] Local file not found: {local_path}")
        return None
    if not user_id or not project_id:
        print("[Storage] user_id and project_id required for upload")
        return None

    if ext is None:
        ext = os.path.splitext(local_path)[1]
    storage_path = build_audio_path(user_id, project_id, ext)
    url = f"{SUPABASE_URL}/storage/v1/object/{AUDIOS_BUCKET}/{storage_path}"

    # Determine content-type from extension
    mime_map = {
        ".mp3": "audio/mpeg",
        ".wav": "audio/wav",
        ".m4a": "audio/m4a",
        ".mp4": "video/mp4",
        ".mov": "video/quicktime",
        ".webm": "video/webm",
        ".avi": "video/x-msvideo",
        ".mkv": "video/x-matroska",
    }
    content_type = mime_map.get(_safe_ext(ext), "application/octet-stream")

    try:
        with open(local_path, "rb") as f:
            data = f.read()
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            # x-upsert: true -> overwrite if exists
            resp = await client.post(
                url,
                content=data,
                headers=_service_headers({
                    "Content-Type": content_type,
                    "x-upsert": "true",
                }),
            )
        if resp.status_code in (200, 201):
            print(f"[Storage] ✓ Uploaded audio: {storage_path} ({len(data)/1024/1024:.1f} MB)")
            return storage_path
        else:
            print(f"[Storage] ✗ Upload failed: {resp.status_code} — {resp.text[:200]}")
            return None
    except Exception as e:
        print(f"[Storage] ✗ Upload exception: {type(e).__name__}: {e}")
        return None


async def download_audio(storage_path: str, local_path: str) -> bool:
    """Download an audio file from Supabase Storage to a local path.

    Returns True on success. Returns False if storage is not configured,
    the path is empty, or the download fails.
    """
    if not is_configured():
        print("[Storage] SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY not set, skipping download")
        return False
    if not storage_path:
        return False

    url = f"{SUPABASE_URL}/storage/v1/object/{AUDIOS_BUCKET}/{storage_path}"
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(url, headers=_service_headers())
        if resp.status_code == 200:
            os.makedirs(os.path.dirname(local_path) or ".", exist_ok=True)
            with open(local_path, "wb") as f:
                f.write(resp.content)
            print(f"[Storage] ✓ Downloaded audio: {storage_path} → {local_path} ({len(resp.content)/1024/1024:.1f} MB)")
            return True
        elif resp.status_code == 404:
            print(f"[Storage] ✗ Not found: {storage_path}")
            return False
        else:
            print(f"[Storage] ✗ Download failed: {resp.status_code} — {resp.text[:200]}")
            return False
    except Exception as e:
        print(f"[Storage] ✗ Download exception: {type(e).__name__}: {e}")
        return False


def storage_path_ext(storage_path: str) -> str:
    """Extract the extension from a storage path. Defaults to .wav."""
    return _safe_ext(os.path.splitext(storage_path)[1])


# ---------------------------------------------------------------------------
# Video cache helpers (48-hour retention)
# ---------------------------------------------------------------------------
# Videos follow the same storage pattern as audio but need longer timeouts
# (200 MB uploads on Railway uplink can exceed the 120s audio timeout) and a
# dedicated bucket with a higher size ceiling. Retention is enforced by the
# backend cleanup task, not by Supabase itself.

VIDEOS_BUCKET = "videos"

_VIDEO_TIMEOUT = httpx.Timeout(connect=10.0, read=600.0, write=600.0, pool=10.0)


def build_video_path(user_id: str, project_id: str) -> str:
    """Path inside the `videos` bucket. E.g. `{user_id}/{project_id}/video.mp4`."""
    safe_user = "".join(c for c in user_id if c.isalnum() or c in "-_")
    safe_project = "".join(c for c in project_id if c.isalnum() or c in "-_")
    return f"{safe_user}/{safe_project}/video.mp4"


async def upload_video(
    local_path: str,
    user_id: str,
    project_id: str,
) -> Optional[str]:
    """Upload a generated MP4 to Supabase Storage.

    Returns the object path on success, or None if storage is not configured,
    inputs are missing, or the upload fails. Callers should treat this as
    fire-and-forget — exceptions are logged, never raised.
    """
    if not is_configured():
        print("[Storage] SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY not set, skipping video upload")
        return None
    if not os.path.exists(local_path):
        print(f"[Storage] Local video not found: {local_path}")
        return None
    if not user_id or not project_id:
        print("[Storage] user_id and project_id required for video upload")
        return None

    storage_path = build_video_path(user_id, project_id)
    url = f"{SUPABASE_URL}/storage/v1/object/{VIDEOS_BUCKET}/{storage_path}"

    try:
        with open(local_path, "rb") as f:
            data = f.read()
        async with httpx.AsyncClient(timeout=_VIDEO_TIMEOUT) as client:
            resp = await client.post(
                url,
                content=data,
                headers=_service_headers({
                    "Content-Type": "video/mp4",
                    "x-upsert": "true",
                }),
            )
        if resp.status_code in (200, 201):
            print(f"[Storage] ✓ Uploaded video: {storage_path} ({len(data)/1024/1024:.1f} MB)")
            return storage_path
        else:
            print(f"[Storage] ✗ Video upload failed: {resp.status_code} — {resp.text[:200]}")
            return None
    except Exception as e:
        print(f"[Storage] ✗ Video upload exception: {type(e).__name__}: {e}")
        return None


async def download_video(storage_path: str, local_path: str) -> bool:
    """Download a cached MP4 from Supabase Storage into the container.

    Returns True on success. Falls back to False on any failure so callers
    can treat the video as missing.
    """
    if not is_configured():
        return False
    if not storage_path:
        return False

    url = f"{SUPABASE_URL}/storage/v1/object/{VIDEOS_BUCKET}/{storage_path}"
    try:
        async with httpx.AsyncClient(timeout=_VIDEO_TIMEOUT) as client:
            resp = await client.get(url, headers=_service_headers())
        if resp.status_code == 200:
            os.makedirs(os.path.dirname(local_path) or ".", exist_ok=True)
            with open(local_path, "wb") as f:
                f.write(resp.content)
            print(f"[Storage] ✓ Downloaded video: {storage_path} → {local_path} ({len(resp.content)/1024/1024:.1f} MB)")
            return True
        elif resp.status_code == 404:
            print(f"[Storage] ✗ Video not found: {storage_path}")
            return False
        else:
            print(f"[Storage] ✗ Video download failed: {resp.status_code} — {resp.text[:200]}")
            return False
    except Exception as e:
        print(f"[Storage] ✗ Video download exception: {type(e).__name__}: {e}")
        return False


async def delete_video(storage_path: str) -> bool:
    """Delete a cached video from Supabase Storage. Never raises."""
    if not is_configured() or not storage_path:
        return False
    url = f"{SUPABASE_URL}/storage/v1/object/{VIDEOS_BUCKET}/{storage_path}"
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.delete(url, headers=_service_headers())
        if resp.status_code in (200, 204):
            print(f"[Storage] ✓ Deleted video: {storage_path}")
            return True
        elif resp.status_code == 404:
            return True  # already gone — treat as success
        else:
            print(f"[Storage] ✗ Video delete failed: {resp.status_code} — {resp.text[:200]}")
            return False
    except Exception as e:
        print(f"[Storage] ✗ Video delete exception: {type(e).__name__}: {e}")
        return False

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
import glob as _glob
import asyncio
from typing import Optional, Tuple, List

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


# ---------------------------------------------------------------------------
# Slide PNG helpers (permanent — no retention cap)
# ---------------------------------------------------------------------------
# Slides are the core artifact of a project, not a convenience cache, so we
# keep them for the project's lifetime. Deletion is tied to project deletion,
# not a time-window sweep. See supabase_migration_slides_storage.sql for the
# bucket + RLS definitions.

SLIDES_BUCKET = "slides"

# Per-file timeouts match audio — PNGs are small (200-500 KB), slide_data.json
# is tiny. The bundle-level concurrency below is what keeps aggregate latency
# bounded on 20+ slide projects.
_SLIDE_TIMEOUT = httpx.Timeout(connect=10.0, read=60.0, write=60.0, pool=10.0)


def build_slides_prefix(user_id: str, project_id: str) -> str:
    """Path prefix (with trailing slash) inside the `slides` bucket.
    E.g. `{user_id}/{project_id}/slides/`.

    Trailing slash matters: Supabase's list API uses the prefix literally, so
    `u/p/slides` would also match `u/p/slides_archive/` if it existed.
    """
    safe_user = "".join(c for c in user_id if c.isalnum() or c in "-_")
    safe_project = "".join(c for c in project_id if c.isalnum() or c in "-_")
    return f"{safe_user}/{safe_project}/slides/"


async def _upload_slide_file(
    client: httpx.AsyncClient,
    local_path: str,
    storage_path: str,
    content_type: str,
) -> bool:
    """Single-file upload. Caller owns the AsyncClient so we can batch with
    parallel semaphore. x-upsert:true means repeated uploads overwrite."""
    url = f"{SUPABASE_URL}/storage/v1/object/{SLIDES_BUCKET}/{storage_path}"
    try:
        with open(local_path, "rb") as f:
            data = f.read()
        resp = await client.post(
            url,
            content=data,
            headers=_service_headers({
                "Content-Type": content_type,
                "x-upsert": "true",
            }),
        )
        if resp.status_code in (200, 201):
            return True
        print(f"[Storage] ✗ Slide upload failed for {storage_path}: "
              f"{resp.status_code} — {resp.text[:200]}")
        return False
    except Exception as e:
        print(f"[Storage] ✗ Slide upload exception for {storage_path}: "
              f"{type(e).__name__}: {e}")
        return False


async def upload_slides_bundle(
    slides_dir: str,
    user_id: str,
    project_id: str,
    concurrency: int = 4,
) -> Optional[str]:
    """Upload every slide_*.png and slide_data.json under `slides_dir` in
    parallel. Returns the storage prefix on success (even partial), or None
    if the whole operation was a no-op (unconfigured, missing dir, no files).

    Partial success returns the prefix anyway: having some slides restored
    is strictly better than none, and the next cache cycle (e.g. after the
    next edit) will catch up.
    """
    if not is_configured():
        print("[Storage] SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY not set, skipping slides upload")
        return None
    if not os.path.isdir(slides_dir):
        print(f"[Storage] slides_dir not found: {slides_dir}")
        return None
    if not user_id or not project_id:
        print("[Storage] user_id and project_id required for slides upload")
        return None

    # Collect payload
    png_paths = sorted(_glob.glob(os.path.join(slides_dir, "slide_*.png")))
    json_path = os.path.join(slides_dir, "slide_data.json")
    files: List[Tuple[str, str, str]] = []  # (local, storage_name, content_type)
    for p in png_paths:
        files.append((p, os.path.basename(p), "image/png"))
    if os.path.exists(json_path):
        files.append((json_path, "slide_data.json", "application/json"))

    if not files:
        print(f"[Storage] No slide files to upload in {slides_dir}")
        return None

    prefix = build_slides_prefix(user_id, project_id)
    sem = asyncio.Semaphore(max(1, concurrency))

    async def _one(client: httpx.AsyncClient, local: str, name: str, ctype: str) -> bool:
        async with sem:
            return await _upload_slide_file(client, local, f"{prefix}{name}", ctype)

    async with httpx.AsyncClient(timeout=_SLIDE_TIMEOUT) as client:
        results = await asyncio.gather(
            *(_one(client, local, name, ctype) for (local, name, ctype) in files),
            return_exceptions=False,
        )

    ok = sum(1 for r in results if r)
    total = len(files)
    if ok == 0:
        print(f"[Storage] ✗ Slides upload completely failed: 0/{total} for project={project_id}")
        return None
    if ok < total:
        print(f"[Storage] ⚠ Slides upload partial: {ok}/{total} for project={project_id} — returning prefix anyway")
    else:
        print(f"[Storage] ✓ Uploaded slides bundle: {prefix} ({ok} files)")
    return prefix


async def list_slide_objects(prefix: str) -> List[str]:
    """List objects under the prefix. Returns names WITHOUT the prefix
    (e.g. `slide_001.png`, `slide_data.json`). Empty list on failure."""
    if not is_configured() or not prefix:
        return []
    # Supabase Storage list API: POST /storage/v1/object/list/{bucket}
    url = f"{SUPABASE_URL}/storage/v1/object/list/{SLIDES_BUCKET}"
    body = {
        "prefix": prefix,
        "limit": 1000,
        "offset": 0,
        "sortBy": {"column": "name", "order": "asc"},
    }
    try:
        async with httpx.AsyncClient(timeout=_SLIDE_TIMEOUT) as client:
            resp = await client.post(
                url,
                json=body,
                headers=_service_headers({"Content-Type": "application/json"}),
            )
        if resp.status_code != 200:
            print(f"[Storage] ✗ list failed for {prefix}: {resp.status_code} — {resp.text[:200]}")
            return []
        items = resp.json() or []
        # Defensive: the API returns objects with a `name` field that is the
        # path relative to the prefix when prefix is non-empty.
        return [it["name"] for it in items if isinstance(it, dict) and it.get("name")]
    except Exception as e:
        print(f"[Storage] ✗ list exception for {prefix}: {type(e).__name__}: {e}")
        return []


async def _download_slide_file(
    client: httpx.AsyncClient,
    storage_path: str,
    local_path: str,
) -> bool:
    url = f"{SUPABASE_URL}/storage/v1/object/{SLIDES_BUCKET}/{storage_path}"
    try:
        resp = await client.get(url, headers=_service_headers())
        if resp.status_code == 200:
            os.makedirs(os.path.dirname(local_path) or ".", exist_ok=True)
            with open(local_path, "wb") as f:
                f.write(resp.content)
            return True
        print(f"[Storage] ✗ Slide download failed for {storage_path}: "
              f"{resp.status_code} — {resp.text[:200]}")
        return False
    except Exception as e:
        print(f"[Storage] ✗ Slide download exception for {storage_path}: "
              f"{type(e).__name__}: {e}")
        return False


async def download_slides_bundle(
    prefix: str,
    dest_dir: str,
    concurrency: int = 4,
) -> int:
    """Download every object under `prefix` into `dest_dir`. Returns the
    number of files that landed on disk (not just requested). Zero means
    the caller should fall back to the "regenerate slides" path.

    Files are named by their storage-side basename, so
    `{prefix}slide_001.png` lands at `{dest_dir}/slide_001.png`.
    """
    if not is_configured() or not prefix:
        return 0
    names = await list_slide_objects(prefix)
    if not names:
        return 0

    os.makedirs(dest_dir, exist_ok=True)
    sem = asyncio.Semaphore(max(1, concurrency))

    async def _one(client: httpx.AsyncClient, name: str) -> bool:
        async with sem:
            # `name` from list() is sometimes the basename only (when prefix is
            # non-empty) and sometimes the full path. Handle both.
            storage_path = name if name.startswith(prefix) else f"{prefix}{name}"
            basename = os.path.basename(storage_path)
            local = os.path.join(dest_dir, basename)
            return await _download_slide_file(client, storage_path, local)

    async with httpx.AsyncClient(timeout=_SLIDE_TIMEOUT) as client:
        results = await asyncio.gather(
            *(_one(client, n) for n in names),
            return_exceptions=False,
        )

    ok = sum(1 for r in results if r)
    total = len(names)
    if ok == total and ok > 0:
        print(f"[Storage] ✓ Downloaded slides bundle: {prefix} → {dest_dir} ({ok} files)")
    elif ok > 0:
        print(f"[Storage] ⚠ Partial slides download: {ok}/{total} for {prefix}")
    else:
        print(f"[Storage] ✗ Slides download failed: 0/{total} for {prefix}")
    return ok


async def delete_slides_prefix(prefix: str) -> bool:
    """Delete every object under the prefix. Used by project-delete flow so
    orphaned slides don't accumulate. Never raises."""
    if not is_configured() or not prefix:
        return False
    names = await list_slide_objects(prefix)
    if not names:
        return True  # nothing to delete — treat as success
    # Supabase DELETE API expects full paths relative to the bucket root.
    full_paths = [
        n if n.startswith(prefix) else f"{prefix}{n}"
        for n in names
    ]
    url = f"{SUPABASE_URL}/storage/v1/object/{SLIDES_BUCKET}"
    try:
        async with httpx.AsyncClient(timeout=_SLIDE_TIMEOUT) as client:
            resp = await client.request(
                "DELETE",
                url,
                json={"prefixes": full_paths},
                headers=_service_headers({"Content-Type": "application/json"}),
            )
        if resp.status_code in (200, 204):
            print(f"[Storage] ✓ Deleted slides prefix: {prefix} ({len(full_paths)} objects)")
            return True
        print(f"[Storage] ✗ Slides delete failed: {resp.status_code} — {resp.text[:200]}")
        return False
    except Exception as e:
        print(f"[Storage] ✗ Slides delete exception: {type(e).__name__}: {e}")
        return False

-- VoiceSlide AI - Slide PNG Persistence via Supabase Storage
-- Run this in Supabase Dashboard > SQL Editor
--
-- Why this exists: Generated slide PNGs (outputs/{job_id}_slides/slide_*.png)
-- and their slide_data.json metadata live only in the Railway container's
-- /app/outputs directory, which is wiped on every redeploy. Previously,
-- reopening a project after a redeploy showed the "スライドのプレビューが見つかりません"
-- banner because the backend's fallback "copy from old job_id" path found
-- nothing on disk.
--
-- Unlike the 48h video cache, slides are the *core artifact* of a project,
-- not a convenience mirror — we keep them for the lifetime of the project.
-- Deletion happens when a project row is removed, not on a time window.
--
-- Retention budget: ~300 KB × 20 slides × N projects. At 10k active projects
-- that's ~60 GB — acceptable on Supabase Pro. Monitor via the
-- idx_projects_slides_cached_at partial index below.

-- 1. Create the `slides` bucket (private)
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES (
  'slides',
  'slides',
  false,  -- private: accessed via service role from backend
  26214400,  -- 25 MB ceiling per file (real PNGs expected 200-500 KB; JSON tiny)
  ARRAY['image/png', 'application/json']::TEXT[]
)
ON CONFLICT (id) DO UPDATE SET
  public = EXCLUDED.public,
  file_size_limit = EXCLUDED.file_size_limit,
  allowed_mime_types = EXCLUDED.allowed_mime_types;

-- 2. RLS: users can only access files under `{their_user_id}/...`
--    Service role (used by backend) bypasses RLS automatically.
--    Path convention: {user_id}/{project_id}/slides/slide_001.png
--                     {user_id}/{project_id}/slides/slide_data.json

DROP POLICY IF EXISTS "Users read own slides" ON storage.objects;
CREATE POLICY "Users read own slides"
  ON storage.objects FOR SELECT
  TO authenticated
  USING (
    bucket_id = 'slides'
    AND (storage.foldername(name))[1] = auth.uid()::text
  );

DROP POLICY IF EXISTS "Users insert own slides" ON storage.objects;
CREATE POLICY "Users insert own slides"
  ON storage.objects FOR INSERT
  TO authenticated
  WITH CHECK (
    bucket_id = 'slides'
    AND (storage.foldername(name))[1] = auth.uid()::text
  );

DROP POLICY IF EXISTS "Users update own slides" ON storage.objects;
CREATE POLICY "Users update own slides"
  ON storage.objects FOR UPDATE
  TO authenticated
  USING (
    bucket_id = 'slides'
    AND (storage.foldername(name))[1] = auth.uid()::text
  );

DROP POLICY IF EXISTS "Users delete own slides" ON storage.objects;
CREATE POLICY "Users delete own slides"
  ON storage.objects FOR DELETE
  TO authenticated
  USING (
    bucket_id = 'slides'
    AND (storage.foldername(name))[1] = auth.uid()::text
  );

-- 3. projects table: record the storage prefix + cache timestamp.
--    slides_cached_at is not used for expiry (slides are permanent) — it's
--    there for observability so we can tell a project "has never been synced"
--    from "was last synced N minutes ago".
ALTER TABLE projects
  ADD COLUMN IF NOT EXISTS slides_storage_prefix TEXT,
  ADD COLUMN IF NOT EXISTS slides_cached_at      TIMESTAMPTZ;

-- Partial index for observability dashboards / future sweep jobs.
-- There is intentionally NO cleanup sweep on this index — unlike the video
-- cache. If we ever need orphan cleanup (e.g. projects deleted without calling
-- delete_slides_prefix), add it as a separate migration.
CREATE INDEX IF NOT EXISTS idx_projects_slides_cached_at
  ON projects(slides_cached_at)
  WHERE slides_storage_prefix IS NOT NULL;

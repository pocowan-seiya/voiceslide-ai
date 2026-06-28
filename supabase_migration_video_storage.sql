-- VoiceSlide AI - 48-Hour Video Caching via Supabase Storage
-- Run this in Supabase Dashboard > SQL Editor
--
-- Why this exists: Generated MP4 videos live only in the Railway container's
-- /app/outputs directory, which is wiped on every redeploy. Previously,
-- resuming a project showed a broken "tape" icon because projects.video_url
-- pointed to a file that no longer existed. Permanently storing every video
-- would inflate storage and bandwidth costs linearly with user count, so
-- we cache videos for ~48 hours instead — enough recovery time for
-- "I forgot to download" scenarios without unbounded growth.
--
-- Access pattern differs from audio: audio is keyed by primary key on restore,
-- so JSONB settings suffice. Video cleanup runs a time-range query
-- (`WHERE video_cached_at < NOW() - 48h`), which needs an indexed timestamp
-- column — hence dedicated columns on the projects table.

-- 1. Create the `videos` bucket (private)
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES (
  'videos',
  'videos',
  false,  -- private: accessed via service role from backend
  2147483648,  -- 2 GB ceiling (real files expected 50-200 MB)
  ARRAY['video/mp4']::TEXT[]
)
ON CONFLICT (id) DO UPDATE SET
  public = EXCLUDED.public,
  file_size_limit = EXCLUDED.file_size_limit,
  allowed_mime_types = EXCLUDED.allowed_mime_types;

-- 2. RLS: users can only access files under `{their_user_id}/...`
--    Service role (used by backend) bypasses RLS automatically.
--    Path convention: {user_id}/{project_id}/video.mp4

DROP POLICY IF EXISTS "Users read own videos" ON storage.objects;
CREATE POLICY "Users read own videos"
  ON storage.objects FOR SELECT
  TO authenticated
  USING (
    bucket_id = 'videos'
    AND (storage.foldername(name))[1] = auth.uid()::text
  );

DROP POLICY IF EXISTS "Users insert own videos" ON storage.objects;
CREATE POLICY "Users insert own videos"
  ON storage.objects FOR INSERT
  TO authenticated
  WITH CHECK (
    bucket_id = 'videos'
    AND (storage.foldername(name))[1] = auth.uid()::text
  );

DROP POLICY IF EXISTS "Users update own videos" ON storage.objects;
CREATE POLICY "Users update own videos"
  ON storage.objects FOR UPDATE
  TO authenticated
  USING (
    bucket_id = 'videos'
    AND (storage.foldername(name))[1] = auth.uid()::text
  );

DROP POLICY IF EXISTS "Users delete own videos" ON storage.objects;
CREATE POLICY "Users delete own videos"
  ON storage.objects FOR DELETE
  TO authenticated
  USING (
    bucket_id = 'videos'
    AND (storage.foldername(name))[1] = auth.uid()::text
  );

-- 3. projects table: track cache path and timestamp for 48h expiry sweep
ALTER TABLE projects
  ADD COLUMN IF NOT EXISTS video_storage_path TEXT,
  ADD COLUMN IF NOT EXISTS video_cached_at    TIMESTAMPTZ;

-- Partial index supports the cleanup sweep:
--   WHERE video_cached_at < NOW() - INTERVAL '48 hours'
--     AND video_storage_path IS NOT NULL
CREATE INDEX IF NOT EXISTS idx_projects_video_cached_at
  ON projects(video_cached_at)
  WHERE video_cached_at IS NOT NULL;

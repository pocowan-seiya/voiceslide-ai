-- VoiceSlide AI - Phase 2: Audio File Persistence via Supabase Storage
-- Run this in Supabase Dashboard > SQL Editor
--
-- Why this exists: Railway containers are ephemeral — files in /app/uploads
-- are wiped on every redeploy. To make project-restore robust, audio files
-- must live in persistent object storage. Supabase Storage is the natural
-- choice since auth is already Supabase.

-- 1. Create the `audios` bucket (private)
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES (
  'audios',
  'audios',
  false,  -- private: accessed via signed URLs or service role
  157286400,  -- 150 MB (covers a ~90-min MP3 at 192kbps)
  ARRAY[
    'audio/mpeg', 'audio/mp3', 'audio/wav', 'audio/x-wav', 'audio/wave',
    'audio/mp4', 'audio/x-m4a', 'audio/m4a',
    'video/mp4', 'video/quicktime', 'video/webm', 'video/x-msvideo', 'video/x-matroska'
  ]::TEXT[]
)
ON CONFLICT (id) DO UPDATE SET
  public = EXCLUDED.public,
  file_size_limit = EXCLUDED.file_size_limit,
  allowed_mime_types = EXCLUDED.allowed_mime_types;

-- 2. RLS: users can only access files under `{their_user_id}/...`
--    Service role (used by backend) bypasses RLS automatically.
--    Path convention: {user_id}/{project_id}/audio.{ext}

DROP POLICY IF EXISTS "Users read own audios" ON storage.objects;
CREATE POLICY "Users read own audios"
  ON storage.objects FOR SELECT
  TO authenticated
  USING (
    bucket_id = 'audios'
    AND (storage.foldername(name))[1] = auth.uid()::text
  );

DROP POLICY IF EXISTS "Users insert own audios" ON storage.objects;
CREATE POLICY "Users insert own audios"
  ON storage.objects FOR INSERT
  TO authenticated
  WITH CHECK (
    bucket_id = 'audios'
    AND (storage.foldername(name))[1] = auth.uid()::text
  );

DROP POLICY IF EXISTS "Users update own audios" ON storage.objects;
CREATE POLICY "Users update own audios"
  ON storage.objects FOR UPDATE
  TO authenticated
  USING (
    bucket_id = 'audios'
    AND (storage.foldername(name))[1] = auth.uid()::text
  );

DROP POLICY IF EXISTS "Users delete own audios" ON storage.objects;
CREATE POLICY "Users delete own audios"
  ON storage.objects FOR DELETE
  TO authenticated
  USING (
    bucket_id = 'audios'
    AND (storage.foldername(name))[1] = auth.uid()::text
  );

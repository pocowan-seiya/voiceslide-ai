-- VoiceSlide AI - Phase 2.3: Audio Storage Path as Top-Level Column
-- Run this in Supabase Dashboard > SQL Editor
--
-- Why this exists: `audioStoragePath` was originally stuffed inside the
-- `settings` JSONB column. The video_storage_path / video_cached_at fix
-- (already shipped) used dedicated columns, creating a schema inconsistency:
-- audio in JSONB, video in columns. That made restore code branchy and
-- left the door open for future bugs where one path forgets to read/write
-- one of the locations.
--
-- This migration promotes audio_storage_path to a dedicated column. The
-- backend dual-writes (column + settings.audioStoragePath) and dual-reads
-- (column first, JSONB fallback) so existing rows continue to work without
-- any data migration. JSONB writes will be removed in a follow-up once
-- all live data has flowed through the dual-write code.
--
-- Idempotent: safe to re-run.

ALTER TABLE projects
  ADD COLUMN IF NOT EXISTS audio_storage_path TEXT;

-- Backfill from settings.audioStoragePath for projects that already have it.
-- COALESCE: don't overwrite a value that's already in the new column.
UPDATE projects
SET audio_storage_path = COALESCE(
  audio_storage_path,
  NULLIF(settings->>'audioStoragePath', '')
)
WHERE settings ? 'audioStoragePath'
  AND audio_storage_path IS NULL;

COMMENT ON COLUMN projects.audio_storage_path IS
  'Supabase Storage object path for the user''s uploaded audio. '
  'Authoritative source as of Phase 2.3 (2026-04-18). '
  'Mirrors settings.audioStoragePath during the dual-write transition.';

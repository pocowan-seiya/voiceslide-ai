-- VoiceSlide AI - Design Mode (Flash 標準 / Pro)
-- Run this in Supabase Dashboard > SQL Editor
--
-- Why this exists: the default "Flash 標準" mode uses Python's deterministic
-- layout/color/font selection for speed + cost predictability (Gemini 3
-- Flash friendly). The new "Pro" mode hands layout/color/font selection to
-- the AI itself so high-end models (Claude Opus 4.7, GPT-5) can actually
-- differentiate their output. The trade-off is cost — Pro x Opus is roughly
-- $3-5 per 10-slide project vs cents on Flash.
--
-- This migration adds:
--   - `projects.design_mode`        — per-project mode (defaults to flash_standard
--     so ALL existing rows keep their current behavior)
--   - `user_settings.default_design_mode` — user-level default so new projects
--     created after this migration respect the user's saved preference
--
-- Both columns use CHECK constraints to pin the allowed values and keep bad
-- data out even if a client bug sends an unknown string. The defaults mean
-- zero behavior change for anyone who doesn't explicitly choose Pro.

ALTER TABLE projects
  ADD COLUMN IF NOT EXISTS design_mode TEXT NOT NULL DEFAULT 'flash_standard'
    CHECK (design_mode IN ('flash_standard', 'pro'));

ALTER TABLE user_settings
  ADD COLUMN IF NOT EXISTS default_design_mode TEXT NOT NULL DEFAULT 'flash_standard'
    CHECK (default_design_mode IN ('flash_standard', 'pro'));

-- Rollback note: `ALTER TABLE ... DROP COLUMN design_mode` is safe because
-- the column is read back with a fallback ("flash_standard" when NULL/
-- missing) in both backend (main.py) and frontend (lib/supabase/types.ts).
-- But dropping the column while code is still reading it means the SELECT *
-- in restore-project will no longer return it. If you need to roll back,
-- revert the application code FIRST, then drop the column.

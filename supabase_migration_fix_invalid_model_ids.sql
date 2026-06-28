-- VoiceSlide AI - Fix invalid Gemini model IDs in user_settings / projects
--
-- Background: the original schema set DEFAULT 'gemini-3-flash-preview' and
-- 'google/gemini-3-flash'. Neither model actually exists on the live APIs,
-- so any call that fell back to the default hit:
--   "google/gemini-3-flash is not a valid model ID"
-- every time.
--
-- This migration:
--   1. Updates the DEFAULT values on the columns so NEW rows don't inherit
--      the bad IDs.
--   2. Rewrites existing rows that still point to the bad IDs. Users who
--      had already picked a different valid model are untouched.
--
-- Safe to re-run (idempotent WHERE clauses).

-- 1. user_settings defaults + rewrite existing bad values
ALTER TABLE user_settings
  ALTER COLUMN gemini_model SET DEFAULT 'gemini-2.5-flash',
  ALTER COLUMN openrouter_model SET DEFAULT 'google/gemini-2.5-flash',
  ALTER COLUMN openrouter_design_model SET DEFAULT 'google/gemini-2.5-flash';

UPDATE user_settings
SET gemini_model = 'gemini-2.5-flash'
WHERE gemini_model = 'gemini-3-flash-preview';

UPDATE user_settings
SET openrouter_model = 'google/gemini-2.5-flash'
WHERE openrouter_model = 'google/gemini-3-flash';

UPDATE user_settings
SET openrouter_design_model = 'google/gemini-2.5-flash'
WHERE openrouter_design_model = 'google/gemini-3-flash';

-- 2. projects defaults (if columns exist — older DBs may not have these)
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'projects' AND column_name = 'gemini_model'
  ) THEN
    ALTER TABLE projects ALTER COLUMN gemini_model SET DEFAULT 'gemini-2.5-flash';
    UPDATE projects SET gemini_model = 'gemini-2.5-flash'
    WHERE gemini_model = 'gemini-3-flash-preview';
  END IF;

  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'projects' AND column_name = 'openrouter_model'
  ) THEN
    ALTER TABLE projects ALTER COLUMN openrouter_model SET DEFAULT 'google/gemini-2.5-flash';
    UPDATE projects SET openrouter_model = 'google/gemini-2.5-flash'
    WHERE openrouter_model = 'google/gemini-3-flash';
  END IF;
END $$;

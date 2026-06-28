-- VoiceSlide AI - Gemini 3 Flash Preview: 正しい OpenRouter slug へ修正
--
-- Background:
--   OpenRouter の正しい slug は `google/gemini-3-flash-preview` (末尾 -preview)
--   だが、以前のコードでは `google/gemini-3-flash` (preview 無し) と書かれていて、
--   "is not a valid model ID" エラーで落ちていた。
--
--   先に実行した supabase_migration_fix_invalid_model_ids.sql は、
--   壊れた slug → `google/gemini-2.5-flash` に一括移動していたが、
--   本来ユーザーが使いたかったのは Gemini 3 Flash Preview の方。
--
-- この migration は:
--   1. DEFAULT を正しい Gemini 3 Flash Preview slug に更新
--   2. 前回 2.5 に落とした user_settings の行を本来の Gemini 3 に戻す
--      (2.5 を明示的に選んだユーザーは対象外にしたいが、前回の migration と
--       時間差が小さいので、今 2.5 になっている行は前回の default 経由だった
--       と判断して戻す)
--
-- idempotent: 何度実行しても同じ結果。

-- 1. DEFAULT を更新
ALTER TABLE user_settings
  ALTER COLUMN gemini_model SET DEFAULT 'gemini-3-flash-preview',
  ALTER COLUMN openrouter_model SET DEFAULT 'google/gemini-3-flash-preview',
  ALTER COLUMN openrouter_design_model SET DEFAULT 'google/gemini-3-flash-preview';

-- 2. 前回の migration で 2.5-flash に落ちた user_settings を
--    Gemini 3 Flash Preview に引き上げ
UPDATE user_settings
SET gemini_model = 'gemini-3-flash-preview'
WHERE gemini_model = 'gemini-2.5-flash';

UPDATE user_settings
SET openrouter_model = 'google/gemini-3-flash-preview'
WHERE openrouter_model = 'google/gemini-2.5-flash';

UPDATE user_settings
SET openrouter_design_model = 'google/gemini-3-flash-preview'
WHERE openrouter_design_model = 'google/gemini-2.5-flash';

-- 3. projects 側にモデルカラムが残っていたら同様に対応
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'projects' AND column_name = 'gemini_model'
  ) THEN
    ALTER TABLE projects ALTER COLUMN gemini_model SET DEFAULT 'gemini-3-flash-preview';
    UPDATE projects SET gemini_model = 'gemini-3-flash-preview'
    WHERE gemini_model = 'gemini-2.5-flash';
  END IF;

  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'projects' AND column_name = 'openrouter_model'
  ) THEN
    ALTER TABLE projects ALTER COLUMN openrouter_model SET DEFAULT 'google/gemini-3-flash-preview';
    UPDATE projects SET openrouter_model = 'google/gemini-3-flash-preview'
    WHERE openrouter_model = 'google/gemini-2.5-flash';
  END IF;
END $$;

-- user_settings テーブル追加マイグレーション
-- Supabase ダッシュボード > SQL Editor で実行してください

CREATE TABLE IF NOT EXISTS user_settings (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     UUID REFERENCES auth.users(id) ON DELETE CASCADE NOT NULL UNIQUE,
  openai_key  TEXT NOT NULL DEFAULT '',
  gemini_key  TEXT NOT NULL DEFAULT '',
  gemini_model TEXT NOT NULL DEFAULT 'gemini-3-flash-preview',
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TRIGGER user_settings_updated_at
  BEFORE UPDATE ON user_settings
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();

ALTER TABLE user_settings ENABLE ROW LEVEL SECURITY;

CREATE POLICY "ユーザーは自分の設定のみ操作可能"
  ON user_settings FOR ALL
  USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);

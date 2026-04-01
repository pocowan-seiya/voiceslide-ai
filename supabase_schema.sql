-- VoiceLive Movie - Supabase Schema
-- Supabase ダッシュボード > SQL Editor で実行してください

-- プロジェクトテーブル
CREATE TABLE IF NOT EXISTS projects (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id             UUID REFERENCES auth.users(id) ON DELETE CASCADE NOT NULL,
  name                TEXT NOT NULL DEFAULT '新しいプロジェクト',
  status              TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'completed')),
  job_id              TEXT,
  step                INTEGER NOT NULL DEFAULT 1,
  workflow_mode       TEXT CHECK (workflow_mode IN ('hybrid', 'full-ai')),

  -- 作業内容
  transcript          TEXT NOT NULL DEFAULT '',
  polished_transcript TEXT NOT NULL DEFAULT '',
  outline             JSONB,
  polished_outline    JSONB,
  timing_map          JSONB NOT NULL DEFAULT '[]',

  -- 設定値（JSON一括）
  settings            JSONB NOT NULL DEFAULT '{}',

  -- 完成情報
  slide_count         INTEGER NOT NULL DEFAULT 0,
  video_url           TEXT,

  created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- updated_at 自動更新トリガー
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER projects_updated_at
  BEFORE UPDATE ON projects
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- RLS: 自分のプロジェクトだけアクセス可能
ALTER TABLE projects ENABLE ROW LEVEL SECURITY;

CREATE POLICY "ユーザーは自分のプロジェクトのみ操作可能"
  ON projects FOR ALL
  USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);

-- インデックス
CREATE INDEX idx_projects_user_id ON projects(user_id);
CREATE INDEX idx_projects_status ON projects(user_id, status);
CREATE INDEX idx_projects_updated_at ON projects(user_id, updated_at DESC);

-- ユーザー設定テーブル（APIキーなど）
CREATE TABLE IF NOT EXISTS user_settings (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     UUID REFERENCES auth.users(id) ON DELETE CASCADE NOT NULL UNIQUE,
  openai_key  TEXT NOT NULL DEFAULT '',
  gemini_key  TEXT NOT NULL DEFAULT '',
  gemini_model TEXT NOT NULL DEFAULT 'gemini-3-flash-preview',
  openrouter_key TEXT NOT NULL DEFAULT '',
  openrouter_model TEXT NOT NULL DEFAULT 'google/gemini-3-flash',
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TRIGGER user_settings_updated_at
  BEFORE UPDATE ON user_settings
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- RLS: 自分の設定だけアクセス可能
ALTER TABLE user_settings ENABLE ROW LEVEL SECURITY;

CREATE POLICY "ユーザーは自分の設定のみ操作可能"
  ON user_settings FOR ALL
  USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);

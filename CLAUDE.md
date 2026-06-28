# CLAUDE.md — VoiceSlide AI Movie

## プロジェクト概要

音声から自動で高品質なプレゼンテーション動画を生成する AI SaaS。
Next.js 16 / React 19 / Supabase / Python FastAPI / Tailwind CSS。

## Git ワークフロー

- **develop**: 開発・検証用ブランチ（Railway で自動デプロイ）
- **main**: 本番用ブランチ（develop で確認後にマージ）
- 作業は必ず **develop ブランチ** で行うこと
- main への直接コミットは禁止

## ハーネス設計（自律開発フロー）

機能追加・修正は以下の3エージェントで自律的に進める。

### 1. Planner（仕様設計）
- ユーザーの要件から詳細な仕様書を作成
- 出力先: `docs/specs/[機能名].md`
- 「何を作るか」に集中、技術詳細には踏み込まない

### 2. Generator（実装）
- 仕様書に基づいて1スプリントずつ実装
- テストも合わせて書く
- 自己評価してから Evaluator に引き渡す

### 3. Evaluator（レビュー・テスト）
- コードレビュー + テスト実行 + 画面確認（Claude Preview MCP）
- 不合格なら具体的なフィードバック付きで Generator に差し戻し
- 合格したら次のスプリントへ進む

### フロー

```
ユーザー要件 → Planner → 仕様書
                            ↓
                        Generator → 実装 + テスト
                            ↓
                        Evaluator → レビュー
                          ↓           ↓
                        不合格      合格
                          ↓           ↓
                     Generator    次のスプリント or 完了
                     （修正）
```

### ルール
- **差し戻しは最大3回**: 3回で解決しなければユーザーにエスカレーション
- **既存機能を壊さない**: リグレッションテストを必ず実行
- **develop ブランチで作業**: すべての作業は develop で行う
- **⚠️ main への マージは絶対に自動で行わない**: develop で完了 → ユーザーが手動確認 → ユーザーの指示があって初めて main にマージ。本番環境にユーザーがいるため、未完成コードの main マージは厳禁

## テストコマンド

```bash
# フロントエンド
npm test

# バックエンド
cd backend && python -m pytest tests/ -v

# ビルド確認
npm run build

# ローカル起動
npm run dev
```

## ディレクトリ構成

```
app/              # Next.js App Router（ページ）
components/       # React コンポーネント
backend/          # Python FastAPI バックエンド
  services/       # ビジネスロジック
  tests/          # pytest テスト
__tests__/        # Jest テスト
docs/specs/       # 仕様書（Planner が生成）
lib/              # ユーティリティ（Supabase等）
public/           # 静的ファイル
```

## 品質基準

- UI は既存のデザインと一貫性を保つ
- 機能は実際に動作すること（スタブやモックで誤魔化さない）
- エッジケース（空入力、長文、連打）を考慮する
- TypeScript の型を正しく使う
- エラーハンドリングを省略しない

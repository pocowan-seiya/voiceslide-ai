# APIモデル切替バグ修正 仕様書

## 概要
APIキー設定で選択したモデル（OpenRouter / Gemini）がアウトライン改善（polish-outline）ステップに反映されないバグを修正する。

## 背景・目的
ユーザーがOpenRouterで高品質なモデル（Claude Opus、GPT-4.1等）を選択しても、アウトライン改善ステップでは環境変数のGemini APIキーがハードコードで使われており、モデル選択が無視される。フロントエンドからのヘッダー送信漏れとバックエンドのパラメータ受け取り漏れが複合的に発生している。

## 原因分析

### バグ1: フロントエンド `handlePolishOutline` がAPIヘッダーを送信していない
- **場所**: `app/page.tsx` 898行目付近
- **内容**: `handleGenerateOutline` は `...getAPIHeaders()` を正しく送信しているが、`handlePolishOutline` は `Content-Type` のみ
- **対策**: `...getAPIHeaders()` を追加

### バグ2: バックエンド `/api/polish-outline` が `x_gemini_key` / `x_gemini_model` を受け取らない
- **場所**: `backend/main.py` 1357-1363行目
- **内容**: `x_openrouter_key` と `x_openrouter_model` はあるが、Gemini系パラメータが欠落
- **対策**: `x_gemini_key`, `x_gemini_model` パラメータを追加

### バグ3: `outline_generator.py` の `polish_outline()` がユーザー提供のGeminiキーを受け取らない
- **場所**: `backend/services/outline_generator.py` 684行目、701行目
- **内容**: `generate_outline()` は `gemini_key` パラメータがあるが、`polish_outline()` にはなく環境変数をハードコード使用
- **対策**: `gemini_key` パラメータを追加し、フォールバックとして環境変数を使用

### バグ4: バックエンド `/api/generate-slides` (非バッチ) がOpenRouterヘッダーを受け取らない
- **場所**: `backend/main.py` 1418-1424行目
- **内容**: Gemini系パラメータのみで、OpenRouter系が欠落
- **対策**: OpenRouter パラメータを追加（防御的修正）

### バグ5: `pipeline.step_polish_outline()` が `gemini_key` を下流に渡さない
- **場所**: `backend/services/pipeline.py` 187行目
- **内容**: `model_name`, `openrouter_key`, `openrouter_model` のみ���し、`gemini_key` が欠落
- **対策**: `gemini_key` パラメータを追加して下流に渡す

## データフロー図

```
[フロントエンド]                [バックエンド main.py]              [サービス層]
handleGenerateOutline           /api/generate-outline               outline_generator.generate_outline
  headers: getAPIHeaders() OK    x_gemini_key: OK                    gemini_key: OK
                                 x_openrouter_key: OK                openrouter_key: OK

handlePolishOutline             /api/polish-outline                  outline_generator.polish_outline
  headers: なし NG               x_gemini_key: なし NG                gemini_key: パラメータなし NG
                                 x_gemini_model: なし NG              → 環境変数ハードコード
                                 x_openrouter_key: OK (定義あり)
                                 x_openrouter_model: OK (定義あり)
```

## 要件

- [ ] handlePolishOutline が getAPIHeaders() をリクエストヘッダーに含めること
- [ ] /api/polish-outline エンドポイントが x_gemini_key, x_gemini_model ヘッダーを受け取ること
- [ ] outline_generator.polish_outline() が gemini_key パラメータを受け取り、ユーザー提供キーを優先すること
- [ ] pipeline.step_polish_outline() が gemini_key を下流に渡すこと
- [ ] /api/generate-slides (非バッチ) が OpenRouter ヘッダーを受け取ること
- [ ] 既存の generate-outline, generate-slides-batch の動作が壊れないこと

## スプリント計画

### Sprint 1: フロントエンド handlePolishOutline のヘッダー修正
- **対象ファイル**: `app/page.tsx`
- **修正内容**: handlePolishOutline の fetch 呼び出しに `...getAPIHeaders()` を追加
- **受け入れ条件**:
  1. handlePolishOutline の fetch ヘッダーに x-openrouter-key, x-openrouter-model, x-gemini-key, x-gemini-model が含まれること
  2. ビルドが通ること

### Sprint 2: バックエンド polish-outline エンドポイント + サービス層の修正
- **対象ファイル**: `backend/main.py`, `backend/services/pipeline.py`, `backend/services/outline_generator.py`
- **修正内容**:
  - `/api/polish-outline` に `x_gemini_key`, `x_gemini_model` パラメータ追加
  - `outline_generator.polish_outline()` に `gemini_key` パラメータ追加（環境変数フォールバック）
  - `pipeline.step_polish_outline()` に `gemini_key` を下流に渡す
  - `jobs` dict にキー情報を保存
- **受け入れ条件**:
  1. OpenRouter キー/モデルが設定時、polish-outline が OpenRouter 経由で指定モデルを使用
  2. Gemini キーのみの場合、そのキーで Gemini API を呼ぶ
  3. どちらも無い場合は環境変数の GEMINI_API_KEY にフォールバック
  4. テストが通ること

### Sprint 3: 非バッチ generate-slides エンドポイントの防御的修正 + テスト
- **対象ファイル**: `backend/main.py`, テストファイル
- **修正内容**:
  - `/api/generate-slides` に OpenRouter パラメータを追加
  - 全修正のリグレッションテスト追加
- **受け入れ条件**:
  1. OpenRouter パラメータが generate_all_custom_slides に正しく渡されること
  2. 既存のバッチエンドポイントの動作が変わらないこと
  3. 全テストパス

## 影響範囲

- `app/page.tsx` — handlePolishOutline のヘッダー追加
- `backend/main.py` — polish-outline, generate-slides エンドポイント
- `backend/services/outline_generator.py` — polish_outline() のパラメータ追加
- `backend/services/pipeline.py` — step_polish_outline() のパラメータ追加

## 対象外（スコープ外）

- フロントエンドUIの変更（モデル選択UIは正常に動作）
- 新しいモデルの追加
- OpenRouter/Gemini以外のプロバイダー対応
- 画像生成（イラスト）のモデル切替

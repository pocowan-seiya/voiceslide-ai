# VoiSlide Movie Sprint 1〜2 固定fixture再生成QA

## 基本情報

- 実施日: 2026-05-03 11:00 JST
- 対象: VoiSlide Movie backend Sprint 1〜2 telemetry / Design QA metric
- ブランチ: `develop`
- 音声fixture: `docs/qa/fixtures/short_voislide_quality_check_32s.mp3`
- 比較対象: `flash_standard` / `pro`
- 実行者: Hermes Agent

## 実行コマンド

```bash
cd /Users/seiyaeto/Antigravity/voiceslide-ai/backend
./venv/bin/python -m py_compile main.py services/generation_telemetry.py services/design_quality_metrics.py services/ai_utils.py services/openrouter_utils.py services/ai_slide_generator.py
./venv/bin/python -m pytest tests/test_generation_telemetry.py tests/test_design_quality_metrics.py tests/test_design_mode.py -q
```

結果:

```text
37 passed, 9 warnings in 0.86s
```

warningsは `httplib2/auth.py` のDeprecationWarning。

## 実API QA結果

FastAPI appに対して固定fixtureをuploadし、固定outlineをセットして `/api/generate-slides-batch/{job_id}` を `flash_standard` / `pro` で実行した。

結果: **実AI生成は未完了**。

理由:

```text
Gemini API key is required
```

これはアプリの回帰ではなく、Hermes実行環境にVoiSlide backendが参照できるAI APIキーがないことによるQA環境ブロッカー。
APIキー値は読んでいない。

### flash_standard

- job_id: `249c7152-d5c3-4c99-9697-4a15122e881b`
- `/api/upload-audio`: 成功
- `audio_storage_status`: `skipped`
- `audio_storage_detail`: `missing_user_or_project_id`（ローカル直接APIでは想定内）
- `/api/batch-status/{job_id}`: `error`
- message: `エラー: Gemini API key is required`
- `/api/status/{job_id}` に `generation_telemetry_summary`: あり
- `/api/status/{job_id}` に `design_quality_metrics`: なし（生成前に停止）

### pro

- job_id: `1fed891a-adeb-4c8e-a496-07ace42bd991`
- `/api/upload-audio`: 成功
- `audio_storage_status`: `skipped`
- `audio_storage_detail`: `missing_user_or_project_id`（ローカル直接APIでは想定内）
- `/api/batch-status/{job_id}`: `error`
- message: `エラー: Gemini API key is required`
- `/api/status/{job_id}` に `generation_telemetry_summary`: あり
- `/api/status/{job_id}` に `design_quality_metrics`: なし（生成前に停止）

詳細JSON:

- `/tmp/voislide_fixed_fixture_sprint12_qa.json`

## 外部AIなしの統合QA

外部AIキーなしでもSprint 1〜2のstatus露出を確認するため、AI生成部だけをmockしたASGI統合QAを実行した。
これは実生成比較ではなく、`/api/status` と `/api/batch-status` のレスポンス形状確認。

### mock QA結果

- `flash_standard`: batch complete
- `pro`: batch complete
- `/api/batch-status/{job_id}` に `generation_telemetry_summary`: あり
- `/api/batch-status/{job_id}` に `design_quality_metrics`: あり
- `/api/status/{job_id}` に `generation_telemetry_summary`: あり
- `/api/status/{job_id}` に `design_quality_metrics`: あり
- 小さい文字を含む2枚目のHTMLは `quality_gate: fail` として検出

| mode | telemetry entries | fallback_count | quality gates | min font sizes | small text counts |
|---|---:|---:|---|---|---|
| flash_standard | 3 | 0 | `pass`, `fail` | 32px, 18px | 0, 1 |
| pro | 3 | 0 | `pass`, `fail` | 32px, 18px | 0, 1 |

詳細JSON:

- `/tmp/voislide_sprint12_mock_integration_qa.json`

## 見つかった問題

### 1. QA環境ブロッカー: 実AI生成に必要なキーがbackendから参照できない

- 影響: 固定fixtureの実生成比較、実データのtoken/cost/quality metric確認ができない。
- 分類: QA環境ブロッカー。アプリ回帰ではない。
- 次: visible Chrome/CDP共有QA、またはbackendが安全にキーを参照できるローカル実行方法で再実施。

### 2. `generation_telemetry_summary.total_calls` と実装フィールド名が不一致（修正済み）

QAテンプレートとSprint 1〜2チェック項目では `generation_telemetry_summary.total_calls` を期待していた。
実レスポンスでは `entry_count` のみが返っていた。

2026-05-03 12:59 JSTに修正済み。
`TelemetryCollector.summary()` は後方互換用の `entry_count` を残しつつ、同じ値を `total_calls` として返す。

検証:

```text
37 passed, 9 warnings in 0.70s
```

- 影響: 解消済み。
- 次: AIキー設定済み共有QA環境で実生成比較を再実施する。

## 判定

- Sprint 1〜2の自動テスト: pass
- 固定fixtureの実AI再生成: blocked
- status/batch-statusのtelemetry/metric露出: mock統合QAではpass
- 小さい文字検出: mock統合QAではpass

## 次アクション

1. `generation_telemetry_summary.total_calls` / `entry_count` の命名不一致を修正する。
2. AIキー設定済みの共有QA環境で、同じ固定fixtureを `flash_standard` / `pro` で再生成する。
3. 実データのtelemetry、fallback_count、token、cost、design_quality_metricsを比較結果へ追記する。
4. その結果を使ってSprint 3のプロンプト/レイアウト改善に進む。

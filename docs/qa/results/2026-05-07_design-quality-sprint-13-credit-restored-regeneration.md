# VoiSlide Design Quality Sprint 13 — Credit restored real regeneration

Date: 2026-05-07 11:21 JST

## 実施内容

OpenRouter credit補充後、Sprint 12と同じ固定fixtureで real generation を再runした。

## Setup

- Origin: `http://127.0.0.1:3010/`
- Backend: `http://127.0.0.1:8001`
- Fixture: `docs/qa/fixtures/short_voislide_quality_check_32s.mp3`
- Visible Chrome/CDP: port `9223`
- API key/model presence: OpenAI / Gemini / OpenRouter / model settings すべて存在確認のみOK

APIキー値は出力・保存していない。

## 結果

今回はOpenRouterのcredit不足ブロックは解消した。

両モードとも以下の成功経路に到達した。

- strategy call: success path到達
- slide HTML generation: 2 slides成功
- self-review: 2回成功
- self-review diagnostic: 発火

ただし、strategy JSON parseはまだ失敗しており、`fallback:Strategy generation failed` が各モード1件残った。slide HTMLとself-reviewは実OpenRouter呼び出しで成功した。

## flash_standard

```text
job_id: eec8c920-a619-4b2a-a96e-2003309f89f6
entry_count: 7
total_calls: 7
fallback_count: 1
strategy_count: 1
slide_html_count: 2
self_review_count: 2
self_review_diagnostic_count: 1
fallback_stage_counts:
  fallback:Strategy generation failed: 1
Design QA: 0/2 pass, 2/2 fail
small_text_total: 6
```

Design QA details:

```text
slide 1: fail, min_font_size_px=17.6, title_font_size_px=96.0, small_text_count=1
slide 2: fail, min_font_size_px=15.2, title_font_size_px=48.0, small_text_count=5
```

## pro

```text
job_id: e5d27c62-ba0a-4483-a1d0-19775449b509
entry_count: 8
total_calls: 8
fallback_count: 1
strategy_count: 1
slide_html_count: 2
self_review_count: 2
self_review_diagnostic_count: 2
fallback_stage_counts:
  fallback:Strategy generation failed: 1
Design QA: 0/2 pass, 2/2 fail
small_text_total: 5
```

Design QA details:

```text
slide 1: fail, min_font_size_px=16.0, title_font_size_px=112.0, small_text_count=1
slide 2: fail, min_font_size_px=16.0, title_font_size_px=112.0, small_text_count=4
```

## Vision review

Contact sheetをvision確認した。

- `pro` は `flash_standard` より視覚階層、余白、中央配置、完成度が高い。
- `flash_standard_slide_002` は右側の説明文が小さく、metric failと視覚印象が一致。
- `pro` は見た目はかなり改善しているが、16px級の小さい文字が残り、metric failは完全な誤検知ではない。
- 今回は「provider成功経路に到達したうえで、小さい文字問題が実データとして再発した」と扱うのが正しい。

## 保存先

```text
docs/qa/results/2026-05-07_design-quality-sprint-13-credit-restored-regeneration.md
docs/qa/results/2026-05-07_design-quality-sprint-13-credit-restored-regeneration/sanitized_api_result.json
docs/qa/results/2026-05-07_design-quality-sprint-13-credit-restored-regeneration/summary.json
docs/qa/results/2026-05-07_design-quality-sprint-13-credit-restored-regeneration/artifact_hashes.json
docs/qa/results/2026-05-07_design-quality-sprint-13-credit-restored-regeneration/comparison_contact_sheet.jpg
docs/qa/results/2026-05-07_design-quality-sprint-13-credit-restored-regeneration/flash_standard_slide_001.png
docs/qa/results/2026-05-07_design-quality-sprint-13-credit-restored-regeneration/flash_standard_slide_002.png
docs/qa/results/2026-05-07_design-quality-sprint-13-credit-restored-regeneration/pro_slide_001.png
docs/qa/results/2026-05-07_design-quality-sprint-13-credit-restored-regeneration/pro_slide_002.png
```

## Artifact hashes

```text
flash_standard_slide_001.png 98afac3f1dc839120e6a7778bd7236c6a654a9e037eefbd0ead37140a5b0293f
flash_standard_slide_002.png 9ffa046571678a847d24787cf2b7dbe45104b932d6c0ad47162b0858e5b3f860
pro_slide_001.png            3f979978342865e66a4871abc6eea6d6e6007578e0f1f191854622f3b546825d
pro_slide_002.png            74a22771165c17c06975bd1734d8ec2cc0e578b5e0f6be57020ed864965ec9a0
```

4枚すべて別hash。mode collapse再発なし。

## 検証

```text
backend py_compile: pass
targeted pytest: 71 passed, 11 warnings
git diff --check: pass
```

## 次

Sprint 14候補:

1. strategy JSON parse失敗の原因を特定する。
2. 実生成HTMLの小さい文字を減らす。特に `flash_standard_slide_002` と `pro` の16px級テキスト。
3. self-review diagnosticが `decision=keep_original` になっているため、self-reviewがタイトルを書き換えがちな原因を追う。

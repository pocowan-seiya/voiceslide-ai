# VoiSlide telemetry total_calls visible Chrome real-generation QA

## 基本情報

| 項目 | 値 |
|---|---|
| 実施日時 | 2026-05-04 18:53–18:56 JST |
| 評価者 | Hermes Agent |
| Frontend | `http://127.0.0.1:3010/` |
| Backend | `http://127.0.0.1:8001` |
| CDP | visible Chrome / `~/.hermes/chrome-voislide` / port `9223` |
| fixture | `docs/qa/fixtures/short_voislide_quality_check_32s.mp3` |
| 目的 | 実生成レスポンスで `generation_telemetry_summary.total_calls` と `design_quality_metrics` が返ることを確認する |

## セキュリティ

- APIキーは共有Chromeの画面設定を使用。
- 値は出力・保存していない。
- 確認したのは presence のみ。

```json
{
  "openai": true,
  "gemini": true,
  "geminiModel": true,
  "openrouter": true,
  "openrouterModel": true,
  "openrouterDesignModel": true
}
```

## 実生成結果

### flash_standard

| 項目 | 値 |
|---|---|
| job_id | `b7384617-328b-4e91-a5d5-b6ea12a2e69e` |
| 音声保存 | `skipped`（local API directのため想定内） |
| transcript_length | 189 |
| outline_slide_count | 2 |
| batch-status | `complete` |
| `/api/batch-status` total_calls | 6 |
| `/api/batch-status` entry_count | 6 |
| `/api/status` total_calls | 6 |
| `/api/status` entry_count | 6 |
| total_duration_ms | 71432 |
| fallback_count | 1 |
| input/output tokens | 12060 / 9104 |
| design_quality_metrics_count | 2 |

Design metrics summary:

| slide | min_font_size_px | title_font_size_px | small_text_count | fallback_used | quality_gate |
|---:|---:|---:|---:|---|---|
| 1 | 16.0 | 84.0 | 1 | true | fail |
| 2 | 16.0 | 72.0 | 1 | true | fail |

### pro

| 項目 | 値 |
|---|---|
| job_id | `61763fc8-15af-48af-8a40-bd08297f1301` |
| 音声保存 | `skipped`（local API directのため想定内） |
| transcript_length | 189 |
| outline_slide_count | 2 |
| batch-status | `complete` |
| `/api/batch-status` total_calls | 6 |
| `/api/batch-status` entry_count | 6 |
| `/api/status` total_calls | 6 |
| `/api/status` entry_count | 6 |
| total_duration_ms | 73231 |
| fallback_count | 1 |
| input/output tokens | 13433 / 9745 |
| design_quality_metrics_count | 2 |

Design metrics summary:

| slide | min_font_size_px | title_font_size_px | small_text_count | fallback_used | quality_gate |
|---:|---:|---:|---:|---|---|
| 1 | 13.0 | 116.0 | 3 | false | fail |
| 2 | 16.0 | 72.0 | 1 | true | fail |

## 保存した生成物

Folder:

`docs/qa/results/2026-05-04_telemetry-total-calls-visible-chrome-real-generation/`

| ファイル | サイズ | SHA256先頭16桁 |
|---|---:|---|
| `flash_standard_slide_001.png` | 717,098 | `abb51af2c42058ea` |
| `flash_standard_slide_002.png` | 655,227 | `3179e11eeee8ef95` |
| `pro_slide_001.png` | 883,781 | `b07b7be416d89906` |
| `pro_slide_002.png` | 649,473 | `62c983ca1905f42a` |
| `comparison_contact_sheet.jpg` | 81,663 | `047b7e3c2d4b4df6` |
| `sanitized_api_result.json` | 6,294 | `a46dfbdcb65c4f3e` |

## 確認できたこと

- `flash_standard` / `pro` の実生成が両方完了した。
- `/api/batch-status/{job_id}` で `generation_telemetry_summary.total_calls` が返る。
- `/api/status/{job_id}` でも `generation_telemetry_summary.total_calls` が返る。
- 両方とも `total_calls == entry_count` だった。
- `design_quality_metrics` は両APIで配列として返った。
- `design_quality_metrics_count == 2` で、生成スライド数と一致した。

## 観察

- `pro` は表紙スライドで明確に優位。タイトルが大きく、余白と視覚階層が安定している。
- `flash_standard` は成立しているが、テンプレート感とfallback感が強い。
- `quality_gate` は両モードとも fail。小さい文字とfallback検出が理由。
- `pro` slide 1 は `fallback_used=false` だが、min font 13px / small text 3 で fail。
- `pro` slide 2 は fallback used true。

## 結論

`total_calls` 追加は実生成レスポンスでも問題なし。  
`/api/batch-status` と `/api/status` の両方で `entry_count` と同値で返っている。  
QAテンプレートや将来UIは `generation_telemetry_summary.total_calls` を読める。

デザイン品質面では、`pro` が表紙で優位。ただし `quality_gate` はまだ fail なので、次の改善対象は小さい文字・fallback発生・内容スライド品質。

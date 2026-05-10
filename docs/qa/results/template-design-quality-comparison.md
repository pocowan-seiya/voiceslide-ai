# デザイン品質比較 QA — テンプレート

> このファイルをコピーして `{日付}_{比較対象}_{音声サンプル名}.md` として保存する。

## 基本情報

| 項目 | 値 |
|------|---|
| 実施日 | YYYY-MM-DD |
| 評価者 | |
| 音声サンプル | `fixtures/` 内のファイル名 |
| 比較目的 | （例: Pro モード改善前後の比較） |

---

## モード A: ___________

| 項目 | 値 |
|------|---|
| モード名 | flash_standard / pro / image-background / other |
| モデル ID | （例: gemini-2.5-flash, claude-opus-4-6 via OpenRouter） |
| 生成時間 | 秒 |
| 推定 API コスト | $ |
| エラー/フォールバック | なし / あり（詳細: ） |

### Sprint 1〜2 自動メトリクス

| 項目 | 値 |
|------|---|
| `generation_telemetry_summary.total_calls` | |
| `generation_telemetry_summary.fallback_count` | |
| `generation_telemetry_summary.total_input_tokens` | |
| `generation_telemetry_summary.total_output_tokens` | |
| `design_quality_metrics[].quality_gate` | pass / warn / fail |
| 最小文字サイズ | px |
| 小さい文字件数 | |
| 備考 | HTML/CSS文字列ベース。画像解析は未実装。 |

### ルーブリックスコア

| # | 項目 | スコア (1-5) | コメント |
|---|------|:---:|----------|
| 1 | Copy Fidelity | | |
| 2 | Readability | | |
| 3 | Whitespace | | |
| 4 | Visual Hierarchy | | |
| 5 | Continuity | | |
| 6 | Audio Fit | | |
| 7 | Editability | | |
| 8 | Restore Safety | | |
| 9 | Performance | | |
| 10 | Cost Awareness | | |
| | **合計** | /50 | |

### 所感

- 見た目:
- 音声同期:
- 復元結果: 正常 / 異常（詳細: ）

---

## モード B: ___________

| 項目 | 値 |
|------|---|
| モード名 | flash_standard / pro / image-background / other |
| モデル ID | |
| 生成時間 | 秒 |
| 推定 API コスト | $ |
| エラー/フォールバック | なし / あり（詳細: ） |

### Sprint 1〜2 自動メトリクス

| 項目 | 値 |
|------|---|
| `generation_telemetry_summary.total_calls` | |
| `generation_telemetry_summary.fallback_count` | |
| `generation_telemetry_summary.total_input_tokens` | |
| `generation_telemetry_summary.total_output_tokens` | |
| `design_quality_metrics[].quality_gate` | pass / warn / fail |
| 最小文字サイズ | px |
| 小さい文字件数 | |
| 備考 | HTML/CSS文字列ベース。画像解析は未実装。 |

### ルーブリックスコア

| # | 項目 | スコア (1-5) | コメント |
|---|------|:---:|----------|
| 1 | Copy Fidelity | | |
| 2 | Readability | | |
| 3 | Whitespace | | |
| 4 | Visual Hierarchy | | |
| 5 | Continuity | | |
| 6 | Audio Fit | | |
| 7 | Editability | | |
| 8 | Restore Safety | | |
| 9 | Performance | | |
| 10 | Cost Awareness | | |
| | **合計** | /50 | |

### 所感

- 見た目:
- 音声同期:
- 復元結果: 正常 / 異常（詳細: ）

---

## モード C（オプション）: ___________

> 3 モード以上を比較する場合に使用。不要なら削除。

| 項目 | 値 |
|------|---|
| モード名 | |
| モデル ID | |
| 生成時間 | 秒 |
| 推定 API コスト | $ |
| エラー/フォールバック | なし / あり（詳細: ） |

### Sprint 1〜2 自動メトリクス

| 項目 | 値 |
|------|---|
| `generation_telemetry_summary.total_calls` | |
| `generation_telemetry_summary.fallback_count` | |
| `generation_telemetry_summary.total_input_tokens` | |
| `generation_telemetry_summary.total_output_tokens` | |
| `design_quality_metrics[].quality_gate` | pass / warn / fail |
| 最小文字サイズ | px |
| 小さい文字件数 | |
| 備考 | HTML/CSS文字列ベース。画像解析は未実装。 |

### ルーブリックスコア

| # | 項目 | スコア (1-5) | コメント |
|---|------|:---:|----------|
| 1 | Copy Fidelity | | |
| 2 | Readability | | |
| 3 | Whitespace | | |
| 4 | Visual Hierarchy | | |
| 5 | Continuity | | |
| 6 | Audio Fit | | |
| 7 | Editability | | |
| 8 | Restore Safety | | |
| 9 | Performance | | |
| 10 | Cost Awareness | | |
| | **合計** | /50 | |

### 所感

- 見た目:
- 音声同期:
- 復元結果: 正常 / 異常（詳細: ）

---

## 比較サマリ

| 項目 | モード A | モード B | モード C |
|------|:---:|:---:|:---:|
| 合計スコア | /50 | /50 | /50 |
| 生成時間 | s | s | s |
| コスト | $ | $ | $ |
| 失敗 | | | |

## 結論

- 優れていたモード:
- 主な差分が出た項目:
- 改善アクション:
- 次のステップ:

---

## 参考スクリーンショット

> `docs/qa/results/screenshots/` に配置し、ここからリンクする。

- モード A: `screenshots/YYYY-MM-DD_modeA_slide01.png`
- モード B: `screenshots/YYYY-MM-DD_modeB_slide01.png`

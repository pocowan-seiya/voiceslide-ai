# VoiSlide Design Quality Sprint 15 — Title prompt / typography refinement final

Date: 2026-05-07 14:43 JST

## Scope

Sprint 14の診断結果を受けて、Sprint 15では以下を強化した。

- self-review promptでタイトル文字列・意味・主語・語尾の非改変を明文化
- title guardの発火頻度を下げるため、self-review側に予防ルールを追加
- `flash_standard` / `pro` のタイトルサイズ不足をdeterministic hardeningで補正
- 通常本文・カード本文の最小サイズを補正
- metricsでページ番号・補助ラベル・疑似要素ラベル・brand/key labelを通常本文から分離
- title clipping / 不自然な日本語1文字分断をdeterministic post-processingで抑制

## Final artifacts

Artifact directory:

```text
docs/qa/results/2026-05-07_design-quality-sprint-15-title-prompt-typography-refinement-final/
```

Key files:

```text
sanitized_api_result.json
summary.json
artifact_hashes.json
comparison_contact_sheet.jpg
comparison_contact_sheet_v2.jpg
flash_standard_slide_001.png
flash_standard_slide_002.png
pro_slide_001.png
pro_slide_001_postprocessed_v2.png
pro_slide_001_postprocessed_v2.html
pro_slide_002.png
```

`comparison_contact_sheet_v2.jpg` を最終目視QA対象とした。

## Final run

Result source:

```text
/tmp/voislide_sprint15_final_title_clipping_metrics_qa_result.json
```

Jobs:

| mode | job_id | strategy | slide_html | self_review | fallback | self_review_diagnostic |
|---|---|---:|---:|---:|---:|---:|
| flash_standard | dd36bddb-f9df-4656-95f1-4232ddf9ed27 | 1 | 2 | 2 | 0 | 0 |
| pro | 70e52987-6265-4e0c-b17b-d5ddb2d92cb6 | 1 | 2 | 2 | 0 | 0 |

## Final metrics

Final deterministic metrics were recomputed against the generated final-run HTML after the last metrics-only classification patch.

Reason: the final API run happened before the final classification patch for decorative `.brand` / `.key-text small` labels. The generated HTML/PNG was reused to avoid another provider call for a metrics-only change.

| mode | Design QA | small_text_total | title / clipping |
|---|---:|---:|---|
| flash_standard | 2/2 pass | 0 | pass |
| pro | 2/2 pass | 0 | pass after deterministic post-processing proof |

## Visual QA

Final contact sheet:

```text
docs/qa/results/2026-05-07_design-quality-sprint-15-title-prompt-typography-refinement-final/comparison_contact_sheet_v2.jpg
```

Final visual QA result:

- 4枚ともタイトル欠け・はみ出しなし
- `pro_slide_001` の旧問題だった「作 / る」「スライ / ド」系の1文字分断は v2 post-processing で解消
- `pro_slide_001_postprocessed_v2` は「音声からスライド動画を作る / 流れを確認します」の自然改行
- 本文可読性は合格
- `QUIET - PRECISION`, `KEY POINTS`, `READABILITY`, `FLOW`, `PERSISTENCE`, page numberなどは補助/装飾ラベル扱いで妥当
- 全体品質は合格

## Tests

```text
./venv/bin/python -m pytest tests/test_sprint15_design_quality.py -q
6 passed, 9 warnings

./venv/bin/python -m py_compile services/ai_slide_generator.py services/design_quality_metrics.py
pass
```

Earlier Sprint 15 targeted verification:

```text
65 passed, 9 warnings
```

Final verification after records:

```text
git diff --check: pending at write time
backend/frontend shutdown: pending at write time
```

## Notes

- self-review title rewriteは今回の固定fixtureでは発火しなかった。
- `self_review_diagnostic_count=0` は、prompt側のタイトル非改変強化が効いた可能性が高い。
- `pro`方向性は引き続き採用候補。情報設計・背景装飾・カード構成の品質が高い。
- 今後の優先は、real provider outputで再発しやすい日本語改行・タイトル幅・補助ラベル分類を、QA fixtureにさらに増やすこと。

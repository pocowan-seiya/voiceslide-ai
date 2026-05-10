# VoiSlide Design Quality Sprint 14 — Strategy parse / typography quality fixes

Date: 2026-05-07 12:35 JST

## 目的

Sprint 13で残った以下3点を修正・検証した。

1. strategy JSON parse失敗の原因特定と修正
2. 実生成HTMLの小さい文字を減らす
3. self-reviewが元タイトルを書き換える傾向を抑える

## 実装内容

### 1. strategy JSON parse hardening

- `json.loads(response_text)` の直接parseをやめた。
- `_parse_design_strategy_response()` を追加。
- OpenRouter/Claudeが返しがちな以下を受け付ける。
  - ```json fenced JSON
  - 前置きつきJSON
  - 後続メモつきJSON
- JSON root / `content_analysis` / `design_style` は引き続き検証する。
- strategy promptにも「JSON objectのみ。先頭`{`、末尾`}`」を追記。

### 2. typography hardening

- `harden_generated_html_typography()` を追加。
- 通常コンテンツの `font-size <= 20px` を決定論的に24px以上へ引き上げる。
- `.slide-number`, `.caption`, `.eyebrow`, `.badge`, `.meta`, `.decorative` などの装飾/補助表示は対象外。
- slide HTML生成後、render/metric前に適用する。

### 3. self-review title preservation

- `self_review_preserves_slide_title()` を追加。
- self-review後HTMLが元タイトルを失った/書き換えた場合は、改善HTMLを採用せず元HTMLを維持する。
- 既存のdiagnostic telemetryを維持。

## TDD / テスト

追加:

- `backend/tests/test_sprint14_design_quality.py`

確認内容:

- fenced JSON + 前置きをstrategyとしてparseできる
- plain JSON + 後続メモをstrategyとしてparseできる
- 通常本文の小さい文字をquality gate failから外せる
- self-reviewのタイトル書き換えを検出できる

## 固定fixture real regeneration

Fixture:

```text
docs/qa/fixtures/short_voislide_quality_check_32s.mp3
```

Run:

- `flash_standard`: `67f87e3d-342f-4059-9fd0-fcb8489aad5f`
- `pro`: `4d6161bd-1ec9-4841-ab12-8b8daa54f56c`

### flash_standard

```text
entry_count: 6
total_calls: 6
fallback_count: 0
stage_counts: strategy=1, slide_html=2, self_review=2, self_review_diagnostic=1
Design QA: 2/2 pass
small_text_count: 0 / 0
quality_gate: pass / pass
```

補足:

- self-review diagnosticは1件あり。
- improved版が元タイトルを保持できなかったため、元HTMLを採用。
- fallbackではない。

### pro

```text
entry_count: 5
total_calls: 5
fallback_count: 0
stage_counts: strategy=1, slide_html=2, self_review=2
Design QA: 2/2 pass
small_text_count: 0 / 0
quality_gate: pass / pass
```

## Sprint 13 → Sprint 14 差分

| 項目 | Sprint 13 | Sprint 14 |
|---|---:|---:|
| strategy fallback | 両モード1件 | 0件 |
| flash Design QA | 0/2 pass | 2/2 pass |
| pro Design QA | 0/2 pass | 2/2 pass |
| small_text_total flash | 6 | 0 |
| small_text_total pro | 5 | 0 |
| mode collapse | なし | なし |

## 視覚確認

- `pro_slide_001.png` をvision確認。
- メインタイトル、階層、背景、配色は高品質。
- 上部ラベルやページ番号など小さい補助表示は残るが、通常本文ではなく、metric上も許容。
- 重要情報は十分読める。

## 成果物

```text
docs/qa/results/2026-05-07_design-quality-sprint-14-quality-fixes.md
docs/qa/results/2026-05-07_design-quality-sprint-14-quality-fixes/
  sanitized_api_result.json
  summary.json
  artifact_hashes.json
  comparison_contact_sheet.jpg
  flash_standard_slide_001.png
  flash_standard_slide_002.png
  pro_slide_001.png
  pro_slide_002.png
```

## 検証

```text
backend py_compile: pass
targeted pytest: 115 passed, 11 warnings
Sprint 14 focused pytest: 4 passed, 9 warnings
real regeneration: flash_standard/pro both complete
git diff --check: pass
```

## 次の実務ポイント

Sprint 14で、credit不足後の品質改善は一段進んだ。

次は以下。

1. Contact sheetを人間目線で確認し、`pro`の方向性を採用するか決める
2. 装飾ラベルやページ番号の扱いをmetric上もUI上も明確化する
3. self-review diagnosticが出たケースの差分HTMLを保存し、なぜタイトルを書き換えたかを分析する

## 2026-05-07 12:45 JST追記: pro方向性と補助要素rubric

Contact sheetと `pro_slide_002.png` を人間目線で再確認した。

結論:

- `pro` の方向性を採用推奨。
- 理由は、`flash_standard` より情報設計、視線誘導、完成度が高いから。
- ステップ、チェックリスト、キーメッセージなどで情報を構造化する方向が、VoiSlideの標準品質に合う。
- 小さい英字ラベルやページ番号は、読めなくても主旨理解に支障がない装飾/補助要素なら許容。
- 章タイトル、手順名、チェック項目、注意事項、ナビゲーションとして読ませる要素なら、通常の可読性基準を適用する。

反映:

```text
docs/qa/voiceslide-design-quality-rubric.md
```

追記内容:

- pro方向性を採用する条件
- 補助ラベルの扱い
- ページ番号の扱い
- 自動メトリクスと手動QAの関係

## 2026-05-07 12:57 JST追記: self-review diagnostic snapshot

Sprint 14の `self_review_diagnostic` 1件を追加調査した。

分かったこと:

- 既存artifactには `self_review_diagnostic` の発生事実は残っていた。
- ただし、slide番号とpre/post self-review HTML snapshotは未保存だった。
- そのため、Sprint 14の既存runだけでは「どのHTML差分でタイトルが消えたか」は復元できない。
- 発生条件は、self-review後HTMLが元HTMLの `h1/h2/.title/.headline` 相当タイトルを保持できず、`decision=keep_original` になったケース。

実装した追加観測:

- `self_review_slide(..., slide_number=...)` を受け取れるようにした。
- 通常生成ループとvalidation再生成ループから `slide_number` を渡すようにした。
- title rewrite検出時だけ、以下を保存する。
  - original HTML
  - improved HTML
  - unified diff patch
- 保存先:

```text
{OUTPUT_DIR}/{job_id}_slides/self_review_diagnostics/
  slide_XXX_{design_mode}_title_rewrite_original.html
  slide_XXX_{design_mode}_title_rewrite_improved.html
  slide_XXX_{design_mode}_title_rewrite_diff.patch
```

安全策:

- 保存前に `redact_secrets()` を通す。
- API responseやtelemetry warningには本文・タイトルを入れない。
- telemetryには従来通りbooleans/decisionだけを残す。
- diagnostic telemetryにも `slide_number` を入れるようにした。

検証:

```text
focused snapshot test: 1 passed, 9 warnings
py_compile: pass
tests/test_generation_telemetry.py + tests/test_sprint14_design_quality.py: 27 passed, 9 warnings
targeted Design QA suite: 59 passed, 9 warnings
git diff --check: pass
```

次回fixed fixture real regenerationで同じdiagnosticが出た場合、差分HTMLまで追跡できる。

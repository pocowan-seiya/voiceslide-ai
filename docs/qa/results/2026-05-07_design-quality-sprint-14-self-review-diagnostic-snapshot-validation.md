# VoiSlide Design Quality Sprint 14 — Self-review diagnostic snapshot validation

Date: 2026-05-07 13:45 JST

## 目的

Sprint 14で追加した `self_review_diagnostic` snapshot保存が、実生成runで機能するか確認した。

確認対象:

- title rewrite検出時に `slide_number` が記録されること
- `{OUTPUT_DIR}/{job_id}_slides/self_review_diagnostics/` に original/improved/diff が保存されること
- 保存物をQA artifactへ退避できること
- title rewriteの条件を差分HTMLから分析できること

## 実行条件

- backend: `http://127.0.0.1:8001`
- frontend: `http://127.0.0.1:3010`
- Chrome/CDP: `http://127.0.0.1:9223`
- fixture: `docs/qa/fixtures/short_voislide_quality_check_32s.mp3`
- script: `/tmp/voislide_sprint14_quality_fix_regeneration_qa_requests.py`
- result: `/tmp/voislide_sprint14_quality_fix_regeneration_qa_result.json`

## 結果

再runは成功した。

```text
ok: true
runs: 2
```

### flash_standard

```text
job_id: 9cfada23-43dc-43de-b8f7-6d938a5bb8a3
stage_counts:
  strategy: 1
  slide_html: 2
  self_review: 2
  self_review_diagnostic: 2
fallback_stage_counts: {}
self_review_diagnostic_count: 2
slide_number: 1, 2
```

保存確認:

```text
outputs/9cfada23-43dc-43de-b8f7-6d938a5bb8a3_slides/self_review_diagnostics/
  slide_001_flash_standard_title_rewrite_original.html
  slide_001_flash_standard_title_rewrite_improved.html
  slide_001_flash_standard_title_rewrite_diff.patch
  slide_002_flash_standard_title_rewrite_original.html
  slide_002_flash_standard_title_rewrite_improved.html
  slide_002_flash_standard_title_rewrite_diff.patch
```

### pro

```text
job_id: c1dfa05c-486c-4196-abcd-f51d8cbbefb3
stage_counts:
  strategy: 1
  slide_html: 2
  self_review: 2
  self_review_diagnostic: 1
fallback_stage_counts: {}
self_review_diagnostic_count: 1
slide_number: 2
```

保存確認:

```text
outputs/c1dfa05c-486c-4196-abcd-f51d8cbbefb3_slides/self_review_diagnostics/
  slide_002_pro_title_rewrite_original.html
  slide_002_pro_title_rewrite_improved.html
  slide_002_pro_title_rewrite_diff.patch
```

## title rewrite条件の分析

`self_review` は品質改善の過程で、元タイトルをより短く・強く・構成的に書き換える傾向がある。

今回のdiffで確認できた例:

### flash_standard slide 1

```diff
+ <h1>音声からスライド動画へ<br>制作フローのすべて</h1>
- <h1>音声からスライド動画を作る<br>流れを確認します</h1>
```

元タイトルの「確認します」が消え、より広告的な「制作フローのすべて」に変わっていた。

### flash_standard slide 2

```diff
- <h1>音声の流れに合わせて、<br/>スライドが自然に繋がること</h1>
+ <h1 class="main">音声の流れに沿って、<br/>スライドが自然に繋がる。</h1>
```

意味は近いが、語尾・助詞・構文が変更されていた。

### pro slide 2

```diff
- <h1>日本語が読みやすく、<br><span class="accent">自然に繋がる</span>こと</h1>
- <div class="subtitle">— 品質向上のための重要要素</div>
+ <h1>読みやすく、<span class="accent">自然に繋がる</span>スライドへ</h1>
+ <div class="subtitle">品質を決める、3つの検証ポイント</div>
```

元タイトルの主語「日本語」が消え、subtitleも書き換わっていた。

## 判断

Sprint 14の title guard は正しく機能している。

理由:

- `self_review` の improved HTML は視覚品質を上げる一方で、元タイトルの意味・語尾・主語を書き換える場合がある
- ユーザー指定タイトルは保持すべきなので、`original_title_present=true improved_title_present=false decision=keep_original` は妥当
- 今回、slide番号と差分HTMLが保存され、次回以降の原因追跡が可能になった

## Design QA補足

今回の再runでは、snapshot保存の確認は成功したが、Design QAは一部で warn/fail が残った。

### metrics

```text
flash_standard slide 1: warn
  title_font_size_px: 64.0
  warning: タイトルフォントサイズが64.0pxです。目標は72.0px以上です。

flash_standard slide 2: fail
  title_font_size_px: 48.0
  warning: タイトルフォントサイズが48.0pxです。最低56.0px必要です。

pro slide 1: fail
  min_font_size_px: 14.0
  small_text_count: 1
  warning: 1個のフォントサイズが20px以下です（最小: 14.0px）。通常テキストで20px以下は禁止です。

pro slide 2: pass
```

### 人間目線QA

contact sheet確認では、以下の判断。

```text
flash_standard slide 1: Pass
flash_standard slide 2: Warn
pro slide 1: Pass〜軽微Warn
pro slide 2: Warn
```

- title guardで元タイトルを維持したこと自体は4枚とも許容
- 問題はタイトル維持ではなく、本文サイズ・カード本文サイズ
- ページ番号、補助ラベル、フッター、装飾ラベルは小さくても許容
- カード内の日本語説明文は通常テキストなので、読みづらい場合はwarn/failが妥当

## 成果物

```text
docs/qa/results/2026-05-07_design-quality-sprint-14-self-review-diagnostic-snapshot-validation.md
docs/qa/results/2026-05-07_design-quality-sprint-14-self-review-diagnostic-snapshot-validation/
  sanitized_api_result.json
  summary.json
  artifact_hashes.json
  comparison_contact_sheet.jpg
  flash_standard_slide_001.png
  flash_standard_slide_002.png
  pro_slide_001.png
  pro_slide_002.png
  flash_standard_9cfada23-43dc-43de-b8f7-6d938a5bb8a3_self_review_diagnostics/
  pro_c1dfa05c-486c-4196-abcd-f51d8cbbefb3_self_review_diagnostics/
```

## 次の実務ポイント

1. title guardは維持する
2. `self_review` promptに「タイトル文字列・意味・主語・語尾を書き換えない」を追加する
3. metrics側でページ番号・補助ラベル・フッター装飾と通常本文を分離する
4. 通常本文、特にカード内日本語説明文の最小サイズをさらに上げる
5. `flash_standard` の title size hardening を追加する

## 検証

```text
fixed fixture rerun: ok
self_review_diagnostic snapshot保存: pass
slide_number記録: pass
diagnostic files copied to QA artifact: pass
```

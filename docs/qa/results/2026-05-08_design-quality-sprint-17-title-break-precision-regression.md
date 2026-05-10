# VoiSlide Design Quality Sprint 17 — title break precision regression

Date: 2026-05-08 11:33 JST

## Scope

Sprint 16の日本語タイトル `<br>` 補正を次段階に進めた。

目的:

- `スライ / ド`、`作 / る` のような語中分断は引き続き除去する
- `作る / 流れ` のような意図的なタイトル改行は残す
- `h1` / `h2` だけでなく、`.headline` / `.title` 系の非見出し要素でも補正を効かせる

## Changes

### Backend

`backend/services/ai_slide_generator.py`

- `_repair_bad_japanese_title_breaks(html)` を精密化
- 全日本語文字間の `<br>` を一律削除する方式をやめた
- 削除対象を以下に限定
  - カタカナ語分断: `スライ<br/>ド`, `デザイ<br/>ン`
  - 1文字ひらがな継続: `作<br/>る`, `見<br/>る`
- 意図的なフレーズ改行は保持
  - `スライド動画を作る<br/>流れ`
- 対象要素を `h1` / `h2` に加えて、`div/span/p` の `.title` / `.headline` / `.main-title` に拡張

### Tests

`backend/tests/test_sprint15_design_quality.py`

追加:

- `test_harden_generated_html_typography_preserves_intentional_japanese_title_line_breaks`
- `test_harden_generated_html_typography_repairs_title_breaks_in_headline_divs`

既存:

- `test_harden_generated_html_typography_repairs_bad_japanese_title_breaks`

## TDD result

```text
RED:
./venv/bin/python -m pytest tests/test_sprint15_design_quality.py::test_harden_generated_html_typography_preserves_intentional_japanese_title_line_breaks tests/test_sprint15_design_quality.py::test_harden_generated_html_typography_repairs_title_breaks_in_headline_divs -q
=> 2 failed, 9 warnings

GREEN focused:
./venv/bin/python -m pytest tests/test_sprint15_design_quality.py::test_harden_generated_html_typography_repairs_bad_japanese_title_breaks tests/test_sprint15_design_quality.py::test_harden_generated_html_typography_preserves_intentional_japanese_title_line_breaks tests/test_sprint15_design_quality.py::test_harden_generated_html_typography_repairs_title_breaks_in_headline_divs -q
=> 3 passed, 9 warnings
```

## Verification

```text
./venv/bin/python -m py_compile services/ai_slide_generator.py services/design_quality_metrics.py && \
./venv/bin/python -m pytest tests/test_design_mode.py tests/test_design_quality_metrics.py tests/test_generation_telemetry.py tests/test_sprint14_design_quality.py tests/test_sprint15_design_quality.py -q && \
git diff --check

=> 68 passed, 9 warnings
=> git diff --check pass
```

## Notes

- 今回も provider real generation は未実行。
- 理由: Sprint 17はSprint 16補正の回帰テスト精度を上げる範囲。
- 次の実生成QAでは、意図的なタイトル改行が消えず、語中分断だけが消えることをcontact sheetで確認する。

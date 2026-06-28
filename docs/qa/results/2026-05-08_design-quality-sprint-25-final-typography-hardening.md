# VoiSlide Design Quality Sprint 25 — Final Typography Hardening

日時: 2026-05-08 19:17:48 JST

## 結論

Sprint 25として、self-review後・browser render直前の最終typography hardeningを追加した。

Sprint 23で発見した `flash_standard` slide 1 のタイトル見た目クリッピングは、最終補正後に解消した。

対象タイトル:

```text
音声からスライド動画を作る流れ
```

## 背景

Sprint 24では、DOM上は正しいタイトルでも、ブラウザ描画上で `scrollWidth > clientWidth` または `scrollHeight > clientHeight` になるケースを検出できるようにした。

Sprint 25では、検出だけでなく、生成物側の最終HTMLに補正を入れる。

## 実装内容

対象ファイル:

- `backend/services/ai_slide_generator.py`
- `backend/tests/test_sprint15_design_quality.py`

### 追加した関数

- `finalize_generated_html_for_render(...)`
- `_relax_title_layout_for_render(css)`
- `_cap_title_font_sizes_for_render(html, max_px)`

### 生成フロー変更

render直前の処理を以下に変更した。

Before:

```python
html = ensure_text_visible(html, slide, slide_number, total_slides, strategy)
```

After:

```python
html = finalize_generated_html_for_render(html, slide, slide_number, total_slides, strategy)
```

### 最終補正の内容

`finalize_generated_html_for_render(...)` は以下を行う。

1. `ensure_text_visible(...)`
2. `harden_generated_html_typography(...)`
3. browser title clipping metricで確認
4. clippingがあればtitle layoutを緩和
   - `max-width: 100%`
   - `line-height` を最低 `1.3` へ
5. それでもclippingがあればtitle font-sizeを段階的にcap
   - `72px`
   - `64px`
   - `56px`

### 既存hardeningの安全化

`_prevent_title_clipping_in_css(...)` は、`word-break: keep-all` があるだけではfont-sizeをcapしないようにした。

cap対象は危険なclipping系CSSがある場合に限定した。

- `white-space: nowrap`
- `text-overflow: clip/ellipsis`
- `overflow: hidden`
- `overflow-wrap: anywhere`

これにより、`pro`の意図された大きめタイトルを必要以上に小さくしにくくした。

## 追加テスト

`backend/tests/test_sprint15_design_quality.py`

追加:

```python
test_finalize_generated_html_for_render_rehardens_self_review_oversized_title
```

確認内容:

- self-review後に戻り得るoversized titleを再現
- `font-size: 128px`
- `max-width: 92%`
- `word-break: keep-all`
- final補正後にbrowser metricで `text_clipping_detected == False`
- `max-width: 100%` が入る
- タイトル欠けwarningが消える

## RED / GREEN

- RED: `ImportError` / 未実装 `finalize_generated_html_for_render`
- GREEN: focused test `1 passed, 9 warnings`

## Sprint 23 artifact再適用

保存先:

- `docs/qa/results/2026-05-08_sprint23_real-generation-metrics-qa/sprint25_fixed_condition_title_measurements.json`

固定条件で再測定した結果:

| mode | slide | title_clipping | title_font_size | gate | warning |
|---|---:|---:|---:|---|---|
| flash_standard | 1 | false | 72px | pass | なし |
| flash_standard | 2 | false | 72px | warn | main occupancy |
| pro | 1 | false | 72px | warn | main occupancy |
| pro | 2 | false | 72px | pass | なし |

### 重要な確認

前回不安定に見えた `pro` 側のtitle clippingは、固定条件で再測定すると解消していた。

直接測定でも以下が一致した。

- metric `text_clipping_detected`: false
- direct detector: false
- Playwright実測 `clip`: false

## Verification

実行コマンド:

```bash
./venv/bin/python -m py_compile services/ai_slide_generator.py services/design_quality_metrics.py
./venv/bin/python -m pytest tests/test_sprint15_design_quality.py -q
./venv/bin/python -m pytest tests/test_generation_telemetry.py tests/test_design_quality_metrics.py tests/test_design_mode.py tests/test_sprint14_design_quality.py tests/test_sprint15_design_quality.py -q
git diff --check
```

結果:

- `py_compile`: pass
- Sprint 15 suite: `11 passed, 9 warnings`
- targeted verification: `85 passed, 9 warnings`
- `git diff --check`: pass

## 残課題

タイトルクリッピングは今回の範囲で解消。

残るwarningは別系統。

- `flash_standard` slide 2: main occupancy warning
- `pro` slide 1: main occupancy warning

次候補は Sprint 26 として、main occupancy warningの実体確認と、装飾/本文/主役要素の候補抽出精度改善を扱う。

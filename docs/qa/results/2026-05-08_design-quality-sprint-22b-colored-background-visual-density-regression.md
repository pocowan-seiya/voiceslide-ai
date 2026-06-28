# VoiSlide Design Quality Sprint 22-B — Colored background visual-density regression

Date: 2026-05-08 17:10 JST
Repo: `/Users/seiyaeto/Antigravity/voiceslide-ai`
Branch: `develop`

## 目的

Sprint 22の `analyze_screenshot_blank_area()` は、白背景/透明背景の空白過多を検出する最小実装だった。

Sprint 22-Bでは、色付き背景で画面全体が埋まっていても、実際の主役要素が小さいケースを検出する。

## 実装内容

`backend/services/design_quality_metrics.py`

- `analyze_screenshot_blank_area(image_path)` の返却値を拡張。
- 既存の near-white metric は維持。
  - `screenshot_blank_area_ratio`
  - `screenshot_content_occupancy_ratio`
- 追加metric:
  - `screenshot_visual_blank_area_ratio`
  - `screenshot_visual_content_occupancy_ratio`
- 画像4隅の平均色を背景色として推定。
- 各ピクセルと背景色のRGB差分を見て、背景と十分違う領域をvisual contentとして数える。
- `screenshot_visual_content_occupancy_ratio < 0.10` なら `warn`。

注意:

- `0.10` は foreground density 用の最小しきい値。
- HTML/CSSの main element occupancy の `0.30` とは別物。
- 色付き背景では、文字・カード・図形などの前景だけを測るため、0.30だと実artifactで過検出しやすい。
- 今回は corner-based background差分の最小deterministic実装。複雑なグラデーションや写真背景は今後の課題。

## 追加テスト

`backend/tests/test_design_quality_metrics.py`

- `TestAnalyzeScreenshotBlankArea::test_detects_underused_content_on_colored_background`
  - 1280x720の青背景に小さい白カードだけを描画。
  - 既存near-white metricでは背景がcontent扱いになる。
  - 新visual metricではカードだけをcontent扱いにして `warn`。

- `TestAnalyzeScreenshotBlankArea::test_dense_content_on_colored_background_passes`
  - 1280x720の青背景に大きい白カードを描画。
  - visual content ratio が十分大きく `pass`。

## RED

Command:

```bash
cd /Users/seiyaeto/Antigravity/voiceslide-ai/backend
./venv/bin/python -m pytest tests/test_design_quality_metrics.py::TestAnalyzeScreenshotBlankArea::test_detects_underused_content_on_colored_background tests/test_design_quality_metrics.py::TestAnalyzeScreenshotBlankArea::test_dense_content_on_colored_background_passes -q
```

Result:

- `2 failed, 9 warnings`
- 失敗理由:
  - `KeyError: 'screenshot_visual_content_occupancy_ratio'`

## GREEN

Command:

```bash
cd /Users/seiyaeto/Antigravity/voiceslide-ai/backend
./venv/bin/python -m pytest tests/test_design_quality_metrics.py::TestAnalyzeScreenshotBlankArea -q
```

Result:

- `4 passed, 9 warnings`

## Sprint 19 artifact再適用

対象:

- `docs/qa/results/2026-05-08_sprint19_post-hardening-regeneration-qa/flash_standard_slide_001.png`
- `docs/qa/results/2026-05-08_sprint19_post-hardening-regeneration-qa/flash_standard_slide_002.png`
- `docs/qa/results/2026-05-08_sprint19_post-hardening-regeneration-qa/pro_slide_001.png`
- `docs/qa/results/2026-05-08_sprint19_post-hardening-regeneration-qa/pro_slide_002.png`

Result:

| file | blank | content | visual_blank | visual_content | gate |
|---|---:|---:|---:|---:|---|
| flash_standard_slide_001.png | 0.014281 | 0.985719 | 0.898840 | 0.101160 | pass |
| flash_standard_slide_002.png | 0.000000 | 1.000000 | 0.741293 | 0.258707 | pass |
| pro_slide_001.png | 0.000424 | 0.999576 | 0.801740 | 0.198260 | pass |
| pro_slide_002.png | 0.003060 | 0.996940 | 0.815623 | 0.184377 | pass |

解釈:

- Sprint 19 artifactは4枚ともpass。
- Sprint 22の白背景metricではほぼ全体がcontent扱いだった。
- Sprint 22-Bのvisual metricでは前景密度が見えるようになった。
- ただし、既存の合格artifactを過剰にwarn化しないよう、foreground densityしきい値は `0.10` に分離した。

## Verification

Focused:

```bash
cd /Users/seiyaeto/Antigravity/voiceslide-ai/backend
./venv/bin/python -m py_compile services/design_quality_metrics.py services/ai_slide_generator.py
./venv/bin/python -m pytest tests/test_design_quality_metrics.py -q
```

Result:

- `38 passed, 9 warnings`

Targeted:

```bash
cd /Users/seiyaeto/Antigravity/voiceslide-ai/backend
./venv/bin/python -m pytest tests/test_generation_telemetry.py tests/test_design_quality_metrics.py tests/test_design_mode.py tests/test_sprint14_design_quality.py tests/test_sprint15_design_quality.py -q
cd ..
git diff --check
```

Result:

- `83 passed, 9 warnings`
- `git diff --check`: pass

## 判定

Sprint 22-Bは完了。

今回で、色付き背景で画面が埋まっていても、主役要素が小さいケースをsynthetic fixtureで検出できるようになった。

次候補:

- Sprint 23: 実生成QAで `flash_standard` / `pro` を再生成し、HTML/CSS metric、browser layout metric、screenshot visual-density metricをまとめて比較する。
- Sprint 22-C: 複雑なグラデーション/写真背景向けに、edge density または local contrast occupancy を追加する。

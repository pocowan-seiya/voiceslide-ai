# VoiSlide Design Quality Sprint 22 — Screenshot blank-area regression

Date: 2026-05-08 16:27 JST
Repo: `/Users/seiyaeto/Antigravity/voiceslide-ai`
Branch: `develop`

## 目的

Sprint 20〜21-Bで追加したHTML/CSS・browser computed layoutの占有率QAに加えて、レンダリング済みスクリーンショットから白背景の空白過多を検出できる最小metricを追加する。

今回の対象は第1段階として、白背景に小さい主役要素だけがあるケースを deterministic regression test 化する。

## 実装内容

`backend/services/design_quality_metrics.py`

- `analyze_screenshot_blank_area(image_path)` を追加。
- Pillowで画像をRGBAとして読み込む。
- 透明またはRGBがすべて245以上のピクセルをblankとして扱う。
- それ以外をvisible contentとして数える。
- 返却値:
  - `screenshot_blank_area_ratio`
  - `screenshot_content_occupancy_ratio`
  - `quality_gate`
  - `warnings`
- content occupancyが `0.30` 未満なら `warn`。

注意:
- このSprint 22は白/ほぼ白の空白検出に絞った最小実装。
- 色付き背景の「見た目上の余白」は、次の段階で背景平均との差分・エッジ密度・主役領域抽出を追加する必要がある。
- HTML/CSS-onlyの `analyze_design_quality()` と browser computed layoutの `analyze_design_quality_with_browser_layout()` は変更していない。

## 追加テスト

`backend/tests/test_design_quality_metrics.py`

- `TestAnalyzeScreenshotBlankArea::test_detects_sparse_screenshot_blank_area`
  - 1280x720白背景に小さい矩形だけを描画。
  - `screenshot_blank_area_ratio >= 0.90`
  - `screenshot_content_occupancy_ratio <= 0.10`
  - `quality_gate == "warn"`

- `TestAnalyzeScreenshotBlankArea::test_dense_screenshot_blank_area_passes`
  - 1280x720白背景に大きい矩形を描画。
  - `screenshot_blank_area_ratio <= 0.40`
  - `screenshot_content_occupancy_ratio >= 0.60`
  - `quality_gate == "pass"`

## RED

Command:

```bash
cd /Users/seiyaeto/Antigravity/voiceslide-ai/backend
./venv/bin/python -m pytest tests/test_design_quality_metrics.py::TestAnalyzeScreenshotBlankArea -q
```

Result:

- exit code: `4`
- `ImportError: cannot import name 'analyze_screenshot_blank_area'`

## GREEN

Command:

```bash
cd /Users/seiyaeto/Antigravity/voiceslide-ai/backend
./venv/bin/python -m pytest tests/test_design_quality_metrics.py::TestAnalyzeScreenshotBlankArea -q
```

Result:

- `2 passed, 9 warnings`

## Sprint 19 artifact再適用

対象:

- `docs/qa/results/2026-05-08_sprint19_post-hardening-regeneration-qa/flash_standard_slide_001.png`
- `docs/qa/results/2026-05-08_sprint19_post-hardening-regeneration-qa/flash_standard_slide_002.png`
- `docs/qa/results/2026-05-08_sprint19_post-hardening-regeneration-qa/pro_slide_001.png`
- `docs/qa/results/2026-05-08_sprint19_post-hardening-regeneration-qa/pro_slide_002.png`

Result:

| file | screenshot_blank_area_ratio | screenshot_content_occupancy_ratio | gate |
|---|---:|---:|---|
| flash_standard_slide_001.png | 0.014281 | 0.985719 | pass |
| flash_standard_slide_002.png | 0.000000 | 1.000000 | pass |
| pro_slide_001.png | 0.000424 | 0.999576 | pass |
| pro_slide_002.png | 0.003060 | 0.996940 | pass |

解釈:

- Sprint 19 artifactは色付き/グラデーション背景が多く、今回の「白背景空白」metricではpass。
- これは仕様通り。色付き背景の中に実質的な余白があるケースは、次Sprintで別metric化する。

## Verification

Focused:

```bash
cd /Users/seiyaeto/Antigravity/voiceslide-ai/backend
./venv/bin/python -m py_compile services/design_quality_metrics.py services/ai_slide_generator.py
./venv/bin/python -m pytest tests/test_design_quality_metrics.py -q
```

Result:

- `36 passed, 9 warnings`

Targeted:

```bash
cd /Users/seiyaeto/Antigravity/voiceslide-ai/backend
./venv/bin/python -m pytest tests/test_generation_telemetry.py tests/test_design_quality_metrics.py tests/test_design_mode.py tests/test_sprint14_design_quality.py tests/test_sprint15_design_quality.py -q
cd ..
git diff --check
```

Result:

- `81 passed, 9 warnings`
- `git diff --check`: pass

## 判定

Sprint 22は完了。

今回で、白背景に主役要素が小さく置かれた「明らかな空白過多」はスクリーンショットから検出できるようになった。

次候補:

- Sprint 22-B: 色付き背景・グラデーション背景でも、背景だけの面積と主役要素密度を分けて見るmetricを追加する。
- 候補metric:
  - edge density
  - local contrast occupancy
  - background color平均との差分
  - central content bounding box

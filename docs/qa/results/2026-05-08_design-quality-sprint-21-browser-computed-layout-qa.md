# VoiSlide Design Quality Sprint 21 — Browser Computed Layout QA

Date: 2026-05-08 15:47 JST
Branch: develop

## 目的

Sprint 20-DまでのHTML/CSS-only metricでは、`height` 未指定の主役要素を安全に推定できないケースが残っていた。

Sprint 21では、Chromiumで実際に描画した `getBoundingClientRect()` を使い、auto-heightの主役コンテンツブロックの `main_element_occupancy_ratio` を補完する最小ヘルパーを追加した。

## 実装内容

対象ファイル:

- `backend/services/design_quality_metrics.py`
- `backend/tests/test_design_quality_metrics.py`

追加:

- `_estimate_main_element_occupancy_ratio_with_browser(html)`
- `analyze_design_quality_with_browser_layout(html, fallback_used=False)`
- browser computed layout用の回帰テスト
- full-slide wrapper除外
  - `slide`
  - `canvas`
  - `wrapper`

方針:

- 既存の `analyze_design_quality()` は deterministic HTML/CSS-only のまま維持。
- browser computed layoutは別ヘルパーとして追加。
- 静的metricで `main_element_occupancy_ratio` が取れる場合はそれを優先。
- 静的metricが `None` の場合だけChromium描画で補完。
- `body` / `html` / full-slide wrapper / 装飾要素で occupancy を偽装しない。

## 追加テスト

`TestAnalyzeDesignQuality::test_browser_layout_estimates_auto_height_main_content`

確認内容:

- `.slide` は1280x720のfull-slide wrapperとして除外される。
- `.main-content { width: 960px; padding: ... }` のように `height` 未指定でも、Chromium描画後の実寸から占有率を取得できる。
- `main_element_occupancy_ratio >= 0.30` の場合は `quality_gate == "pass"`。

## RED / GREEN

### RED

```bash
cd /Users/seiyaeto/Antigravity/voiceslide-ai/backend
./venv/bin/python -m pytest tests/test_design_quality_metrics.py::TestAnalyzeDesignQuality::test_browser_layout_estimates_auto_height_main_content -q
```

結果:

- `ImportError: cannot import name 'analyze_design_quality_with_browser_layout'`
- exit code: 4

### GREEN

同じテストを再実行。

結果:

- `1 passed, 9 warnings`

## Sprint 19 artifact再適用

対象:

- `flash_standard`: `143c1d64-fd41-448d-b73d-53cc8d92d769`
- `pro`: `18f84d23-cc29-4317-8d44-185a74c57b26`

結果:

| mode | slide | static occupancy | browser occupancy | gate |
|---|---:|---:|---:|---|
| flash_standard | 1 | `None` | `0.834011` | pass |
| flash_standard | 2 | `None` | `None` | pass |
| pro | 1 | `None` | `0.834345` | pass |
| pro | 2 | `1.0` | `1.0` | pass |

判定:

- Sprint 20-D時点で残っていた `None` のうち、2件をbrowser computed layoutで補完できた。
- `flash_standard` slide 2は引き続き `None`。候補markerに安全に一致しないため、推測せず維持。
- 既存のpass判定は維持。

## 検証

### Focused

```bash
cd /Users/seiyaeto/Antigravity/voiceslide-ai/backend
./venv/bin/python -m py_compile services/design_quality_metrics.py services/ai_slide_generator.py
./venv/bin/python -m pytest tests/test_design_quality_metrics.py -q
```

結果:

- `33 passed, 9 warnings`

### Targeted verification

```bash
cd /Users/seiyaeto/Antigravity/voiceslide-ai/backend
./venv/bin/python -m pytest tests/test_generation_telemetry.py tests/test_design_quality_metrics.py tests/test_design_mode.py tests/test_sprint14_design_quality.py tests/test_sprint15_design_quality.py -q
cd ..
git diff --check
```

結果:

- `78 passed, 9 warnings`
- `git diff --check`: pass

## 注意

`git status --short --branch -- backend/services/design_quality_metrics.py backend/tests/test_design_quality_metrics.py docs/qa/results` は以下の通り。

```text
## develop...origin/develop
?? backend/services/design_quality_metrics.py
?? backend/tests/test_design_quality_metrics.py
?? docs/qa/results/
```

この作業では既存のuntracked状態を維持し、不要なgit操作はしていない。

## 次候補

Sprint 21-B:

- browser computed layoutの候補markerを、実artifact由来で安全に拡張する。
- 例: `section`, `container`, `grid` などは誤検出リスクが高いため、まず実HTMLを抽出してからREDテスト化する。
- screenshot-based blank-area ratioはその次段階が自然。

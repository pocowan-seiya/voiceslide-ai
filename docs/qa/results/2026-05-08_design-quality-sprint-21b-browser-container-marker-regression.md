# VoiSlide Design Quality Sprint 21-B — Browser Container Marker Regression

Date: 2026-05-08 16:17 JST
Branch: develop

## 目的

Sprint 21で `browser computed layout` を追加したが、Sprint 19 artifact の `flash_standard` slide 2 は `main_element_occupancy_ratio` がまだ `None` だった。

原因を実HTMLから見ると、主役要素が `.container` で、既存のbrowser候補markerに含まれていなかった。

Sprint 21-Bでは、実artifact由来の `.container` を安全に候補へ追加し、auto-heightの主役コンテナを補完できるようにした。

## 実artifact確認

対象:

- `flash_standard`: `143c1d64-fd41-448d-b73d-53cc8d92d769`
- `pro`: `18f84d23-cc29-4317-8d44-185a74c57b26`

確認した未補完ケース:

- `flash_standard` slide 2
- HTML内の主要要素:
  - `.container`
  - `.eyebrow`
  - `h1`
- CSS:
  - `.container { position: relative; z-index: 2; text-align: center; max-width: 1700px; width: 100%; }`

判定:

- `container` は汎用名なので静的HTML/CSS-only推定には入れない。
- ただしbrowser computed layoutでは、実寸・textContent・装飾除外・wrapper除外を通せるため、安全に候補化できる。

## 実装内容

対象ファイル:

- `backend/services/design_quality_metrics.py`
- `backend/tests/test_design_quality_metrics.py`

変更:

- browser computed layout の `candidate_markers` に `container` を追加。
- 実artifact由来の `.container` パターンを回帰テスト化。

既存方針は維持:

- `analyze_design_quality()` は deterministic HTML/CSS-only のまま。
- `analyze_design_quality_with_browser_layout()` だけがChromium描画を使う。
- 装飾・背景・full-slide wrapperはoccupancy対象外。

## 追加テスト

`TestAnalyzeDesignQuality::test_browser_layout_estimates_real_artifact_container_class`

確認内容:

- `.container { max-width: 1120px; width: 100%; }` で `height` 未指定。
- 静的metricでは `main_element_occupancy_ratio is None`。
- browser computed layoutでは `.container` の実寸から `main_element_occupancy_ratio >= 0.30`。
- `quality_gate == "pass"`。

## RED / GREEN

### RED

```bash
cd /Users/seiyaeto/Antigravity/voiceslide-ai/backend
./venv/bin/python -m pytest tests/test_design_quality_metrics.py::TestAnalyzeDesignQuality::test_browser_layout_estimates_real_artifact_container_class -q
```

結果:

- `1 failed, 9 warnings`
- 失敗理由: `assert None is not None`

### GREEN

同じテストを再実行。

結果:

- `1 passed, 9 warnings`

## Sprint 19 artifact再適用

| mode | slide | static occupancy | browser occupancy | gate |
|---|---:|---:|---:|---|
| flash_standard | 1 | `None` | `0.834806` | pass |
| flash_standard | 2 | `None` | `0.892622` | pass |
| pro | 1 | `None` | `0.834345` | pass |
| pro | 2 | `1.0` | `1.0` | pass |

判定:

- Sprint 21時点で残っていた `flash_standard` slide 2 の `None` を補完できた。
- Sprint 19の4枚は、browser computed layout pathではすべて占有率を取得できる状態になった。
- 既存のpass判定は維持。

## 検証

### Focused

```bash
cd /Users/seiyaeto/Antigravity/voiceslide-ai/backend
./venv/bin/python -m py_compile services/design_quality_metrics.py services/ai_slide_generator.py
./venv/bin/python -m pytest tests/test_design_quality_metrics.py -q
```

結果:

- `34 passed, 9 warnings`

### Targeted verification

```bash
cd /Users/seiyaeto/Antigravity/voiceslide-ai/backend
./venv/bin/python -m pytest tests/test_generation_telemetry.py tests/test_design_quality_metrics.py tests/test_design_mode.py tests/test_sprint14_design_quality.py tests/test_sprint15_design_quality.py -q
cd ..
git diff --check
```

結果:

- `79 passed, 9 warnings`
- `git diff --check`: pass

## 注意

`git status --short --branch -- backend/services/design_quality_metrics.py backend/tests/test_design_quality_metrics.py docs/qa/results/2026-05-08_design-quality-sprint-21b-browser-container-marker-regression.md` は以下。

```text
## develop...origin/develop
?? backend/services/design_quality_metrics.py
?? backend/tests/test_design_quality_metrics.py
```

この作業では既存のuntracked状態を維持し、不要なgit操作はしていない。

## 次候補

Sprint 22:

- screenshot-based blank-area ratioを検討する。
- browser computed layoutでは主役要素の矩形占有率は取れるが、背景/余白の実際の見え方までは見ていない。
- まずは固定fixtureの実生成4枚に対して、スクリーンショットから空白・密度・中央寄せ偏りを記録するのが自然。

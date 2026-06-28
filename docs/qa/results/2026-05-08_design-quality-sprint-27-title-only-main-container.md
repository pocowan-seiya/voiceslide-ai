# VoiSlide Design Quality Sprint 27 — Title-only Main Container

日時: 2026-05-08

## 結論

Sprint 27として、`flash_standard` の title-only slide に明示的な主役コンテナを付与するfinal補正を追加した。

Sprint 26後に残っていた `flash_standard` slide 2 の main occupancy warning は解消した。

## 原因

対象artifactでは、`eyebrow` と `h1` が `body` 直下に配置されていた。

ブラウザ上では十分読めるが、browser computed layout metricの候補になる `.content` / `.hero` / `.container` / `.main` などの主役コンテナがなかった。

その結果、静的metricが小さい装飾要素を拾り、`main_element_occupancy_ratio = 0.000868` のwarningが残っていた。

## 実装

対象:

- `backend/services/ai_slide_generator.py`

追加:

- `_ensure_title_only_main_content_container(html)`

挙動:

- `body` 直下に `h1` / `h2` があるtitle-only slideを検出する。
- 既に `.content` / `.hero` / `.container` / `.main` などの主役コンテナがある場合は何もしない。
- `eyebrow` と `h1/h2` を `.voislide-main-content` でwrapする。
- `.voislide-main-content` に以下のlayoutを付与する。
  - `width: min(100%, 1680px)`
  - `min-height: 360px`
  - `display: flex`
  - `flex-direction: column`
  - `align-items: center`
  - `justify-content: center`
  - `text-align: center`

この補正は `finalize_generated_html_for_render(...)` の中で、typography hardening後・browser render前に実行する。

## 併せて安定化した点

対象:

- `backend/services/design_quality_metrics.py`

変更:

- PlaywrightでHTMLを読み込んだ後、`document.fonts.ready` を待つ。

理由:

- font loading前後でtitle clipping判定が揺れるケースがあったため。
- Sprint 25/26系のbrowser metricを安定させるため。

## 追加テスト

対象:

- `backend/tests/test_sprint15_design_quality.py`

追加:

- `test_finalize_generated_html_for_render_wraps_title_only_slide_in_main_content_container`

確認内容:

- title-only slideに `.voislide-main-content` が追加される。
- browser metricで `main_element_occupancy_ratio >= 0.30` になる。
- title clippingなし。
- quality gateが `pass` になる。

## Sprint 23 artifact再適用

保存先:

```text
docs/qa/results/2026-05-08_sprint23_real-generation-metrics-qa/sprint27_fixed_condition_title_only_container_measurements.json
```

結果:

| mode | slide | gate | occupancy | title_clipping | title_font | main container |
|---|---:|---|---:|---:|---:|---:|
| flash_standard | 1 | pass | 0.58913 | false | 72px | false |
| flash_standard | 2 | pass | 0.65625 | false | 72px | true |
| pro | 1 | pass | 0.723775 | false | 72px | false |
| pro | 2 | pass | 1.0 | false | 82px | false |

Sprint 23 artifact由来の4slideは全て `pass` になった。

## Verification

- `py_compile`: pass
- `tests/test_sprint15_design_quality.py tests/test_design_quality_metrics.py`: 52 passed, 9 warnings
- targeted verification: 87 passed, 9 warnings
- `git diff --check`: pass

## 次の候補

Sprint 28では、実生成QAを再実行するのが自然。

目的:

- Sprint 25〜27のfinal補正が実AI生成でも安定するか確認する。
- `flash_standard` / `pro` 両方で、title clipping・main occupancy・visual density・self-review diagnostic混入なしを確認する。

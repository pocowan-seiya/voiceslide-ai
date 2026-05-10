# Sprint 20-C — layout dimension inference regression

Date: 2026-05-08 15:01 JST
Branch: develop

## 目的

Sprint 20-Bでは、canvas occupancy を inline style と `<style>` block の simple class/id rule から推定できるようにした。

ただし実生成HTMLでは、主要レイアウト寸法が `max-width` / `min-height` / viewport unit で表現されることがある。Sprint 20-Cでは、この範囲を deterministic metric に追加する。

## 実装内容

### `backend/services/design_quality_metrics.py`

追加・更新:

- occupancy寸法の対応unitを拡張
  - `vw`
  - `vh`
- width推定のfallbackとして `max-width` を追加
- height推定のfallbackとして `min-height` を追加
- inline style と `<style>` block rule の両方で同じ推定を使用

今回も意図的に conservative な実装にしている。

- `max-width` は width がない場合だけ使う
- `min-height` は height がない場合だけ使う
- `calc()` / grid実レイアウト / browser computed layout はまだ推測しない
- 寸法が確定できない場合は `None` のままにする

## 追加テスト

`backend/tests/test_design_quality_metrics.py`

追加:

- `test_estimates_occupancy_from_max_width_and_min_height_style_rule`
  - `.content-frame { max-width: 960px; min-height: 540px; }`
  - occupancy `0.5625` で `pass`
- `test_estimates_occupancy_from_viewport_units`
  - `.stage { width: 80vw; height: 60vh; }`
  - occupancy `0.48` で `pass`

## TDD結果

### RED

```text
2 failed, 9 warnings
```

失敗理由:

```text
assert None == 0.5625
assert None == 0.48
```

つまり、`max-width` / `min-height` / `vw` / `vh` をまだ読めていないことを確認した。

### GREEN

```text
2 passed, 9 warnings
```

## Sprint 19 artifactへの再適用

Sprint 19の再生成済みartifactに、新metricを再適用した。

```json
{
  "flash_standard": {
    "job_id": "143c1d64-fd41-448d-b73d-53cc8d92d769",
    "slides": [
      {
        "slide_number": 1,
        "quality_gate": "pass",
        "min_font_size_px": 26.0,
        "small_text_count": 0,
        "main_element_occupancy_ratio": null,
        "blank_area_ratio_estimate": null,
        "warnings": []
      },
      {
        "slide_number": 2,
        "quality_gate": "pass",
        "min_font_size_px": 115.2,
        "small_text_count": 0,
        "main_element_occupancy_ratio": null,
        "blank_area_ratio_estimate": null,
        "warnings": []
      }
    ]
  },
  "pro": {
    "job_id": "18f84d23-cc29-4317-8d44-185a74c57b26",
    "slides": [
      {
        "slide_number": 1,
        "quality_gate": "pass",
        "min_font_size_px": 72.0,
        "small_text_count": 0,
        "main_element_occupancy_ratio": null,
        "blank_area_ratio_estimate": null,
        "warnings": []
      },
      {
        "slide_number": 2,
        "quality_gate": "pass",
        "min_font_size_px": 26.0,
        "small_text_count": 0,
        "main_element_occupancy_ratio": 1.0,
        "blank_area_ratio_estimate": 0.0,
        "warnings": []
      }
    ]
  }
}
```

解釈:

- 今回の追加で deterministic metric の対応範囲は広がった。
- ただしSprint 19 artifactでは `None` は減らなかった。
- 理由は、該当artifactの残り `None` が今回追加した `max-width + min-height` / `vw + vh` パターンではないため。
- `None` は失敗扱いではなく、推測を避けるための仕様。

## 検証

### focused

```bash
cd /Users/seiyaeto/Antigravity/voiceslide-ai/backend
./venv/bin/python -m py_compile services/design_quality_metrics.py services/ai_slide_generator.py
./venv/bin/python -m pytest tests/test_design_quality_metrics.py -q
```

結果:

```text
31 passed, 9 warnings
```

### targeted verification

```bash
cd /Users/seiyaeto/Antigravity/voiceslide-ai/backend
./venv/bin/python -m pytest \
  tests/test_generation_telemetry.py \
  tests/test_design_quality_metrics.py \
  tests/test_design_mode.py \
  tests/test_sprint14_design_quality.py \
  tests/test_sprint15_design_quality.py -q
cd ..
git diff --check
```

結果:

```text
76 passed, 9 warnings
git diff --check: pass
```

## 判定

Sprint 20-Cは pass。

`max-width` / `min-height` / `vw` / `vh` を deterministic canvas occupancy metric に追加できた。

## 残すこと

次に進めるなら以下。

1. `calc()` / `grid-template` / `gap` / `padding` を読む。ただし誤推定リスクが上がるため、実artifactの具体例を先に採取する。
2. browser computed layout で、CSSだけでは取れない実寸を読む。
3. screenshot-based blank area ratio を追加する。
4. prompt/fallback template側に「主役要素の占有率」ルールを反映する。

## 注意

今回も backend metric / regression test のみ。プロンプト変更、fallback template変更、production deployは行っていない。

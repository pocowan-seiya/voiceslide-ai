# Sprint 20-B — style block canvas occupancy regression

Date: 2026-05-08 14:46 JST
Branch: develop

## 目的

Sprint 20第一段階では、canvas occupancy を inline style の `width` / `height` だけで推定した。

ただし実生成HTMLでは、主要レイアウト寸法が `<style>` block 側に出ることが多い。そこでSprint 20-Bでは、CSS rule側の `width` / `height` も deterministic metric に含める。

## 実装内容

### `backend/services/design_quality_metrics.py`

追加・更新:

- `<style>` block の CSS rule から `width` / `height` を抽出
- simple class selector と id selector をHTML要素の `class` / `id` に照合
- `%` / `px` / `rem` / `em` を既存の 1280x720 canvas 前提でpx換算
- decorative shapeをoccupancy対象から除外
  - `glow`
  - `background`
  - `bg-` / `-bg`
  - `circle`
  - `wave`
  - `grid`
  - `accent`
  - `underline`
  - `corner`
  - `dot`
  - `line-` / `-line`

この除外は重要。実生成HTMLには大きな背景グローや円形装飾が多く、そこを主役要素として数えると、余白過多を見逃すため。

## 追加テスト

`backend/tests/test_design_quality_metrics.py`

追加:

- `test_detects_underused_canvas_from_style_block_class_rule`
  - `.main-card { width: 320px; height: 180px; }` を検出
  - occupancy `0.0625` で `warn`
- `test_large_main_group_from_style_block_id_rule_passes`
  - `#heroLayout { width: 75%; height: 75%; }` を検出
  - occupancy `0.5625` で `pass`
- `test_ignores_large_decorative_style_block_shapes_for_occupancy`
  - `.glow-bg { width: 1600px; height: 1600px; }` を無視
  - `.main-card { width: 320px; height: 180px; }` を主役として扱う

## TDD結果

### RED

```text
2 failed, 9 warnings
```

失敗理由:

```text
assert None == 0.0625
assert None == 0.5625
```

つまり、CSS rule側の寸法をまだ見ていないことを確認した。

追加で decorative shape の誤検出もRED化した。

```text
1 failed, 9 warnings
assert 1.0 == 0.0625
```

背景グローを主役要素として拾ってしまう問題を確認した。

### GREEN

```text
3 passed, 9 warnings
```

## Sprint 19 artifactへの再適用

Sprint 19の再生成済みartifactに、新metricを再適用した。

```json
{
  "flash_standard": {
    "job_id": "143c1d64-fd41-448d-b73d-53cc8d92d769",
    "slides": [
      {
        "quality_gate": "pass",
        "min_font_size_px": 26.0,
        "small_text_count": 0,
        "main_element_occupancy_ratio": null,
        "blank_area_ratio_estimate": null,
        "warnings": []
      },
      {
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
        "quality_gate": "pass",
        "min_font_size_px": 72.0,
        "small_text_count": 0,
        "main_element_occupancy_ratio": null,
        "blank_area_ratio_estimate": null,
        "warnings": []
      },
      {
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

- CSS rule解析により、実生成artifactでも少なくとも一部はoccupancyを取れるようになった。
- ただし `max-width` だけ、または `height` が明示されないレイアウトではまだ `None` になる。
- これは推測で誤検出しないための仕様。

## 検証

### focused

```bash
cd /Users/seiyaeto/Antigravity/voiceslide-ai/backend
./venv/bin/python -m py_compile services/design_quality_metrics.py services/ai_slide_generator.py
./venv/bin/python -m pytest tests/test_design_quality_metrics.py -q
```

結果:

```text
29 passed, 9 warnings
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
74 passed, 9 warnings
 git diff --check: pass
```

## 判定

Sprint 20-Bは pass。

inline styleだけでなく、`<style>` block の simple class/id rule からも canvas occupancy を推定できるようになった。

## 残すこと

次に進めるなら以下。

1. `max-width` + `padding` + `grid` など、実生成で多い寸法表現を追加で読む。
2. `min-height: 100vh` / `height: 100vh` など viewport系の換算を追加する。
3. screenshot-based blank area ratio を追加して、CSSだけでは取れない余白過多を検出する。
4. prompt/fallback template側に「主役要素の占有率」ルールを反映する。

## 注意

今回も backend metric / regression test のみ。プロンプト変更、fallback template変更、production deployは行っていない。

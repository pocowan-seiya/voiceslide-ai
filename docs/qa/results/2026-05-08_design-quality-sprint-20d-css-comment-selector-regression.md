# Sprint 20-D — CSS comment selector regression

Date: 2026-05-08 15:18 JST
Branch: develop

## 目的

Sprint 20-C後も、Sprint 19 artifactの一部で `main_element_occupancy_ratio` が `null` のままだった。

Sprint 20-Dでは、まず実artifactのCSS寸法パターンを確認した。
その結果、実生成HTMLではCSS ruleのselector前に日本語コメントが付くケースがあることを確認した。

例:

```css
/* メインコンテナ */ .main {
  position: absolute;
  width: 92%;
}
```

この形式では、selector文字列が `/* メインコンテナ */ .main` になり、simple class selectorとして照合できない。
今回は安全な範囲として、CSS selector中のコメントを除去してから照合する回帰テストを追加した。

## 実装内容

### `backend/services/design_quality_metrics.py`

追加・更新:

- `_RE_CSS_COMMENT` を追加
- `_normalize_css_selector(selector)` を追加
- CSS rule selectorを使う前にコメントを除去
- `_is_non_content_selector()` / `_selector_matches_attrs()` / occupancy rule収集で同じ正規化を使用

対象:

```css
/* メインコンテナ */ .main {
  width: 960px;
  height: 540px;
}
```

期待:

- `.main` として `<div class="main">` に照合できる
- occupancy `0.5625`
- quality gate `pass`

## 追加テスト

`backend/tests/test_design_quality_metrics.py`

追加:

- `test_estimates_occupancy_from_style_rule_with_leading_css_comment`

## TDD結果

### RED

```text
1 failed, 9 warnings
```

失敗理由:

```text
assert None == 0.5625
```

CSSコメント付きselectorを照合できていないことを確認した。

### GREEN

```text
1 passed, 9 warnings
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

- CSSコメント付きselectorへの対応は追加できた。
- ただしSprint 19 artifactでは `None` は減らなかった。
- 理由は、残っている `None` が主に以下の安全に推定しづらいパターンだったため。
  - `max-width` はあるがheightがない
  - `width: 92%` はあるがheightがない
  - body/html寸法はcontent occupancy対象外
  - 装飾要素は除外対象
- `None` は失敗ではなく、推測を避けるための仕様。

## 検証

### focused

```bash
cd /Users/seiyaeto/Antigravity/voiceslide-ai/backend
./venv/bin/python -m py_compile services/design_quality_metrics.py services/ai_slide_generator.py
./venv/bin/python -m pytest tests/test_design_quality_metrics.py -q
```

結果:

```text
32 passed, 9 warnings
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
77 passed, 9 warnings
git diff --check: pass
```

## 判定

Sprint 20-Dは pass。

CSSコメントがselector前に付く実生成HTMLパターンを、deterministic occupancy metricで安全に扱えるようにした。

## 残すこと

次に進めるなら以下。

1. height未指定の実artifactは、HTML/CSS-onlyではまだ安全に推定しない。
2. 次はbrowser computed layoutで実寸を読む方がよい。
3. もしくはscreenshot-based blank area ratioを追加する。
4. prompt/fallback template側に「主役要素の占有率」ルールを反映する。

## 注意

今回も backend metric / regression test のみ。プロンプト変更、fallback template変更、production deployは行っていない。

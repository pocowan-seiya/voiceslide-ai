# Sprint 20 — small text / canvas occupancy regression

Date: 2026-05-08 13:52 JST
Branch: develop

## 目的

Sprint 18/19後の次段階として、タイトル分断ではなく以下を deterministic regression test に落とす。

- 小さすぎる本文・カード文字
- 画面中央の小さいカードだけで、キャンバスを使えていないスライド
- 余白が「構成」ではなく、ただ空いているだけになるケース

## 実装内容

### `backend/services/design_quality_metrics.py`

既存の font-size metric に加えて、HTML/CSS-only の簡易 canvas occupancy metric を追加した。

追加フィールド:

- `main_element_occupancy_ratio`
- `blank_area_ratio_estimate`
- `text_clipping_detected`

今回の占有率は 1280x720 landscape canvas を前提に、inline style の `width` / `height` が明示された content element の最大面積から推定する。

- 例: `width: 320px; height: 180px;` → `0.0625`
- 例: `width: 960px; height: 540px;` → `0.5625`

寸法が取れない場合は推測せず `None` にする。画像解析・スクリーンショットベースの blank area 判定は次段階に残す。

### `backend/tests/test_design_quality_metrics.py`

追加テスト:

- `test_detects_underused_canvas_when_main_group_is_too_small`
  - 320x180 の小さい main card を `warn` にする
  - `main_element_occupancy_ratio` と `blank_area_ratio_estimate` を検証
- `test_large_main_group_canvas_occupancy_passes`
  - 960x540 の main group は `pass`
  - 占有率と余白推定を検証

## TDD結果

### RED

```text
2 failed, 9 warnings
```

失敗理由:

```text
KeyError: 'main_element_occupancy_ratio'
```

つまり、まだ canvas occupancy metric が存在しないことを確認した。

### GREEN

```text
2 passed, 9 warnings
```

## 検証

### design metrics focused

```bash
cd /Users/seiyaeto/Antigravity/voiceslide-ai/backend
./venv/bin/python -m py_compile services/design_quality_metrics.py services/ai_slide_generator.py
./venv/bin/python -m pytest tests/test_design_quality_metrics.py -q
```

結果:

```text
26 passed, 9 warnings
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
71 passed, 9 warnings
 git diff --check: pass
```

## 既存Sprint 19 artifactへの再適用

Sprint 19の再生成済みartifactに、新metricを再適用した。

```text
flash_standard 143c1d64-fd41-448d-b73d-53cc8d92d769
1 {'quality_gate': 'pass', 'min_font_size_px': 26.0, 'small_text_count': 0, 'main_element_occupancy_ratio': None, 'blank_area_ratio_estimate': None}
2 {'quality_gate': 'pass', 'min_font_size_px': 115.2, 'small_text_count': 0, 'main_element_occupancy_ratio': None, 'blank_area_ratio_estimate': None}
pro 18f84d23-cc29-4317-8d44-185a74c57b26
1 {'quality_gate': 'pass', 'min_font_size_px': 72.0, 'small_text_count': 0, 'main_element_occupancy_ratio': None, 'blank_area_ratio_estimate': None}
2 {'quality_gate': 'pass', 'min_font_size_px': 26.0, 'small_text_count': 0, 'main_element_occupancy_ratio': None, 'blank_area_ratio_estimate': None}
```

現行実生成HTMLでは、主役要素の width/height がinline styleとして明示されていないため、占有率は `None` になった。これは誤検出を避けるための仕様。

## 判定

Sprint 20の第一段階は pass。

small text は既存 metric で検出済み。今回、画面占有率が低い main group も deterministic に `warn` できるようにした。

ただし実生成HTMLへの適用では、inline dimension が少ないため `main_element_occupancy_ratio` はまだ出ない。次は `<style>` block の layout rule 解析、または screenshot-based occupancy に進むのが必要。

## 残すこと

次にやるなら以下。

1. 実生成 `flash_standard` / `pro` で `main_element_occupancy_ratio` が実際に出るか確認する。
2. inline style だけでなく `<style>` block の width/height にも対応する。
3. screenshot / image-based blank area ratio を別スプリントで追加する。
4. fallback template のカード・主役要素にも占有率が出るようにする。

## 注意

今回の変更は backend metric / regression test のみ。実AI生成、プロンプト変更、fallback template変更はまだ行っていない。

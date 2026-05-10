# VoiSlide Movie デザイン品質改善 Spec

> **For Hermes:** 実装する場合は `subagent-driven-development` skill を使い、Sprint単位で Claude Code / Generator に渡す。

**Goal:** VoiSlide Movie のスライドを「文字が大きく読みやすい」「画面全体を使う」「モデルの良さが出る」品質へ上げる。

**Architecture:** 既存の HTML/CSS 生成パイプラインを維持し、Design Director → Layout Plan → HTML生成 → 自動検査 → 必要時のみデザイン修正再生成、の流れに整理する。全面画像化はせず、GPT Image 2 等は背景・キービジュアル・区切りスライドから検証する。

**Tech Stack:** Next.js / React / FastAPI / Python / OpenRouter / Gemini / Playwright screenshot rendering / existing `docs/qa` rubric.

---

## 1. 背景

2026-05-02 の固定音声 fixture QA で、`flash_standard` と `pro` を比較した。

- fixture: `docs/qa/fixtures/short_voislide_quality_check_32s.mp3`
- result: `docs/qa/results/2026-05-02_flash_standard-vs-pro_short_voislide_quality_check.md`
- 暫定スコア:
  - `flash_standard`: 35/50
  - `pro`: 39/50
- 1枚目は `pro` が優位。
- 2枚目は `flash_standard` と `pro` が同一画像。
- 2枚目の課題: 文字が小さく、カード内の情報が弱い。画面を使い切れていない。

誠哉さんの要望:

- 余白を単に空けるのではなく、スライド全体を自由に使ってほしい。
- 文字をもっと大きくしたい。
- モデルの性能を活かしたい。
- VoiSlide Movie としてのデザイン品質を高くしたい。
- API設定で複数モデルを選べるため、モデル比較も品質改善の中に入れたい。

---

## 2. 現状コードから見えた問題

対象ファイル:

- `backend/services/ai_slide_generator.py`
- `backend/services/ai_utils.py`
- `backend/services/openrouter_utils.py`
- `docs/qa/voiceslide-design-quality-rubric.md`
- `docs/qa/results/2026-05-02_flash_standard-vs-pro_short_voislide_quality_check.md`

### 2.1 `pro` は消費上限が増える

`backend/services/ai_slide_generator.py` の現状:

- strategy生成:
  - `flash_standard`: `max_output_tokens=8192`
  - `pro`: `max_output_tokens=12288`
- 各スライドHTML生成:
  - `flash_standard`: `max_output_tokens=8192`
  - `pro`: `max_output_tokens=12288`
- self-review:
  - 両方 `max_output_tokens=8192`

2枚スライドの場合、上限ベースでは以下。

- `flash_standard`: 40960 output tokens
- `pro`: 53248 output tokens
- 差分: +12288 output tokens
- 上限比: 約1.3倍

ただし実課金は、実際の input/output tokens、選択モデル単価、再生成回数、self-review回数、fallback/retry回数で決まる。

### 2.2 strategy JSON 失敗が品質を落とす

2026-05-02 の実生成ログで以下が出ている。

```text
[Design Architect] Strategy generation failed: Expecting value: line 1 column 1 (char 0)
```

この場合、`get_fallback_strategy()` に落ちる。
そのため `pro` でも、Design Director の設計が効かない場合がある。

### 2.3 `Minimal` layout が文字小さめ・空白多めに寄る

ログ上、2枚目は以下。

```text
[Design Architect] Slide 2: Using layout 'Minimal'
```

Minimal系は、安全だが画面占有が低くなりやすい。
誠哉さんの要望とは逆に、文字が小さく、空白が目立つ結果になりやすい。

### 2.4 TextSafety fallback が安全寄りすぎる

ログ上、以下が出ている。

```text
[TextSafety] Slide 2: title '日本語が読みやすく、スライドが自然に繋がること' not found (even with fuzzy match), using fallback HTML
```

fallback は破綻を防ぐ目的として必要。  
ただし fallback の見た目が弱いと、AIモデルの良さより安全テンプレートの見た目が最終出力になる。

### 2.5 今のrubricは「余白過多」を検出しにくい

`docs/qa/voiceslide-design-quality-rubric.md` の Whitespace は、主に「詰め込みすぎ」を評価している。  
今回の課題は逆で、「空いているだけ」「文字が小さい」「画面を使い切れていない」。

そのため以下の評価項目を追加する必要がある。

- minimum font size
- main element canvas occupancy
- blank area ratio
- card text size
- text clipping
- fallback occurrence
- actual model name
- actual token usage / estimated cost

---

## 3. 品質方針

### 3.1 VoiSlide のデザイン原則

1. 1スライド1メッセージを守る。
2. タイトルは大きく、主役として配置する。
3. 画面全体を使う。
4. 空いている領域は、背景、図形、光、カード、線、グラデーションで構成する。
5. 文字を小さくして解決しない。
6. 日本語テキストは HTML/CSS として読みやすく描画する。
7. 動画として連続して見た時に、配色・フォント・装飾ルールが揃う。
8. PiP / facecam の安全エリアを守る。
9. fallback でも最低限の見た目を保証する。
10. 生成時間とAPIコストをログで見えるようにする。

### 3.2 禁止したい生成傾向

- 20px以下の本文・カード文字。
- 画面中央に小さいカードだけを置く。
- 何もない空白が大きすぎる。
- 補足テキストが多く、主役が不明。
- タイトルが長く小さくなる。
- `Minimal` を理由に情報密度が下がる。
- fallback時に単調なテンプレートへ落ちる。
- モデルが選ばれているのに、実際は fallback model で生成されることがUIに出ない。

---

## 4. 実装スプリント

### Sprint 1: Cost / model / fallback telemetry を追加

**Objective:** どのモデルで、何回AIを呼び、fallbackが起きたかをQAログに残せるようにする。

**Files:**

- Modify: `backend/services/openrouter_utils.py`
- Modify: `backend/services/ai_utils.py`
- Modify: `backend/services/ai_slide_generator.py`
- Modify: `backend/main.py`
- Create: `backend/tests/test_generation_telemetry.py`
- Modify: `docs/qa/results/template-design-quality-comparison.md`

**Required fields:**

```json
{
  "job_id": "...",
  "design_mode": "flash_standard|pro",
  "stage": "strategy|slide_html|self_review|fallback|video",
  "slide_number": 1,
  "requested_model": "anthropic/claude-opus-4-7",
  "actual_model": "anthropic/claude-opus-4-7",
  "provider": "openrouter|gemini|openai",
  "input_tokens": 0,
  "output_tokens": 0,
  "estimated_cost_usd": null,
  "duration_ms": 0,
  "fallback_reason": null,
  "warning": null
}
```

**Implementation notes:**

- OpenRouter response usage fieldsが取れる場合は使う。
- 取れない場合は `input_tokens`, `output_tokens`, `estimated_cost_usd` を `null` にしてよい。
- `requested_model` と `actual_model` は必ず残す。
- `Strategy generation failed`、`TextSafety fallback`、OpenRouter model fallback は必ず記録する。
- APIキー値は絶対に記録しない。

**Tests:**

```bash
cd /Users/seiyaeto/Antigravity/voiceslide-ai/backend
./venv/bin/python -m pytest tests/test_generation_telemetry.py -q
```

Expected:

- telemetry object can be created without secrets.
- fallback event is recorded.
- token/cost fields can be null.
- API key-like strings are redacted.

---

### Sprint 2: Design QA metric を追加

**Objective:** 小さい文字・画面未使用・余白過多を検出する。

**Files:**

- Create: `backend/services/design_quality_metrics.py`
- Create: `backend/tests/test_design_quality_metrics.py`
- Modify: `backend/services/ai_slide_generator.py`
- Modify: `docs/qa/voiceslide-design-quality-rubric.md`

**Metrics:**

```json
{
  "min_font_size_px": 24,
  "title_font_size_px": 82,
  "body_font_size_px_min": 32,
  "main_element_occupancy_ratio": 0.42,
  "blank_area_ratio_estimate": 0.31,
  "text_clipping_detected": false,
  "small_text_count": 0,
  "fallback_used": false,
  "quality_gate": "pass|warn|fail"
}
```

**Target thresholds for landscape 16:9:**

- title / headline: 72px以上を目標。最低56px。
- subtitle: 36px以上を目標。最低30px。
- body / card text: 32px以上を目標。最低28px。
- footnote / slide number: 24px以上。
- 20px以下の通常テキストは禁止。
- main visual / text group should use 30〜65% of canvas.
- blank area should not be plain empty background only. 背景装飾があれば許容。

**Implementation notes:**

- 最初はHTML/CSS文字列から font-size を抽出する簡易版でよい。
- Playwright screenshot後の画像解析は Sprint 3 以降でよい。
- `clamp()` は下限値・上限値を解析し、下限が小さすぎる場合は warn。
- inline style と `<style>` 両方を見る。

**Tests:**

```bash
cd /Users/seiyaeto/Antigravity/voiceslide-ai/backend
./venv/bin/python -m pytest tests/test_design_quality_metrics.py -q
```

Expected:

- `font-size: 18px` を fail/warn にできる。
- `font-size: clamp(1rem, 2vw, 2rem)` を小さすぎる可能性として warn にできる。
- 大きいタイトル + 32px本文は pass。
- 空のHTMLでもクラッシュしない。

---

### Sprint 3: Promptを「余白」から「画面活用」へ変更

**Objective:** AIが余白を「何も置かない場所」と解釈しないようにする。

**Files:**

- Modify: `backend/services/ai_slide_generator.py`
- Modify: `backend/tests/test_design_mode.py`
- Create or Modify: `docs/specs/voiceslide-design-prompt-guidelines.md`

**Prompt changes:**

Replace or amend current design guidance:

```text
画面の40-60%を余白に
```

with:

```text
画面全体を使って構成する。
余白は「空白」ではなく、背景の流れ、図形、光、カード、線、グラデーションで画面の密度を作るために使う。
主役テキストまたは主役ビジュアルは、画面の30〜65%を占める。
本文やカード内文字を小さくして解決しない。
横長スライドでは、タイトル72〜120px、サブタイトル36〜56px、カード本文32px以上を目安にする。
20px以下の通常テキストは禁止。
1スライド1メッセージ。補足文を増やすより、主役を大きくする。
```

**Pro mode addendum changes:**

`DESIGN_STRATEGY_SYSTEM_PROMPT` の `Pro Mode` 追加指示に以下を加える。

```text
Do not choose Minimal layout when it would make the main text small or leave the canvas underused.
If the content is short, enlarge the headline and create background structure, not empty space.
For each slide_layout, include `scale_hints` with target title/body font sizes and main occupancy.
```

**Tests:**

- `tests/test_design_mode.py` に、プロンプト文字列が最小フォント・画面占有・小文字禁止を含むことを確認するテストを追加。

---

### Sprint 4: fallback templates を VoiSlide品質へ上げる

**Objective:** AI生成やTextSafetyが失敗しても、最低品質を保つ。

**Files:**

- Modify: `backend/services/ai_slide_generator.py`
- Create: `backend/services/fallback_slide_templates.py`
- Create: `backend/tests/test_fallback_slide_templates.py`

**Templates:**

1. `fallback_title_slide`
   - 大タイトル
   - サブタイトル
   - 背景グラデーション
   - 装飾図形
   - スライド番号

2. `fallback_message_slide`
   - 大きな1メッセージ
   - 1〜2ポイント
   - 余白過多にならない背景構造

3. `fallback_cards_slide`
   - 2〜3カード
   - カード内文字32px以上
   - カードが画面中央だけに小さくならない

4. `fallback_closing_slide`
   - 締めの大きいメッセージ
   - 次アクション/まとめ

**Selection logic:**

- `title`: `fallback_title_slide`
- `closing`: `fallback_closing_slide`
- points 2〜3: `fallback_cards_slide`
- points 0〜1: `fallback_message_slide`

**Rules:**

- 20px以下の本文は禁止。
- title は最低56px。
- card body は最低28px、目標32px。
- 色は strategy の `color_palette` を使う。
- `word-break: keep-all; overflow: visible;` を維持する。
- PiP safe zone がある場合は既存 `inject_pip_safe_zone()` と併用する。

**Tests:**

```bash
cd /Users/seiyaeto/Antigravity/voiceslide-ai/backend
./venv/bin/python -m pytest tests/test_fallback_slide_templates.py -q
```

Expected:

- 各slide_typeで適切なfallback templateが選ばれる。
- 生成HTMLにtitleが含まれる。
- 20px以下のfont-sizeが通常本文に出ない。
- strategy colorがCSSに反映される。

---

### Sprint 5: Layout Plan JSON を strategy と分離する

**Objective:** strategy JSON失敗で全体が崩れないようにする。

**Files:**

- Modify: `backend/services/ai_slide_generator.py`
- Create: `backend/services/layout_plan.py`
- Create: `backend/tests/test_layout_plan.py`

**New flow:**

1. `generate_design_strategy()`
   - 全体コンセプト、配色、フォント、トーンだけ返す。

2. `generate_layout_plan()`
   - 各スライドの layout, scale, occupancy, fallback preference を返す。

3. `generate_slide_html()`
   - strategy + layout_plan + slide content を使ってHTML生成。

**Layout plan schema:**

```json
{
  "slide_number": 2,
  "layout_key": "cards",
  "layout_reason": "2つの評価項目を比較するため",
  "title_font_px_target": 82,
  "body_font_px_target": 34,
  "main_occupancy_target": 0.45,
  "blank_area_policy": "decorate_with_background_shapes",
  "density": "medium",
  "avoid": ["tiny text", "empty minimal layout", "plain centered small card"]
}
```

**Fallback behavior:**

- strategy JSONに失敗しても layout plan は deterministic fallback で作る。
- layout planに失敗しても slide_type based fallback を使う。
- `Minimal` は、短文かつ大タイトル構成でのみ許可。

**Tests:**

- 2枚スライドなら2件のlayout planが返る。
- closing slide が自動で `Minimal` 固定にならない。
- `main_occupancy_target` が 0.30 未満なら補正される。

---

### Sprint 6: 品質ゲートと自動デザイン修正

**Objective:** 生成後に小さい文字や余白過多を検出し、デザインだけ修正する。

**Files:**

- Modify: `backend/services/ai_slide_generator.py`
- Modify: `backend/services/design_quality_metrics.py`
- Create: `backend/tests/test_design_quality_gate.py`

**Flow:**

1. HTML生成。
2. `analyze_design_quality(html, screenshot_path=None)` を実行。
3. `quality_gate == pass` ならそのままレンダリング。
4. `warn` ならログに残し、原則通す。
5. `fail` なら1回だけ self-review に具体的修正指示を渡す。
6. 2回目も fail なら、美しい fallback template を使う。

**Auto-fix feedback examples:**

```text
カード内文字が24px未満です。カード本文を32px以上にしてください。
主役要素の画面占有率が低すぎます。タイトルまたはカード群を大きくし、画面の30〜65%を使ってください。
空いている領域が大きすぎます。背景グラデーション、図形、線、カード配置で構成してください。
```

**Limits:**

- 再生成は最大1回。
- 無限retryは禁止。
- cost telemetryに auto-fix の発生を記録する。

---

### Sprint 7: QA fixture とモデル比較を拡張

**Objective:** 1本のfixtureだけで判断しない。

**Files:**

- Modify: `docs/qa/fixtures/README.md`
- Modify: `docs/qa/results/template-design-quality-comparison.md`
- Create: `docs/qa/results/YYYY-MM-DD_model-comparison-template.md` または既存テンプレートを拡張

**Fixtures:**

1. short basic QA: 30秒前後
2. dense explanation: 60〜90秒、情報量多め
3. emotional story: 60〜90秒、抽象語多め
4. tutorial/process: 60〜120秒、手順説明
5. closing/CTA: 30〜60秒、締めメッセージ

**Model comparison targets:**

- `google/gemini-3-flash-preview`
- `google/gemini-3.1-pro-preview` または利用可能なPro系
- `anthropic/claude-sonnet-*`
- `anthropic/claude-opus-*`
- GPT系モデル
- 将来: image-background mode / GPT Image 2 background

**Record:**

- design_mode
- requested model
- actual model
- token/cost if available
- generation time
- fallback count
- quality gate result
- visual score

---

## 5. Claude Code に渡す実装指示案

```text
VoiSlide Movieのデザイン品質改善を、docs/specs/voiceslide-design-quality-upgrade.md に沿って実装してください。

前提:
- 作業ブランチは develop。
- mainマージ、本番反映、git pushは禁止。
- 既存未コミット差分を破棄しない。
- APIキーやsecret値を表示・保存しない。

今回の対象:
Sprint 1〜2だけを実装してください。

Sprint 1:
- generation telemetryを追加する。
- requested_model / actual_model / design_mode / stage / slide_number / fallback_reason / duration_ms を記録できるようにする。
- token/costは取得できる場合だけ。取得できない場合は null でよい。
- APIキー値は絶対に記録しない。

Sprint 2:
- backend/services/design_quality_metrics.py を追加する。
- HTML/CSSから小さいfont-sizeを検出する簡易メトリクスを実装する。
- landscape 16:9の目安として、title 56px未満、body 28px未満、通常テキスト20px以下をwarn/failにする。

テスト:
- backend/tests/test_generation_telemetry.py
- backend/tests/test_design_quality_metrics.py
- 既存 backend tests/test_design_mode.py が壊れないこと

完了条件:
- 新規テストがpassする。
- 既存デザインモードテストがpassする。
- docs/qa/results/template-design-quality-comparison.md にtelemetry項目が追加されている。
- 実装内容と未対応Sprintを短く報告する。
```

---

## 6. 検証コマンド

Sprint 1〜2 実装後:

```bash
cd /Users/seiyaeto/Antigravity/voiceslide-ai/backend
./venv/bin/python -m pytest tests/test_generation_telemetry.py tests/test_design_quality_metrics.py tests/test_design_mode.py -q
```

必要に応じて:

```bash
cd /Users/seiyaeto/Antigravity/voiceslide-ai
npm test -- --watch=false
npm run build
```

実生成QA:

```bash
cd /Users/seiyaeto/Antigravity/voiceslide-ai/backend
mkdir -p ../outputs ../uploads
OUTPUT_DIR="$PWD/../outputs" UPLOAD_DIR="$PWD/../uploads" DEBUG=true PORT=8001 ./venv/bin/python main.py
```

その後、visible Chrome/CDP で `docs/qa/fixtures/short_voislide_quality_check_32s.mp3` を使う。

---

## 7. 成功条件

### Short term

- 生成結果に、モデル名・fallback・生成時間が残る。
- 文字が小さいスライドを自動検出できる。
- QA結果に「なぜ小さい文字になったか」を書ける。

### Mid term

- fallbackでも最低限美しいスライドが出る。
- `Minimal` が空白過多・小文字化の原因になりにくい。
- `pro` の強みが2枚目以降にも出る。

### Long term

- モデル選択を感覚ではなく、品質・時間・コストで比較できる。
- GPT Image 2 等の画像生成は、背景・区切り・キービジュアルとして安全に比較できる。
- VoiSlide Movie の品質改善ループが、固定fixtureで継続運用できる。

---

## 8. 実装しないこと

このSpecでは以下をしない。

- full-slide image generation への全面移行。
- mainマージ。
- production deploy。
- APIキーの保存・表示。
- 既存未コミット差分の整理・削除。
- 大規模なUI刷新。

---

## 9. 関連ドキュメント

- `docs/specs/fix-pro-model-quality.md`
- `docs/qa/voiceslide-design-quality-rubric.md`
- `docs/qa/fixtures/README.md`
- `docs/qa/results/template-design-quality-comparison.md`
- `docs/qa/results/2026-05-02_flash_standard-vs-pro_short_voislide_quality_check.md`
- Vault: `04_Projects/Active/product-ops-board.md`

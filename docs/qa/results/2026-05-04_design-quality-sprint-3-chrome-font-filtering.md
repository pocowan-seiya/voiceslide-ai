# 2026-05-04 Design Quality Sprint 3 — chrome font filtering

実施日時: 2026-05-04 19:43 JST  
対象: VoiSlide Movie `design_quality_metrics`  
実行形態: Hermes orchestration + Codex CLI small task + Hermes review/TDD補正

## 背景

2026-05-04の固定fixture実生成QAで、`flash_standard` / `pro` とも telemetry と status API露出はOKだった一方、`design_quality_metrics.quality_gate` は `fail` が残った。

主な観察:

- 小さい文字が検出される
- fallback使用が残る
- 一部の16pxは本文ではなく、`body` のglobal defaultや `.slide-number` などのslide chromeである可能性がある

## 変更内容

`backend/services/design_quality_metrics.py` で、raw extraction と quality gate 用 extraction を分離した。

- `analyze_font_sizes()` は従来通り、すべての `font-size` を抽出する
- `analyze_design_quality()` は quality gate 用に content font sizes を使う
- quality gate では以下を除外する
  - `body`
  - `html`
  - `*`
  - `:root`
  - `.slide-number` / `.page-number` 系 selector/class/id
- inline style は `style` と `class` の属性順に依存しないようにした
- grouped selector は `body, .body` のような mixed selector で content側を落としすぎないよう、全selectorがnon-contentの場合だけ除外する

## 追加・強化したテスト

`backend/tests/test_design_quality_metrics.py`

追加/強化:

- raw extraction は global/chrome のfont-sizeも含む
- `body { font-size: 16px; }` と `.slide-number { font-size: 16px; }` があっても、title/bodyが十分大きければ `quality_gate=pass`
- inline slide chrome は `style` が `class` より前でも除外される
- `body, .body { font-size: 32px; }` のような grouped selector で content font-size が残る
- title 60px は `warn` になり、title warningが出る

## TDDメモ

Codexが最初に追加した回帰テストは、旧実装で `quality_gate=fail` になりREDを確認。  
Hermes側で追加した `style` before `class` と grouped selector のテストも、修正前にREDを確認してから実装を補正した。

## 検証結果

```bash
cd /Users/seiyaeto/Antigravity/voiceslide-ai/backend
./venv/bin/python -m py_compile main.py services/generation_telemetry.py services/design_quality_metrics.py services/ai_utils.py services/openrouter_utils.py services/ai_slide_generator.py
./venv/bin/python -m pytest tests/test_generation_telemetry.py tests/test_design_quality_metrics.py tests/test_design_mode.py tests/test_status_telemetry_fields.py -q
```

結果:

```text
44 passed, 11 warnings in 2.04s
```

warnings:

- `httplib2/auth.py` DeprecationWarning
- FastAPI `on_event` DeprecationWarning

## Independent review

独立レビュー結果:

- Blocking issue: なし
- Sprint 3 filtering behaviorは安全
- raw `analyze_font_sizes()` と gated `analyze_design_quality()` の分離は妥当
- non-blocking suggestionとして出た grouped selector / incomplete assertion / raw extractor regression はHermes側で反映済み

## 注意

この変更は「false/symptomatic failを減らす」ための最小改善。  
実際の本文が20px以下の場合は引き続きfailになる。

今回は実AI生成の再実行はしていない。次にvisible Chrome/CDP固定fixtureで再生成し、`quality_gate` がどこまで改善したか確認する。

## 次アクション

1. visible Chrome/CDPで `short_voislide_quality_check_32s.mp3` を再生成
2. `flash_standard` / `pro` の `design_quality_metrics` を比較
3. まだfailする場合は、本文サイズ・fallback template・prompt/layout改善に分解する

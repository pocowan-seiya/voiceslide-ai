# 2026-05-04 Design Quality Sprint 4 fallback mode / telemetry

実施日時: 2026-05-04 20:45〜20:59 JST  
対象: VoiSlide Movie fixed fixture QA follow-up  
目的: `pro` slide 1 が `flash_standard` slide 1 と同一hashになった原因と、`fallback_used=true` が残る理由を小さく調査・改善する

## 結論

Codex CLIで原因分析と最小修正を実施した。

`pro` と `flash_standard` が同一画像になった主因は、両方がfallback HTMLに落ちたとき、fallback generatorがdesign modeを見ていなかったこと。  
同じslide番号・同じfallback strategyなら、`pro` でも `flash_standard` と同じHTMLになりうる状態だった。

今回の修正で、fallback時でも `pro` は `flash_standard` と別variantを選ぶ。  
これにより、少なくともfallback同士でslide 1がbyte-identicalになる問題は防げる。

`fallback_used=true` 自体は消していない。  
これは実際にfallback HTMLが使われていることを示すため、Sprint 4では「区別できる」「telemetryで理由を追いやすい」状態にした。

## 変更内容

### `backend/services/ai_slide_generator.py`

- `generate_slide_html()` の例外fallback時に telemetry を記録
  - `stage="fallback"`
  - `fallback_reason="Slide HTML generation failed"`
  - `slide_number`
  - `design_mode`
- 例外メッセージは `redact_secrets()` 後に `warning` と stdout へ出す
- `generate_fallback_html()` で `strategy["_design_mode"]` を見てvariantを分ける
  - `flash_standard`: `(slide_number - 1) % 4`
  - `pro`: `slide_number % 4`

### `backend/tests/test_design_mode.py`

- `test_pro_fallback_html_does_not_match_flash_fallback_html_for_same_slide` を追加
- 同じslide contentでも、fallback時に `pro` と `flash_standard` が同一HTMLにならないことを確認

### `backend/tests/test_generation_telemetry.py`

- `test_slide_html_exception_fallback_records_telemetry` を追加
- slide HTML生成例外時にfallback telemetryが記録されることを確認
- `test_slide_html_exception_redacts_secret_like_warning_and_stdout` を追加
- 例外メッセージにAPIキー風文字列が含まれても、telemetry warningとstdoutに秘密値断片が出ないことを確認

## TDDメモ

Codex側で新規テストのRED確認後に最小修正。  
Hermesレビュー後、stdoutの未redact経路を見つけたため追加でREDを確認した。

追加RED確認:

```text
FAILED tests/test_generation_telemetry.py::TestSlideFallbackTelemetry::test_slide_html_exception_redacts_secret_like_warning_and_stdout
AssertionError: assert '1234567890abcdef' not in captured.out
```

その後、`print` と `warning` の両方で `redact_secrets(str(e))` を使うように修正した。

## 検証

```bash
cd /Users/seiyaeto/Antigravity/voiceslide-ai/backend
./venv/bin/python -m py_compile main.py services/generation_telemetry.py services/design_quality_metrics.py services/ai_utils.py services/openrouter_utils.py services/ai_slide_generator.py
./venv/bin/python -m pytest tests/test_design_mode.py tests/test_design_quality_metrics.py tests/test_generation_telemetry.py tests/test_status_telemetry_fields.py -q
```

結果:

```text
47 passed, 11 warnings in 0.78s
```

warnings:

- `httplib2/auth.py` の DeprecationWarning
- FastAPI `on_event` の DeprecationWarning

## 独立レビュー

delegate review結果: blocking issueなし。

指摘:

- fallback telemetry追加は安全
- fallback variant分岐は今回の小目標に対して妥当
- telemetry warningはredactionされるが、stdout printは未redactだった

対応:

- stdout printもredactするテストを追加
- 実装修正済み

## 影響範囲

改善したこと:

- fallback同士で `pro` slide 1 と `flash_standard` slide 1 が同一HTMLになる問題を軽減
- slide HTML生成例外fallbackの理由をtelemetryで追える
- 例外メッセージ由来の秘密値風文字列をstdout/telemetryでredact

まだ残ること:

- `fallback_used=true` を根本的に減らす修正ではない
- `pro` strategy生成自体がfallback/欠落した場合、Pro固有のlayout/font指示が弱くなる可能性は残る
- 実生成で再度hash差・fallback_count改善を確認する必要がある

## 次アクション候補

1. visible Chrome/CDP固定fixtureを再生成して、`pro` slide 1 と `flash_standard` slide 1 のhash差を確認する
2. `generation_telemetry` のstage別fallback理由をQA結果表に出す
3. `pro` strategyが `slide_layouts` を欠いた場合の補完ロジックを小タスク化する
4. `flash_standard` slide 2 の本文小ささをprompt/layout側で改善する

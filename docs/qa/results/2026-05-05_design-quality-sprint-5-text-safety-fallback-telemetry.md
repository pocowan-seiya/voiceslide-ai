# 2026-05-05 Design Quality Sprint 5 text-safety fallback telemetry

実施日時: 2026-05-05 10:02〜10:09 JST  
対象: VoiSlide Movie Design Quality / generation telemetry  
repo: `/Users/seiyaeto/Antigravity/voiceslide-ai`  
branch: `develop`

## 結論

Sprint 4 visible Chrome再生成QAで見つかった observability gap を1つ修正した。

問題は、`fallback_used=true` のslideがあるのに、telemetry上は `Strategy generation failed` しか見えないこと。  
原因の一部は `ensure_text_visible()` がfallback HTMLへ落ちる時に、slide単位telemetryを記録していなかったこと。

今回、`ensure_text_visible()` の以下2経路で `stage=fallback` のtelemetryを記録するようにした。

- visible textがない
- titleが見つからない

## 変更内容

### production

`backend/services/ai_slide_generator.py`

- `ensure_text_visible()` のfallback返却前に `_record_text_safety_fallback()` を呼ぶようにした
- `fallback_reason` を安定文字列で記録
  - `TextSafety fallback: no visible text`
  - `TextSafety fallback: title missing`
- `slide_number` と `design_mode` を記録
- deterministic/local処理として以下で記録
  - `provider=local`
  - `requested_model=deterministic-text-safety`
  - `actual_model=deterministic-text-safety`
- title missing時のstdoutも `redact_secrets()` 済みpreviewに変更

### tests

`backend/tests/test_generation_telemetry.py`

追加/拡張:

- `test_text_safety_fallback_records_slide_level_telemetry`
  - RED: `fallback_count` が0で失敗
  - GREEN: no visible text fallbackがslide-level telemetryに出る
- `test_text_safety_title_missing_fallback_redacts_warning_and_stdout`
  - RED: title断片がstdoutに出て失敗
  - GREEN: warning/stdoutともsecret-like文字列を出さない

## TDD evidence

### RED 1

```text
assert collector.summary()["fallback_count"] == 1
E assert 0 == 1
```

### RED 2

```text
assert "1234567890abcdef" not in captured.out
E AssertionError
```

### GREEN

```bash
cd /Users/seiyaeto/Antigravity/voiceslide-ai/backend
./venv/bin/python -m pytest \
  tests/test_generation_telemetry.py::TestSlideFallbackTelemetry::test_text_safety_title_missing_fallback_redacts_warning_and_stdout \
  tests/test_generation_telemetry.py::TestSlideFallbackTelemetry::test_text_safety_fallback_records_slide_level_telemetry -q
```

結果:

```text
2 passed, 9 warnings
```

## Verification

```bash
cd /Users/seiyaeto/Antigravity/voiceslide-ai/backend
./venv/bin/python -m py_compile main.py services/generation_telemetry.py services/design_quality_metrics.py services/ai_utils.py services/openrouter_utils.py services/ai_slide_generator.py
./venv/bin/python -m pytest tests/test_generation_telemetry.py tests/test_design_quality_metrics.py tests/test_design_mode.py tests/test_status_telemetry_fields.py -q
git diff --check -- services/ai_slide_generator.py tests/test_generation_telemetry.py
```

結果:

```text
49 passed, 11 warnings in 0.86s
```

warningsは既存の `httplib2` / FastAPI `on_event` DeprecationWarning。

## Independent review

小変更後に独立レビューを実施。

結果:

- blocking issueなし
- `provider=local` / `deterministic-text-safety` は妥当
- `fallback_count` が増えるのは意図通り
- 注意点: `total_calls == entry_count` のため、local deterministic fallbackも `total_calls` に含まれる
- レビュー指摘: title missing時のstdout title previewが未redact
  - 追加REDテスト後に修正済み

## Remaining note

`total_calls` は現在 `entry_count` aliasなので、外部AI/API callだけではなくtelemetry event数として増える。  
将来UIで「外部AI呼び出し回数」を見せるなら、別途 `ai_call_count` / `total_events` の分離が必要。

## Next actions

1. visible Chrome/CDP固定fixtureを再生成して、`TextSafety fallback:*` が実データに出るか確認する
2. `pro` のdecorative/footer textをquality gate上どう扱うか整理する
3. `Strategy generation failed` の原因を追う

## commit / push

未実施。

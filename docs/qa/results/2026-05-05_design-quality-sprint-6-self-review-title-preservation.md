# 2026-05-05 Design Quality Sprint 6 self-review title preservation

実施日時: 2026-05-05 JST  
対象: VoiSlide Movie fixed fixture regeneration after self-review title preservation guard  
frontend: `http://127.0.0.1:3010/`  
backend: `http://127.0.0.1:8001`  
CDP: `http://127.0.0.1:9223`  
fixture: `docs/qa/fixtures/short_voislide_quality_check_32s.mp3`

## 結論

Sprint 5で見えた `TextSafety fallback: title missing` の主因は、AI self-reviewがタイトル文言を書き換える経路だった可能性が高い。

対応として、`self_review_slide()` に「改善後HTMLが元タイトルを失ったら、改善後HTMLを採用せず元HTMLを返す」guardを追加した。

TDDで以下を確認した。

1. RED: self-reviewが `日本語が読みやすく、自然に繋がること` を `読みやすい日本語で自然につなぐ` へ書き換えると、既存実装はそのまま採用して失敗。
2. GREEN: 元タイトルが改善後HTMLに存在しない場合、元HTMLを返すようにしてpass。

追加で、OpenRouter error payloadに含まれる `user_...` provider/user IDがtelemetry warningへ残りうることを見つけたため、redaction対象へ追加した。

## 変更ファイル

- `backend/services/ai_slide_generator.py`
  - `self_review_slide()` にtitle-preservation guardを追加
- `backend/services/generation_telemetry.py`
  - `user_...` provider/user ID redactionを追加
- `backend/tests/test_generation_telemetry.py`
  - `test_self_review_rejects_title_rewrite`
  - `test_redacts_openrouter_user_id`

## 検証

```bash
cd /Users/seiyaeto/Antigravity/voiceslide-ai/backend
./venv/bin/python -m py_compile main.py services/generation_telemetry.py services/design_quality_metrics.py services/ai_utils.py services/openrouter_utils.py services/ai_slide_generator.py
./venv/bin/python -m pytest tests/test_generation_telemetry.py tests/test_design_quality_metrics.py tests/test_design_mode.py tests/test_status_telemetry_fields.py -q
cd /Users/seiyaeto/Antigravity/voiceslide-ai
git diff --check
```

Result:

```text
51 passed, 11 warnings in 0.95s
git diff --check: pass
```

Warnings are existing dependency/FastAPI deprecation warnings.

## Real generation rerun

最新backendで固定fixtureを再実行した。

### flash_standard

- job_id: `975651f2-89bf-4110-b96f-81577034c27b`
- `entry_count=7`
- `total_calls=7`
- `fallback_count=2`
- fallback:
  - `Strategy generation failed`: 1
  - `TextSafety fallback: title missing`: 1
- quality:
  - slide 1: fail（small text 2件、title 48px）
  - slide 2: pass

Sprint 5では `flash_standard` のTextSafety fallbackが2件だった。  
Sprint 6では1件に減った。

### pro

- job_id: `5c29f10c-3f77-4250-92b5-c7740e9cac0b`
- `entry_count=5`
- `total_calls=5`
- `fallback_count=3`
- fallback:
  - `Strategy generation failed`: 1
  - `Slide HTML generation failed`: 2

`pro` はOpenRouter credit不足の upstream error により、実AI slide HTML生成が2枚ともfallbackへ落ちた。  
このため、Sprint 6のtitle-preservation効果確認としては参考扱い。

保存時はprovider/user IDをredact済み。

## Vision確認

`comparison_contact_sheet.jpg` をvision確認した。

- 4枚とも主要タイトルは見えている
- `flash_standard` / `pro` ともタイトルは保持されている
- 明らかなplaceholder崩れはない
- 小さいcard / bullet / caption textは残る
- `pro slide 2` はタイトルの改行が少し不自然

## Artifacts

Folder:

`docs/qa/results/2026-05-05_design-quality-sprint-6-self-review-title-preservation/`

Files:

- `sanitized_api_result.json`
- `artifact_hashes.json`
- `summary.json`
- `comparison_contact_sheet.jpg`
- `flash_standard_slide_001.png`
- `flash_standard_slide_002.png`
- `pro_slide_001.png`
- `pro_slide_002.png`

## 次アクション

1. `flash_standard slide 2` に残った `TextSafety fallback: title missing` の原因を、pre/post self-review HTML snapshotで切る
2. OpenRouter credit不足時のwarning redactionを継続確認する
3. `pro` decorative/footer/caption textをquality gate対象に含めるか整理する
4. OpenRouter credit不足のときは、`pro` real generation QAは結果を参考扱いにする

## commit / push

未実施。

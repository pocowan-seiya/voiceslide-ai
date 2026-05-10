# VoiSlide Design Quality Sprint 19: Post-hardening regeneration QA

Date: 2026-05-08 12:24 JST
Branch: develop
Scope: Sprint 18 の title/headline CSS hardening 後に、同じ固定fixtureで `flash_standard` / `pro` を再生成し、日本語タイトルの語中1文字分断が実ブラウザ描画上でも解消しているか確認する。

## Fixture

- Audio: `docs/qa/fixtures/short_voislide_quality_check_32s.mp3`
- Transcript: `docs/qa/fixtures/short_voislide_quality_check_32s.txt`
- Slides: controlled 2-slide outline
- Aspect ratio: landscape
- Design preference: 日本語タイトルは読みやすく、語中で1文字分断しない。余白はあるが画面を十分に使う。

## Environment

- Frontend: `http://127.0.0.1:3000/` already running
- Backend: `http://127.0.0.1:8001/`
- Visible Chrome/CDP: `hermes-chrome voislide`, CDP `9223`
- Backend command:
  - `OUTPUT_DIR="$PWD/../outputs" UPLOAD_DIR="$PWD/../uploads" DEBUG=true PORT=8001 ./venv/bin/python main.py`

## Jobs

### flash_standard

- Job ID: `143c1d64-fd41-448d-b73d-53cc8d92d769`
- Status: `complete`
- Message: `バッチ完了 (1-2)`
- Slides: 2
- Telemetry:
  - `total_calls`: 5
  - `total_duration_ms`: 87051
  - `fallback_count`: 0
  - `total_input_tokens`: 14257
  - `total_output_tokens`: 11742
- Design metrics:
  - slide 1: pass, `min_font_size_px=26.0`, `small_text_count=0`, `fallback_used=false`
  - slide 2: pass, `min_font_size_px=115.2`, `small_text_count=0`, `fallback_used=false`

### pro

- Job ID: `18f84d23-cc29-4317-8d44-185a74c57b26`
- Status: `complete`
- Message: `バッチ完了 (1-2)`
- Slides: 2
- Telemetry:
  - `total_calls`: 5
  - `total_duration_ms`: 97724
  - `fallback_count`: 0
  - `total_input_tokens`: 16729
  - `total_output_tokens`: 13393
- Design metrics:
  - slide 1: pass, `min_font_size_px=72.0`, `small_text_count=0`, `fallback_used=false`
  - slide 2: pass, `min_font_size_px=26.0`, `small_text_count=0`, `fallback_used=false`

## Visual QA

Contact sheet:

- `docs/qa/results/2026-05-08_sprint19_post-hardening-regeneration-qa/contact_sheet_flash_vs_pro_2slide_post_hardening.png`

Vision QA result:

- 日本語タイトルの語中1文字分断: pass
  - `読/みやすさ`, `ス/ライド`, `作/る` のような分断は確認されなかった。
- タイトル可読性: pass
  - 4枚とも大きく明瞭。
  - `音声からスライド動画を / 作る流れ`、`日本語の読みやすさと / 復元確認` は自然な改行。
- 余白 / 画面使用: pass
  - `flash_standard` は余白多めで破綻なし。
  - `pro` は画面をより使い、視覚階層も良い。
- pro品質低下: pass
  - 背景、文字階層、カード表現、装飾が `flash_standard` より高品質。
- self-review diagnostic混入: pass
  - QA文言、自己評価、プロンプト断片、診断ログの混入は見当たらない。

## Artifact summary

- `docs/qa/results/2026-05-08_sprint19_post-hardening-regeneration-qa/artifact_summary.json`
- `docs/qa/results/2026-05-08_sprint19_post-hardening-regeneration-qa/flash_standard_slide_001.png`
- `docs/qa/results/2026-05-08_sprint19_post-hardening-regeneration-qa/flash_standard_slide_002.png`
- `docs/qa/results/2026-05-08_sprint19_post-hardening-regeneration-qa/pro_slide_001.png`
- `docs/qa/results/2026-05-08_sprint19_post-hardening-regeneration-qa/pro_slide_002.png`

## Verification

Command:

```bash
cd backend
./venv/bin/python -m py_compile services/ai_slide_generator.py services/design_quality_metrics.py
./venv/bin/python -m pytest tests/test_design_mode.py tests/test_design_quality_metrics.py tests/test_generation_telemetry.py tests/test_sprint14_design_quality.py tests/test_sprint15_design_quality.py -q
cd ..
git diff --check
```

Result:

- `py_compile`: pass
- targeted pytest: `69 passed, 9 warnings in 0.61s`
- `git diff --check`: pass

## Conclusion

Sprint 18 の `word-break: keep-all; overflow-wrap: normal; line-break: strict; text-wrap: balance;` hardening は、今回の固定fixture再生成では有効に見える。

Sprint 18で見えていた `読 / みやすさ`、`ス / ライド` 系のブラウザ自動1文字分断は、Sprint 19再生成QAでは再発しなかった。

## Remaining notes

- 今回は controlled 2-slide fixture の再生成QA。
- 5-slide smoke 全体や別fixtureでは、今後も small text / fallback / canvas occupancy を継続確認する。
- `pro` slide 2 の `min_font_size_px=26.0` は pass 扱いだが、今後のより厳密なカード/ラベル別メトリクスでは追加観察対象にできる。

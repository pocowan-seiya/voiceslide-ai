# VoiSlide Design Quality Sprint 18 — Real Generation Title Wrap QA

- Date: 2026-05-08 12:09 JST
- Repo: `/Users/seiyaeto/Antigravity/voiceslide-ai`
- Branch: `develop`
- Scope: Sprint 17 の日本語タイトル `<br>` 補正を、固定 fixture の実生成で確認し、実ブラウザ描画上の1文字分断まで追加で回帰テスト化する。

## Fixture

- Audio: `docs/qa/fixtures/short_voislide_quality_check_32s.mp3`
- Source text: `docs/qa/fixtures/short_voislide_quality_check_32s.txt`
- Visible Chrome/CDP profile: `hermes-chrome voislide`, CDP `9223`
- Backend: `http://127.0.0.1:8001`

## Real generation runs

### Initial 5-slide smoke

- Mode: `flash_standard`
- Job ID: `53311ad9-b3be-470c-ad72-5e940d0c512a`
- Status: `complete`
- Slides: 5
- Telemetry summary:
  - `total_calls`: 12
  - `total_duration_ms`: 169357
  - `fallback_count`: 1
  - `total_input_tokens`: 30587
  - `total_output_tokens`: 21674
- Design metrics:
  - slide 1: pass
  - slide 2: pass
  - slide 3: fail, `small_text_count=1`, minimum 18px
  - slide 4: pass
  - slide 5: pass, fallback used

### Controlled 2-slide comparison

Artifacts:

- `docs/qa/results/2026-05-08_sprint18_real-generation-title-break-qa/contact_sheet_flash_vs_pro_2slide.png`
- `docs/qa/results/2026-05-08_sprint18_real-generation-title-break-qa/artifact_summary.json`

#### flash_standard

- Job ID: `660fc45a-900e-49a5-a754-d9e9b70d351c`
- Status: `complete`
- Slides: 2
- Telemetry summary:
  - `total_calls`: 5
  - `total_duration_ms`: 114658
  - `fallback_count`: 0
  - `total_input_tokens`: 14535
  - `total_output_tokens`: 12029
- Design metrics:
  - slide 1: pass
  - slide 2: pass
- HTML `<br>` findings:
  - slide 1: no Japanese `<br>` split
  - slide 2: `日本語の読みやすさと<br/>復元確認` remained. This is phrase-level and acceptable.

#### pro

- Job ID: `69069177-84b3-482d-9f17-405444aca075`
- Status: `complete`
- Slides: 2
- Telemetry summary:
  - `total_calls`: 5
  - `total_duration_ms`: 118165
  - `fallback_count`: 0
  - `total_input_tokens`: 17046
  - `total_output_tokens`: 14608
- Design metrics:
  - slide 1: fail, `small_text_count=2`, minimum 16px
  - slide 2: pass
- HTML `<br>` findings:
  - slide 1: `音声からスライド動画を<br/>作る流れ` remained. This is phrase-level and acceptable.
  - slide 2: no Japanese `<br>` split.

## Visual QA result

Vision review of the contact sheet found that Sprint 17 fixed hard-coded bad `<br>` splits, but real browser rendering still produced bad automatic Japanese wraps:

- `flash_standard` slide 2: `日本語の読 / みやすさと / 復元確認`
- `pro` slide 1: `音声からス / ライド動画を / 作る流れ`

These are not caused by bad `<br>` in the HTML. They are browser line-wrap behavior caused by title CSS allowing Japanese line breaks at arbitrary character boundaries.

No self-review diagnostic text was visible in the generated slides.

## Sprint 18 code change

Updated `backend/services/ai_slide_generator.py`:

- `_prevent_title_clipping_in_css()` now removes dangerous clipping/wrapping declarations:
  - `white-space: nowrap`
  - `text-overflow: clip/ellipsis`
  - `overflow: hidden`, `overflow-x: hidden`, `overflow-y: hidden`
  - `overflow-wrap: anywhere`
  - existing `word-break: normal/break-all/break-word/keep-all`
- It then appends title-safe wrapping rules:
  - `white-space: normal`
  - `overflow: visible`
  - `overflow-wrap: normal`
  - `word-break: keep-all`
  - `line-break: strict`
  - `text-wrap: balance`

Rationale:

- Sprint 17 handled explicit bad `<br>` tags.
- Sprint 18 handles browser-created 1-character Japanese wraps.
- The prior `word-break: normal` was not strict enough for Japanese titles.

## Tests added/updated

Updated `backend/tests/test_sprint15_design_quality.py`:

- Changed clipping-rule test to expect `word-break: keep-all`.
- Added:
  - `test_harden_generated_html_typography_prevents_browser_japanese_title_one_character_wraps`

## Verification

### RED

Command:

```bash
cd backend
./venv/bin/python -m pytest \
  tests/test_sprint15_design_quality.py::test_harden_generated_html_typography_prevents_title_clipping_rules \
  tests/test_sprint15_design_quality.py::test_harden_generated_html_typography_prevents_browser_japanese_title_one_character_wraps -q
```

Result:

- `2 failed, 9 warnings`

### GREEN focused

Same command after code change:

- `2 passed, 9 warnings`

### Targeted verification

Command:

```bash
cd backend
./venv/bin/python -m py_compile services/ai_slide_generator.py services/design_quality_metrics.py
./venv/bin/python -m pytest tests/test_design_mode.py tests/test_design_quality_metrics.py tests/test_generation_telemetry.py tests/test_sprint14_design_quality.py tests/test_sprint15_design_quality.py -q
git diff --check
```

Result:

- `69 passed, 9 warnings`
- `git diff --check`: pass

## Remaining work

- Re-run the same 2-slide real generation after Sprint 18 to visually confirm `word-break: keep-all` removes browser-created 1-character title wraps.
- Add a screenshot/render-level metric for title one-character line fragments. Current deterministic checks only verify generated HTML/CSS.
- Investigate design metrics failures from real generation:
  - initial flash slide 3: 18px small text
  - pro slide 1: 16px small text

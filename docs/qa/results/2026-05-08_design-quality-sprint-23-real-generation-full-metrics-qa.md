# Design Quality Sprint 23: Real Generation Full Metrics QA

Date: 2026-05-08 17:31 JST
Repo: `/Users/seiyaeto/Antigravity/voiceslide-ai`
Backend: `/Users/seiyaeto/Antigravity/voiceslide-ai/backend`

## Purpose

Sprint 20〜22-Bで追加した design quality metrics を、固定fixtureの実生成artifactに適用する。

確認対象:

- `flash_standard`
- `pro`
- HTML/CSS deterministic metric
- Browser computed layout metric
- Screenshot blank-area metric
- Screenshot visual-density metric
- 日本語タイトルの1文字分断
- self-review diagnostic混入
- small text
- 余白過多 / 主役要素が小さすぎる問題

## Fixture

- Audio: `docs/qa/fixtures/short_voislide_quality_check_32s.mp3`
- Text: `docs/qa/fixtures/short_voislide_quality_check_32s.txt`
- Slides: 2

## Jobs

| mode | job id | status | total calls | total duration | fallback |
|---|---|---:|---:|---:|---:|
| `flash_standard` | `17ed0f93-d70b-42ae-867d-99d908e2146b` | complete | 5 | 145,753 ms | 0 |
| `pro` | `c540ed73-f944-4139-8729-099382e4f184` | complete | 5 | 219,089 ms | 0 |

## Artifacts

Directory:

`docs/qa/results/2026-05-08_sprint23_real-generation-metrics-qa/`

Files:

- `flash_standard_slide_001.png`
- `flash_standard_slide_002.png`
- `pro_slide_001.png`
- `pro_slide_002.png`
- `flash_standard_slide_data.json`
- `pro_slide_data.json`
- `artifact_summary.json`
- `contact_sheet_flash_vs_pro_sprint23.png`

## Metric Results

### flash_standard

| slide | static gate | static occupancy | browser gate | browser occupancy | screenshot gate | visual content | warnings |
|---:|---|---:|---|---:|---|---:|---|
| 1 | pass | null | pass | 0.975317 | warn | 0.070179 | screenshot visual-density under 0.10 |
| 2 | warn | 0.000868 | warn | 0.000868 | pass | 0.241198 | static/browser occupancy under 0.30 |

Notes:

- Slide 1: Browser layout上は画面を使えているが、screenshot visual-densityは `0.070179` でwarn。
- Slide 2: static/browser occupancyが `0.000868` でwarn。ただしscreenshot visual-densityはpass。

### pro

| slide | static gate | static occupancy | browser gate | browser occupancy | screenshot gate | visual content | warnings |
|---:|---|---:|---|---:|---|---:|---|
| 1 | warn | 0.000347 | warn | 0.000347 | pass | 0.142212 | static/browser occupancy under 0.30 |
| 2 | pass | 1.0 | pass | 1.0 | pass | 0.194679 | none |

Notes:

- Slide 1: screenshot上は十分な表示密度だが、HTML/CSS main element occupancyは `0.000347` と誤検出または候補選定不足の可能性あり。
- Slide 2: all pass。

## Vision QA

Contact sheet:

`docs/qa/results/2026-05-08_sprint23_real-generation-metrics-qa/contact_sheet_flash_vs_pro_sprint23.png`

Vision findings:

1. `flash_standard` slide 1 has a major Japanese title rendering problem.
   - Title visually reads as `音声からスライド動画を作...` and the ending is broken/clipped.
   - Expected title is `音声からスライド動画を作る流れ`.
   - This is a regression target for the next sprint.
2. self-review diagnostic text was not visible in the contact sheet.
3. Small text exists mainly in decorative labels and metadata.
   - `pro` slide 2 card body is the main practical readability concern.
4. `pro` quality is higher than `flash_standard` in this run.
   - `pro` slide 1 title wrap is natural.
   - `pro` slide 2 has clearer information architecture.
5. `flash_standard` still has unstable Japanese title layout.

## Verification

Commands run from `backend/` unless noted:

```bash
./venv/bin/python -m py_compile services/design_quality_metrics.py services/ai_slide_generator.py
./venv/bin/python -m pytest tests/test_design_quality_metrics.py -q
./venv/bin/python -m pytest tests/test_generation_telemetry.py tests/test_design_quality_metrics.py tests/test_design_mode.py tests/test_sprint14_design_quality.py tests/test_sprint15_design_quality.py -q
```

Results:

- `py_compile`: pass
- `tests/test_design_quality_metrics.py`: `38 passed, 9 warnings`
- targeted verification: `83 passed, 9 warnings`

From repo root:

```bash
git diff --check
```

Result:

- pass

## Git Status Note

`git status --short --branch` shows many existing modified/untracked files across the repo, including Sprint 14〜23 QA/test files. Sprint 23 did not attempt cleanup or commit.

## Conclusion

Sprint 23 real generation QA completed.

Important result:

- Metrics pipeline itself runs end-to-end on new real generation artifacts.
- `pro` is mostly stable.
- `flash_standard` slide 1 shows a visible Japanese title clipping/break regression that current deterministic metrics did not catch.

Recommended next sprint:

- Sprint 24: add screenshot/DOM regression for title clipping and broken terminal Japanese characters.
- Target case: `flash_standard` title `音声からスライド動画を作る流れ`.
- Detection should catch visible clipping even when DOM text and font-size metrics pass.

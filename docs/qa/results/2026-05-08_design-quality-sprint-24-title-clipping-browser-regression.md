# Design Quality Sprint 24: Browser Title Clipping Regression

Date: 2026-05-08 17:38 JST
Repo: `/Users/seiyaeto/Antigravity/voiceslide-ai`
Backend: `/Users/seiyaeto/Antigravity/voiceslide-ai/backend`

## Purpose

Sprint 23 real generation QA found a visible regression:

- `flash_standard` slide 1 title visually clipped at the end.
- DOM text was still correct: `音声からスライド動画を作る流れ`.
- Static HTML/CSS metrics and browser occupancy metrics did not catch it.

Sprint 24 adds a browser-based title overflow regression so DOM text that is visually clipped is caught automatically.

## Root Cause Evidence

Sprint 23 artifact:

`docs/qa/results/2026-05-08_sprint23_real-generation-metrics-qa/flash_standard_slide_data.json`

Browser computed evidence for `h1`:

- text: `音声からスライド動画を作る流れ`
- `clientWidth`: `1546`
- `scrollWidth`: `1978`
- `clientHeight`: `151`
- `scrollHeight`: `168`
- CSS included:
  - `font-size: 128px`
  - `max-width: 92%`
  - `word-break: keep-all`
  - `overflow-wrap: normal`
  - `-webkit-text-fill-color: transparent`
  - `background-clip: text`

Conclusion:

- The text node was present.
- The rendered title box was too narrow for the no-break Japanese title.
- Because the title uses gradient text with transparent fill and background clipping, overflow can become visually broken/clipped even when DOM text is intact.

## RED

Added regression test:

```bash
./venv/bin/python -m pytest tests/test_design_quality_metrics.py::TestAnalyzeDesignQuality::test_browser_layout_detects_japanese_title_horizontal_clipping -q
```

Result before implementation:

- `1 failed, 9 warnings`
- Failure: `text_clipping_detected` stayed `False`.

## GREEN Implementation

File:

`backend/services/design_quality_metrics.py`

Added:

- `_detect_title_clipping_with_browser(html)`
  - Uses Playwright Chromium.
  - Checks `h1`, `h2`, `.title`, `.headline`, `.main-title`.
  - Detects title overflow when:
    - `scrollWidth > clientWidth + 2`, or
    - `scrollHeight > clientHeight + 2`.
- `analyze_design_quality_with_browser_layout()` now sets:
  - `text_clipping_detected: True`
  - `quality_gate: warn` when previously pass
  - warning: `タイトル要素の横幅または高さが不足し、ブラウザ描画で文字がはみ出しています。`

## GREEN Result

```bash
./venv/bin/python -m pytest tests/test_design_quality_metrics.py::TestAnalyzeDesignQuality::test_browser_layout_detects_japanese_title_horizontal_clipping -q
```

Result:

- `1 passed, 9 warnings`

## Sprint 23 Artifact Reapply

Output summary:

`docs/qa/results/2026-05-08_sprint23_real-generation-metrics-qa/sprint24_title_clipping_reapply_summary.json`

| mode | slide | gate | text clipping | occupancy | note |
|---|---:|---|---:|---:|---|
| `flash_standard` | 1 | warn | true | 0.975317 | Sprint 23 visual issue now detected |
| `flash_standard` | 2 | warn | false | 0.000868 | existing occupancy warning |
| `pro` | 1 | warn | false | 0.000347 | existing occupancy warning |
| `pro` | 2 | pass | false | 1.0 | OK |

## Verification

Commands:

```bash
./venv/bin/python -m pytest tests/test_design_quality_metrics.py -q
./venv/bin/python -m pytest tests/test_generation_telemetry.py tests/test_design_quality_metrics.py tests/test_design_mode.py tests/test_sprint14_design_quality.py tests/test_sprint15_design_quality.py -q
./venv/bin/python -m py_compile services/design_quality_metrics.py services/ai_slide_generator.py
```

Results:

- design metrics focused: `39 passed, 9 warnings`
- targeted verification: `84 passed, 9 warnings`
- `py_compile`: pass

Repo root:

```bash
git diff --check
```

Result:

- pass

## Changed Files

- `backend/services/design_quality_metrics.py`
- `backend/tests/test_design_quality_metrics.py`
- `docs/qa/results/2026-05-08_design-quality-sprint-24-title-clipping-browser-regression.md`
- `docs/qa/results/2026-05-08_sprint23_real-generation-metrics-qa/sprint24_title_clipping_reapply_summary.json`

## Conclusion

Sprint 24 completed.

The Sprint 23 `flash_standard` slide 1 title clipping is now caught by browser layout metric.

Important limitation:

- This sprint detects the issue and turns it into a regression warning.
- It does not yet change generation output.

Recommended next sprint:

- Sprint 25: final post-self-review typography hardening.
- Root target: self-review can reintroduce oversized no-break Japanese titles after `generate_slide_html()` already hardened initial output.
- Candidate fix: run `harden_generated_html_typography()` again after self-review / caption removal / `ensure_text_visible()` and before rendering/saving HTML.

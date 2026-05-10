# Design Quality Sprint 10 — Post-Sprint 9 fixed fixture real regeneration

Date: 2026-05-05
Repo: `/Users/seiyaeto/Antigravity/voiceslide-ai`
Backend: `http://127.0.0.1:8001`

## Purpose

Re-run the fixed fixture real generation after Sprint 7-9 changes.

Checks:

- strategy generation succeeds
- slide HTML generation succeeds
- self-review executes
- `self_review_diagnostic` has useful real-data signal
- `pro` decorative/support text false fail decreases

## Result

The run completed, but provider credit/token constraints still dominated the generation path.

Artifacts:

- `docs/qa/results/2026-05-05_design-quality-sprint-10-post-sprint9-real-regeneration/summary.json`
- `docs/qa/results/2026-05-05_design-quality-sprint-10-post-sprint9-real-regeneration/sanitized_api_result.json`

## Summary

### flash_standard

```text
job_id: 1a3770e3-ec35-469f-a513-c45a4dd6c327
entry_count: 3
total_calls: 3
fallback_count: 3
stage_counts: fallback=3
Strategy generation failed: 1
Slide HTML generation failed: 2
TextSafety fallback: title missing: 0
strategy_count: 0
slide_html_count: 0
self_review_count: 0
self_review_diagnostic_count: 0
Design QA: 2/2 pass
small_text_total: 0
fallback_used_slides: [1, 2]
```

### pro

```text
job_id: 975afdd6-11dc-4be8-b92c-93d53beb73d1
entry_count: 3
total_calls: 3
fallback_count: 3
stage_counts: fallback=3
Strategy generation failed: 1
Slide HTML generation failed: 2
TextSafety fallback: title missing: 0
strategy_count: 0
slide_html_count: 0
self_review_count: 0
self_review_diagnostic_count: 0
Design QA: 2/2 pass
small_text_total: 0
fallback_used_slides: [1, 2]
```

## Interpretation

This run does not prove full title-missing resolution, because both modes still fell back before normal strategy / slide HTML telemetry was recorded.

The important confirmed points are:

- `generation_telemetry_summary.total_calls` and `entry_count` remained compatible.
- `Strategy generation failed` and `Slide HTML generation failed` remained separated in telemetry.
- `TextSafety fallback: title missing` stayed at `0` in this run.
- `pro` quality gate is now `2/2 pass` under fallback output, so Sprint 9's decorative/support text false-fail fix is reflected in the runtime QA path.
- `self_review_diagnostic_count` remained `0`, because the real provider path did not reach a successful self-review title-rewrite boundary.

## Additional redaction fix found during QA

During the rerun, outline/OpenRouter error logging still had a path where provider/user identifiers could be printed before caller-level redaction.

Fixed with TDD:

- Added `tests/test_outline_redaction.py`.
- `services/openrouter_utils.py` now redacts error output before printing.
- `services/outline_generator.py` now redacts Gemini outline / GPT fallback / polish error output before printing.

Synthetic-only test values are used. No real secret values are stored in repo artifacts.

## Verification

```text
./venv/bin/python -m py_compile main.py services/generation_telemetry.py services/design_quality_metrics.py services/ai_utils.py services/ai_slide_generator.py services/transcription.py services/outline_generator.py services/openrouter_utils.py
./venv/bin/python -m pytest tests/test_generation_telemetry.py tests/test_transcription.py tests/test_design_quality_metrics.py tests/test_design_mode.py tests/test_status_telemetry_fields.py tests/test_outline_redaction.py -q
git diff --check

67 passed, 11 warnings
git diff --check: pass
```

## Not done

- commit: not done
- push: not done
- main merge: not done
- production release: not done

## Next step

After OpenRouter/provider credit is restored, run this same fixed fixture again. The remaining target is a run where strategy generation, slide HTML generation, and self-review all succeed, so `self_review_diagnostic` can be evaluated on real title-preservation cases.

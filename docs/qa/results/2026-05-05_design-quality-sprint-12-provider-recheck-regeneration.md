# Design Quality Sprint 12 — Provider recheck real regeneration

Date: 2026-05-05
Repo: `/Users/seiyaeto/Antigravity/voiceslide-ai`

## Purpose

Rerun the fixed fixture real generation after Sprint 11 to check whether the provider path is healthy enough to reach:

- strategy generation
- slide HTML generation
- self-review
- `self_review_diagnostic` evaluation

## Setup

- Origin: `http://127.0.0.1:3010/`
- Backend: `http://127.0.0.1:8001`
- Fixed fixture: `docs/qa/fixtures/short_voislide_quality_check_32s.mp3`
- Visible Chrome/CDP: port `9223`
- API key/model state: presence-only check passed for OpenAI, Gemini, OpenRouter, and model settings.

No key values were printed or stored.

## Result

The run completed for both modes, but provider credit/token constraints still dominated the generation path.

### flash_standard

```text
job_id: 748c1a19-26c8-4bf7-ba55-5fffd1fde226
entry_count: 3
total_calls: 3
fallback_count: 3

fallback:Strategy generation failed: 1
fallback:Slide HTML generation failed: 2
TextSafety fallback: title missing: 0

strategy_count: 0
slide_html_count: 0
self_review_count: 0
self_review_diagnostic_count: 0

Design QA: 2/2 pass
small_text_total: 0
```

### pro

```text
job_id: e6a171c7-a723-448f-bc45-98d636c720e5
entry_count: 3
total_calls: 3
fallback_count: 3

fallback:Strategy generation failed: 1
fallback:Slide HTML generation failed: 2
TextSafety fallback: title missing: 0

strategy_count: 0
slide_html_count: 0
self_review_count: 0
self_review_diagnostic_count: 0

Design QA: 2/2 pass
small_text_total: 0
```

## Interpretation

This is still an upstream-fallback dominated run.

`TextSafety fallback: title missing=0` is not proof of complete resolution because successful strategy/slide HTML/self-review paths were not reached.

The useful confirmation is:

- browser-stored key presence exists on the test origin;
- upload/transcription/outline/batch pipeline still completes;
- redaction is working in provider error logs/artifacts;
- fallback outputs remain Design QA pass in both modes;
- `total_calls` / `entry_count` compatibility remains intact.

## Artifacts

```text
docs/qa/results/2026-05-05_design-quality-sprint-12-provider-recheck-regeneration/sanitized_api_result.json
docs/qa/results/2026-05-05_design-quality-sprint-12-provider-recheck-regeneration/summary.json
```

## Verification

```text
./venv/bin/python -m py_compile main.py services/generation_telemetry.py services/design_quality_metrics.py services/ai_utils.py services/ai_slide_generator.py services/transcription.py services/outline_generator.py services/openrouter_utils.py services/slide_design_ai.py services/slide_generator.py services/image_generator.py
./venv/bin/python -m pytest tests/test_generation_telemetry.py tests/test_transcription.py tests/test_design_quality_metrics.py tests/test_design_mode.py tests/test_status_telemetry_fields.py tests/test_outline_redaction.py tests/test_legacy_ai_redaction.py -q
git diff --check

71 passed, 11 warnings
git diff --check: pass
```

## Not done

- commit: not done
- push: not done
- main merge: not done
- production release: not done

## Next step

Provider/OpenRouter credit must be topped up or the max token budget/model choice must be adjusted. Then rerun the same fixed fixture and check whether strategy/slide HTML/self-review success paths are reached.

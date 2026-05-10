# VoiSlide Design Quality Sprint 7 — Self-review diagnostic regeneration QA

Date: 2026-05-05
Branch: develop

## Purpose

Verify the newly added `self_review_diagnostic` telemetry with the fixed fixture regeneration flow.

The diagnostic is intended to distinguish these cases in later runs:

- self-review removed or rewrote the original title
- title was already missing before self-review
- `_title_present()` is too strict

The diagnostic stores booleans and a stable decision string only. It does not store slide title text.

## Result summary

The fixed fixture rerun completed for both modes, but this run was not a clean self-review diagnostic validation.

Both modes hit upstream generation fallback before self-review could produce useful diagnostic telemetry.

### flash_standard

- job_id: `f4432c0f-775d-4613-a7eb-8eef406d1e23`
- `entry_count`: 3
- `total_calls`: 3
- `fallback_count`: 3
- `stage_counts`: `fallback=3`
- `fallback_stage_counts`:
  - `fallback:Strategy generation failed`: 1
  - `fallback:Slide HTML generation failed`: 2
- `self_review_diagnostic_count`: 0
- `TextSafety fallback: title missing`: 0
- Design QA:
  - slide 1: pass, fallback_used=true
  - slide 2: pass, fallback_used=true

### pro

- job_id: `049026aa-1afb-4600-ae9d-0c6389994dde`
- `entry_count`: 3
- `total_calls`: 3
- `fallback_count`: 3
- `stage_counts`: `fallback=3`
- `fallback_stage_counts`:
  - `fallback:Strategy generation failed`: 1
  - `fallback:Slide HTML generation failed`: 2
- `self_review_diagnostic_count`: 0
- `TextSafety fallback: title missing`: 0
- Design QA:
  - slide 1: pass, fallback_used=true
  - slide 2: fail, fallback_used=true, small_text_count=1

## Interpretation

This run confirms the backend and artifact pipeline work with the Sprint 7 diagnostic code, but it does not prove the remaining title-missing path.

Reason:

- Strategy generation and slide HTML generation failed before normal self-review/title-safety behavior could be observed.
- Therefore `self_review_diagnostic_count=0` is expected for this run.
- `TextSafety fallback: title missing=0` here does not mean the title-missing issue is fully resolved. The run was dominated by earlier fallback paths.

## Artifacts

- `docs/qa/results/2026-05-05_design-quality-sprint-7-self-review-diagnostic-regeneration/sanitized_api_result.json`
- `docs/qa/results/2026-05-05_design-quality-sprint-7-self-review-diagnostic-regeneration/summary.json`

## Secret handling

- API keys were not printed or saved.
- Provider/user ID style strings are redacted in the saved artifact path.
- The diagnostic telemetry does not store title text.

## Next step

Re-run this diagnostic fixture when upstream provider quota/credit is healthy, or force a controlled mocked/integration self-review path that reaches the self-review boundary. The useful target is a run where `slide_html` succeeds and `self_review` executes, so `self_review_diagnostic` can explain whether a title was lost there.

# VoiSlide Design Quality Sprint 8 — Upstream fallback redaction and self-review boundary check

Date: 2026-05-05
Branch: develop

## Purpose

Continue after Sprint 7 fixed fixture regeneration.

Sprint 7 confirmed the artifact pipeline, but both `flash_standard` and `pro` hit upstream fallback before a useful self-review diagnostic path could be observed.

Sprint 8 therefore focused on two things:

1. Identify and harden the upstream fallback/error path.
2. Verify the self-review boundary with a controlled mocked integration path instead of relying on provider availability.

## Findings from Sprint 7 artifacts

Sprint 7 fixed fixture regeneration produced fallback before self-review:

- `flash_standard`
  - `fallback_count`: 3
  - `Strategy generation failed`: 1
  - `Slide HTML generation failed`: 2
  - `self_review_diagnostic_count`: 0
  - `TextSafety fallback: title missing`: 0
- `pro`
  - `fallback_count`: 3
  - `Strategy generation failed`: 1
  - `Slide HTML generation failed`: 2
  - `self_review_diagnostic_count`: 0
  - `TextSafety fallback: title missing`: 0

Interpretation:

- `title missing=0` in this run is not proof that the title-missing path is gone.
- The run did not reliably reach normal slide HTML + self-review behavior.
- The next reliable check is a controlled self-review boundary test.

## Changes

### 1. Redacted strategy generation error output

`generate_design_strategy()` now redacts exception text before printing or storing telemetry warning text.

This keeps provider/user IDs and key-like fragments out of stdout and telemetry.

### 2. Redacted self-review error output

`self_review_slide()` now redacts exception text before printing self-review errors.

This protects the exact boundary being inspected.

### 3. Redacted Gemini model discovery key logging

`get_available_gemini_model()` no longer prints API key prefix/suffix fragments.

It now logs the key through `redact_secrets()`.

### 4. Test compatibility cleanup

`tests/test_transcription.py` had async tests marked with `pytest.mark.asyncio`, but the current backend test environment does not have a suitable async pytest plugin active.

Those tests were converted to synchronous tests using `asyncio.run()` where needed. This allows the whole touched test file to run cleanly.

## TDD / regression checks added

Added tests covering:

- self-review exception stdout redaction
- strategy generation exception stdout + telemetry warning redaction
- Gemini API key fragment redaction in model discovery logs
- existing self-review title rewrite rejection path still records one `self_review_diagnostic` entry and does not store title text

The self-review boundary is now covered by a mocked integration path:

- `safe_gemini_generate()` returns rewritten HTML that removes the original title
- `self_review_slide()` rejects the rewrite
- original HTML is kept
- `self_review_diagnostic` telemetry is recorded once
- diagnostic warning contains booleans/decision only, not the title text

## Validation

Command run from `backend/`:

```bash
./venv/bin/python -m py_compile main.py services/generation_telemetry.py services/design_quality_metrics.py services/ai_utils.py services/ai_slide_generator.py services/transcription.py
./venv/bin/python -m pytest tests/test_generation_telemetry.py tests/test_transcription.py tests/test_design_quality_metrics.py tests/test_design_mode.py tests/test_status_telemetry_fields.py -q
git diff --check
```

Result:

```text
61 passed, 11 warnings
git diff --check: pass
```

Warnings are existing dependency/FastAPI deprecation warnings.

## Secret handling

- No real key values are stored in this report.
- Synthetic `user_...` and key-like test strings are used only as regression fixtures.
- Runtime stdout and telemetry warnings now redact these fragments in the touched paths.

## Remaining work

A provider-healthy fixed fixture rerun is still useful.

The ideal real-generation target remains:

- strategy generation succeeds
- slide HTML generation succeeds
- self-review executes
- `self_review_diagnostic` either stays 0 for safe output or records title-loss decisions if the model rewrites/removes the title

Separate next product-quality topic:

- `pro` still tends to fail quality gate on small decorative/footer/supplemental text. This should be handled separately from title-safety fallback.

## Commit / release status

No commit, push, main merge, or production release was performed.

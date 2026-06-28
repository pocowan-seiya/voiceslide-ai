# Design Quality Sprint 11 — Legacy AI redaction hardening

Date: 2026-05-05
Repo: `/Users/seiyaeto/Antigravity/voiceslide-ai`

## Purpose

After Sprint 10, provider credit/token constraints still blocked a full successful real-generation path.

The next safe step was to harden remaining AI-related stdout redaction paths that can be exercised without provider access.

## Discovery

A scan of `backend/services` found additional AI/provider error print paths outside the Sprint 8-10 primary flow:

- `services/slide_design_ai.py`
- `services/slide_generator.py`
- `services/image_generator.py`

These are older or auxiliary AI paths, but they can still print exception strings. Provider error payloads can include credential-like IDs, so these paths should also use centralized redaction.

## TDD

Added:

```text
backend/tests/test_legacy_ai_redaction.py
```

RED confirmed first:

```text
4 failed
```

The failing cases covered:

- `slide_design_ai.analyze_slide_design()` model fallback errors
- `slide_design_ai.generate_background_image()` generation errors
- `slide_generator.generate_outline()` Gemini fallback errors
- `image_generator.generate_slide_illustration()` generation errors

All tests use synthetic provider/user IDs only.

## Implementation

Updated stdout error logging to use `redact_secrets(str(e))`:

- `backend/services/slide_design_ai.py`
- `backend/services/slide_generator.py`
- `backend/services/image_generator.py`

No API key values were read or stored.

## Verification

```text
./venv/bin/python -m py_compile main.py services/generation_telemetry.py services/design_quality_metrics.py services/ai_utils.py services/ai_slide_generator.py services/transcription.py services/outline_generator.py services/openrouter_utils.py services/slide_design_ai.py services/slide_generator.py services/image_generator.py
./venv/bin/python -m pytest tests/test_generation_telemetry.py tests/test_transcription.py tests/test_design_quality_metrics.py tests/test_design_mode.py tests/test_status_telemetry_fields.py tests/test_outline_redaction.py tests/test_legacy_ai_redaction.py -q
git diff --check

71 passed, 11 warnings
git diff --check: pass
```

Warnings are existing dependency/FastAPI deprecation warnings.

## Not done

- commit: not done
- push: not done
- main merge: not done
- production release: not done

## Next step

When provider credit is restored, rerun the fixed fixture real generation again and check whether strategy, slide HTML, and self-review all succeed.

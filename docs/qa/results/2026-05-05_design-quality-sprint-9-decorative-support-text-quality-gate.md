# VoiSlide Design Quality Sprint 9 — Decorative/support text quality gate

Date: 2026-05-05
Branch: develop

## Purpose

Continue after Sprint 8 by separating the remaining `pro` quality-gate issue from title-safety fallback.

The observed issue was not that `pro` output had unreadable body copy. The metric was failing slides because small decorative/support text, such as section labels, captions, footer markers, or supplemental labels, was counted as normal body text.

## Decision

Small decorative/support text should not fail an otherwise readable slide.

The metric should still fail normal body copy at 20px or below.

This keeps the quality gate aligned with the visual review from earlier runs:

- readable title/body text remains strict
- slide chrome and decorative labels are excluded from body-copy failure logic
- `pro` can keep premium small supporting labels without being marked as a body readability failure

## Changes

### 1. Expanded non-content marker filtering

`backend/services/design_quality_metrics.py` now treats these class/id parts as non-content for quality-gate extraction:

- `decorative`
- `footer`
- `caption`
- `supplemental`
- `section-label`
- `eyebrow`
- `kicker`
- `badge`
- `meta`

Existing slide chrome exclusions remain:

- `slide-number`
- `page-number`

Raw `analyze_font_sizes()` behavior is unchanged. It still extracts all sizes for diagnostics.

### 2. Fallback section label markup

`generate_fallback_html()` now marks the pro diagonal fallback section chip as:

```html
class="section-label"
```

This prevents the deterministic fallback's 16px `SECTION 02` label from failing the quality gate.

## TDD checks added

Added regression tests for:

1. CSS decorative/footer support text at 16px/18px does not fail a readable slide.
2. Inline `section-label` / `caption` text at 16px/18px does not fail a readable slide.
3. `pro` fallback slide with a 16px section label passes when title/body text is readable.

The RED run failed all 3 tests before implementation:

```text
3 failed
```

The GREEN run passed all 3 after implementation:

```text
3 passed
```

## Validation

Command run from `backend/`:

```bash
./venv/bin/python -m py_compile main.py services/generation_telemetry.py services/design_quality_metrics.py services/ai_utils.py services/ai_slide_generator.py services/transcription.py
./venv/bin/python -m pytest tests/test_generation_telemetry.py tests/test_transcription.py tests/test_design_quality_metrics.py tests/test_design_mode.py tests/test_status_telemetry_fields.py -q
git diff --check
```

Result:

```text
64 passed, 11 warnings
git diff --check: pass
```

Warnings are existing dependency/FastAPI deprecation warnings.

## What this does not change

- Normal body copy at 20px or below still fails.
- Raw font-size extraction still includes decorative sizes.
- Title-safety fallback and `self_review_diagnostic` behavior are unchanged.
- No provider-backed real generation was rerun in this sprint.

## Next step

Run provider-backed fixed fixture regeneration when provider quota/credit is healthy.

The next real-generation check should verify:

- strategy generation succeeds
- slide HTML generation succeeds
- self-review executes
- `self_review_diagnostic` remains meaningful
- `pro` decorative/support text no longer creates false `quality_gate=fail` when readable body text is present

## Commit / release status

No commit, push, main merge, or production release was performed.

# 2026-05-15 Pro OpenRouter final no-fallback pass

## Summary

Fixed 32-second VoiSlide fixture was generated through the native Pro/OpenRouter path without fallback.

- Job ID: `139831ee-2474-4058-bab4-61a814ae219a`
- Elapsed: `164218 ms`
- `fallback_count`: `0`
- `total_calls`: `5`
- `total_input_tokens`: `17874`
- `total_output_tokens`: `13879`

## Design QA metrics

| Slide | quality_gate | fallback_used | text_clipping_detected | small_text_count | min_font_size_px | main occupancy |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | pass | false | false | 0 | 28 | 1 |
| 2 | pass | false | false | 0 | 34 | 1 |

## Visual QA

Contact sheet review:

- Slide 1: Japanese title is not clipped. Body/step text is readable. The dark navy and gold design is consistent.
- Slide 2: Japanese title is not clipped. Body text is readable. The centered spacing is large but acceptable for a closing/key-message slide.
- No obvious cheap-looking layout collapse was found.
- Very small text appears limited to decorative English labels/footer-style elements, not core body copy.

## Artifacts

```text
docs/qa/results/2026-05-15_pro-openrouter-final-no-fallback-pass/qa_result.json
docs/qa/results/2026-05-15_pro-openrouter-final-no-fallback-pass/slide_data.json
docs/qa/results/2026-05-15_pro-openrouter-final-no-fallback-pass/artifact_hashes.json
docs/qa/results/2026-05-15_pro-openrouter-final-no-fallback-pass/contact_sheet_final_no_fallback_pass_2026-05-15.png
docs/qa/results/2026-05-15_pro-openrouter-final-no-fallback-pass/slide_001.png
docs/qa/results/2026-05-15_pro-openrouter-final-no-fallback-pass/slide_002.png
```

## Notes

This validates the short fixture only. Longer 1-3 minute and 5+ minute flows, video generation, save/restore, and post-generation edit friction still need separate QA before considering production release.

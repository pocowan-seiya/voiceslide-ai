# 2026-05-04 telemetry total_calls regression QA

対象: VoiSlide Movie Sprint 1〜2 telemetry / status APIs

## Summary

`generation_telemetry_summary.total_calls` の追加後、`entry_count` との一致と status API 露出を回帰テストで確認した。

## Checked fields

- `/api/status/{job_id}`
  - `generation_telemetry_summary.entry_count`
  - `generation_telemetry_summary.total_calls`
  - `design_quality_metrics`
- `/api/batch-status/{job_id}`
  - `generation_telemetry_summary.entry_count`
  - `generation_telemetry_summary.total_calls`
  - `design_quality_metrics`

## Result

```text
40 passed, 11 warnings in 0.96s
```

Warnings are existing dependency/framework deprecations.

## Notes

- `total_calls` is an alias of `entry_count`.
- `entry_count` remains for backward compatibility.
- Live fixed-fixture AI generation is blocked in this Hermes environment because AI API keys are not present. Key values were not read or printed.

## Next

Run fixed-fixture live generation in the visible shared Chrome/CDP environment where AI keys are configured, then compare `flash_standard` and `pro` telemetry/metrics.

# VoiSlide Manual Edit Friction Recorder — Phase 1

Date: 2026-05-14
Branch target: `develop`

## Purpose

Connect machine-side generation quality with human-side editing friction after AI slide generation.

```txt
design_quality_metrics
×
generation_telemetry_summary
×
manual_edit_friction_summary
```

This lets Product Ops see not only whether a slide passed the Design QA metric, but also where users stop, zoom, edit, retry, or save before video generation.

## Phase 1 scope

Phase 1 records privacy-safe interaction metadata in the post-generation editor.

It does **not** record edited text, transcript text, API keys, image contents, or provider payloads.

### Events

Initial event types:

- `slide_selected`
- `zoom_opened`
- `direct_editor_opened`
- `direct_editor_closed`
- `direct_editor_text_focused`
- `direct_editor_text_input`
- `direct_editor_save_started`
- `direct_editor_save_succeeded`
- `direct_editor_save_failed`
- `ai_feedback_started`
- `ai_feedback_succeeded`
- `ai_feedback_failed`
- `undo_clicked`
- `undo_succeeded`
- `undo_failed`
- `video_generate_clicked`

### Stored fields

Each event stores:

```json
{
  "event_type": "direct_editor_text_input",
  "slide_number": 2,
  "workflow_mode": "full-ai",
  "design_mode": "pro",
  "elapsed_ms": 1234,
  "source": "iframe",
  "details": {
    "target_tag": "H1",
    "target_class_hint": "main-title",
    "text_length_before": 12,
    "text_length_after": 18
  },
  "quality_snapshot": {
    "slide_number": 2,
    "quality_gate": "warn",
    "fallback_used": false,
    "text_clipping_detected": true,
    "small_text_count": 1,
    "min_font_size_px": 24,
    "main_element_occupancy_ratio": 0.28,
    "warnings_count": 2
  },
  "created_at": "2026-05-14T17:00:00"
}
```

### Summary shape

The backend keeps a bounded per-job event window and exposes:

```json
{
  "event_count": 4,
  "by_type": {
    "slide_selected": 1,
    "direct_editor_opened": 1,
    "direct_editor_text_input": 1,
    "direct_editor_save_succeeded": 1
  },
  "by_slide": {
    "2": {
      "event_count": 4,
      "event_types": {
        "slide_selected": 1,
        "direct_editor_opened": 1,
        "direct_editor_text_input": 1,
        "direct_editor_save_succeeded": 1
      },
      "quality_snapshot": {
        "quality_gate": "warn",
        "text_clipping_detected": true
      }
    }
  },
  "first_at": "...",
  "last_at": "..."
}
```

## API

### POST `/api/manual-edit-friction/{job_id}`

Records one privacy-safe event.

Validation:

- unknown `event_type` returns `400`
- unknown `job_id` returns `404`
- `details` is allowlisted
- `quality_snapshot` is allowlisted
- per-job retained events are capped at 500

### GET `/api/manual-edit-friction/{job_id}`

Returns retained events and summary for QA/Product Ops inspection.

### Existing status APIs

These now expose `manual_edit_friction_summary`:

- `GET /api/status/{job_id}`
- `GET /api/batch-status/{job_id}`

## Frontend instrumentation points

Phase 1 records events from:

1. slide selection and zoom
2. direct editor open/close
3. contenteditable focus/input inside the iframe
4. direct HTML save start/success/failure
5. AI feedback request start/success/failure
6. video generation click

The iframe sends only metadata through `postMessage`:

- element tag
- class hint
- text length before/after

No text content is sent.

## Product Ops reading

Useful first questions:

1. Which slide numbers receive the most edits?
2. Do `quality_gate=warn/fail` slides receive more direct edits?
3. Are users using direct edit or AI feedback for correction?
4. Do users save successfully after editing, or abandon before video generation?
5. Are fallback slides edited more than non-fallback slides?

## Not in Phase 1

- Database persistence across process restarts
- User-facing dashboard
- Admin export UI
- Session replay
- Capturing exact text diffs
- Production/main deploy

## Next step

If Phase 1 data looks useful, Phase 2 should persist summaries to Supabase per project/job and add an internal QA view that joins:

```txt
slide_number
quality_gate
fallback_used
text_clipping_detected
manual_edit_event_count
save_success_count
video_generate_clicked
```

## Colorful AI波及

The same pattern can return to Colorful AI as:

```txt
AI生成品質スコア
×
手動編集イベント数
×
保存・公開までの到達
```

Colorful AIでは、生成後エディタの「ダブルクリック編集」「セクション順入れ替え」「保存/公開前の離脱」に接続すると、AI生成品質を主観だけでなくユーザー行動で改善できます。

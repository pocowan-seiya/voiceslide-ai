"""
Sprint 1 — Generation telemetry tests (TDD).

Verifies that:
- TelemetryEntry can be created with all required fields.
- Token/cost fields can be null.
- Fallback events are recorded.
- API-key-like strings are redacted.
- Telemetry collector accumulates entries.
"""

from __future__ import annotations

import asyncio

import pytest

from services import ai_slide_generator
from services.generation_telemetry import (
    TelemetryEntry,
    TelemetryCollector,
    reset_current_collector,
    redact_secrets,
    set_current_collector,
)


# ---------------------------------------------------------------------------
# TelemetryEntry creation
# ---------------------------------------------------------------------------


class TestTelemetryEntry:
    def test_create_with_all_fields(self):
        entry = TelemetryEntry(
            job_id="job-123",
            design_mode="pro",
            stage="strategy",
            slide_number=None,
            requested_model="anthropic/claude-opus-4-7",
            actual_model="anthropic/claude-opus-4-7",
            provider="openrouter",
            input_tokens=1500,
            output_tokens=800,
            estimated_cost_usd=0.045,
            duration_ms=2340,
            fallback_reason=None,
            warning=None,
        )
        assert entry.job_id == "job-123"
        assert entry.design_mode == "pro"
        assert entry.stage == "strategy"
        assert entry.requested_model == "anthropic/claude-opus-4-7"
        assert entry.actual_model == "anthropic/claude-opus-4-7"
        assert entry.provider == "openrouter"
        assert entry.input_tokens == 1500
        assert entry.output_tokens == 800
        assert entry.estimated_cost_usd == 0.045
        assert entry.duration_ms == 2340
        assert entry.fallback_reason is None
        assert entry.warning is None

    def test_token_and_cost_can_be_null(self):
        entry = TelemetryEntry(
            job_id="job-456",
            design_mode="flash_standard",
            stage="slide_html",
            slide_number=2,
            requested_model="google/gemini-3-flash-preview",
            actual_model="google/gemini-3-flash-preview",
            provider="gemini",
            input_tokens=None,
            output_tokens=None,
            estimated_cost_usd=None,
            duration_ms=1200,
        )
        assert entry.input_tokens is None
        assert entry.output_tokens is None
        assert entry.estimated_cost_usd is None

    def test_fallback_event_is_recorded(self):
        entry = TelemetryEntry(
            job_id="job-789",
            design_mode="pro",
            stage="strategy",
            slide_number=None,
            requested_model="anthropic/claude-opus-4-7",
            actual_model="google/gemini-2.5-flash",
            provider="openrouter",
            input_tokens=None,
            output_tokens=None,
            estimated_cost_usd=None,
            duration_ms=500,
            fallback_reason="Strategy generation failed: JSON parse error",
            warning="Fell back to deterministic strategy",
        )
        assert entry.fallback_reason is not None
        assert "JSON parse error" in entry.fallback_reason
        assert entry.requested_model != entry.actual_model

    def test_to_dict_returns_all_fields(self):
        entry = TelemetryEntry(
            job_id="job-dict",
            design_mode="pro",
            stage="slide_html",
            slide_number=1,
            requested_model="anthropic/claude-opus-4-7",
            actual_model="anthropic/claude-opus-4-7",
            provider="openrouter",
            input_tokens=100,
            output_tokens=200,
            estimated_cost_usd=0.01,
            duration_ms=999,
        )
        d = entry.to_dict()
        assert isinstance(d, dict)
        required_keys = {
            "job_id", "design_mode", "stage", "slide_number",
            "requested_model", "actual_model", "provider",
            "input_tokens", "output_tokens", "estimated_cost_usd",
            "duration_ms", "fallback_reason", "warning",
        }
        assert required_keys.issubset(d.keys())


# ---------------------------------------------------------------------------
# TelemetryCollector
# ---------------------------------------------------------------------------


class TestTelemetryCollector:
    def test_collect_entries(self):
        collector = TelemetryCollector(job_id="job-collect")
        collector.record(
            design_mode="pro",
            stage="strategy",
            slide_number=None,
            requested_model="anthropic/claude-opus-4-7",
            actual_model="anthropic/claude-opus-4-7",
            provider="openrouter",
            duration_ms=1000,
        )
        collector.record(
            design_mode="pro",
            stage="slide_html",
            slide_number=1,
            requested_model="anthropic/claude-opus-4-7",
            actual_model="anthropic/claude-opus-4-7",
            provider="openrouter",
            duration_ms=2000,
        )
        entries = collector.entries
        assert len(entries) == 2
        assert entries[0].stage == "strategy"
        assert entries[1].stage == "slide_html"
        assert entries[1].slide_number == 1

    def test_to_list_returns_dicts(self):
        collector = TelemetryCollector(job_id="job-list")
        collector.record(
            design_mode="flash_standard",
            stage="fallback",
            slide_number=2,
            requested_model="google/gemini-3-flash-preview",
            actual_model="google/gemini-3-flash-preview",
            provider="gemini",
            duration_ms=300,
            fallback_reason="TextSafety fallback",
        )
        result = collector.to_list()
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["fallback_reason"] == "TextSafety fallback"

    def test_summary_includes_total_duration(self):
        collector = TelemetryCollector(job_id="job-summary")
        collector.record(
            design_mode="pro",
            stage="strategy",
            slide_number=None,
            requested_model="m1",
            actual_model="m1",
            provider="openrouter",
            duration_ms=1000,
        )
        collector.record(
            design_mode="pro",
            stage="slide_html",
            slide_number=1,
            requested_model="m1",
            actual_model="m1",
            provider="openrouter",
            duration_ms=2000,
        )
        summary = collector.summary()
        assert summary["total_duration_ms"] == 3000
        assert summary["entry_count"] == 2
        assert summary["total_calls"] == 2
        assert summary["total_calls"] == summary["entry_count"]
        assert summary["fallback_count"] == 0

    def test_summary_total_calls_matches_entry_count_for_empty_collector(self):
        collector = TelemetryCollector(job_id="job-empty")

        summary = collector.summary()

        assert summary["entry_count"] == 0
        assert summary["total_calls"] == 0
        assert summary["total_calls"] == summary["entry_count"]

    def test_summary_counts_fallbacks(self):
        collector = TelemetryCollector(job_id="job-fb")
        collector.record(
            design_mode="pro",
            stage="strategy",
            slide_number=None,
            requested_model="m1",
            actual_model="m2",
            provider="openrouter",
            duration_ms=500,
            fallback_reason="Strategy generation failed",
        )
        collector.record(
            design_mode="pro",
            stage="fallback",
            slide_number=2,
            requested_model="m1",
            actual_model="m1",
            provider="openrouter",
            duration_ms=200,
            fallback_reason="TextSafety fallback",
        )
        summary = collector.summary()
        assert summary["fallback_count"] == 2


class TestSlideFallbackTelemetry:
    def test_slide_html_exception_fallback_records_telemetry(self, monkeypatch):
        async def raise_from_model(*args, **kwargs):
            raise RuntimeError("provider returned malformed HTML")

        monkeypatch.setattr(ai_slide_generator, "safe_gemini_generate", raise_from_model)
        collector = TelemetryCollector(job_id="job-slide-fallback")
        token = set_current_collector(collector)
        try:
            html = asyncio.run(
                ai_slide_generator.generate_slide_html(
                    slide={"slide_copy": {"headline": "Telemetry", "bullet_points": ["fallback"]}},
                    slide_number=1,
                    total_slides=1,
                    strategy={"_design_mode": "pro", "design_style": {}},
                    job_id="job-slide-fallback",
                    gemini_key="dummy-key",
                )
            )
        finally:
            reset_current_collector(token)

        assert 'data-voislide-fallback="true"' in html
        assert collector.summary()["fallback_count"] == 1
        entry = collector.entries[0]
        assert entry.design_mode == "pro"
        assert entry.stage == "fallback"
        assert entry.slide_number == 1
        assert entry.fallback_reason == "Slide HTML generation failed"

    def test_slide_html_exception_redacts_secret_like_warning_and_stdout(self, monkeypatch, capsys):
        async def raise_with_secret_like_message(*args, **kwargs):
            raise RuntimeError("provider rejected key sk-test1234567890abcdef")

        monkeypatch.setattr(ai_slide_generator, "safe_gemini_generate", raise_with_secret_like_message)
        collector = TelemetryCollector(job_id="job-slide-fallback-redact")
        token = set_current_collector(collector)
        try:
            html = asyncio.run(
                ai_slide_generator.generate_slide_html(
                    slide={"slide_copy": {"headline": "Telemetry", "bullet_points": ["fallback"]}},
                    slide_number=1,
                    total_slides=1,
                    strategy={"_design_mode": "pro", "design_style": {}},
                    job_id="job-slide-fallback-redact",
                    gemini_key="dummy-key",
                )
            )
        finally:
            reset_current_collector(token)

        captured = capsys.readouterr()
        entry = collector.entries[0]
        assert 'data-voislide-fallback="true"' in html
        assert "1234567890abcdef" not in entry.warning
        assert "1234567890abcdef" not in captured.out
        assert "[REDACTED]" in entry.warning
        assert "[REDACTED]" in captured.out

    def test_text_safety_fallback_records_slide_level_telemetry(self):
        collector = TelemetryCollector(job_id="job-text-safety-fallback")
        token = set_current_collector(collector)
        try:
            html = ai_slide_generator.ensure_text_visible(
                html="<html><body></body></html>",
                slide={"slide_copy": {"headline": "Visible title", "bullet_points": ["fallback"]}},
                slide_number=2,
                total_slides=3,
                strategy={"_design_mode": "pro", "design_style": {}},
            )
        finally:
            reset_current_collector(token)

        assert 'data-voislide-fallback="true"' in html
        assert collector.summary()["fallback_count"] == 1
        entry = collector.entries[0]
        assert entry.design_mode == "pro"
        assert entry.stage == "fallback"
        assert entry.slide_number == 2
        assert entry.fallback_reason == "TextSafety fallback: no visible text"
        assert entry.provider == "local"
        assert entry.requested_model == "deterministic-text-safety"
        assert entry.actual_model == "deterministic-text-safety"

    def test_text_safety_title_missing_fallback_redacts_warning_and_stdout(self, capsys):
        secret_like_title = "sk-1234567890abcdef1234567890abcdef should not leak"
        collector = TelemetryCollector(job_id="job-text-safety-title-missing")
        token = set_current_collector(collector)
        try:
            html = ai_slide_generator.ensure_text_visible(
                html="<html><body>Completely different readable content</body></html>",
                slide={"slide_copy": {"headline": secret_like_title, "bullet_points": ["fallback"]}},
                slide_number=1,
                total_slides=2,
                strategy={"_design_mode": "flash_standard", "design_style": {}},
            )
        finally:
            reset_current_collector(token)

        captured = capsys.readouterr()
        entry = collector.entries[0]
        assert 'data-voislide-fallback="true"' in html
        assert entry.fallback_reason == "TextSafety fallback: title missing"
        assert "1234567890abcdef" not in entry.warning
        assert "1234567890abcdef" not in captured.out
        assert "[REDACTED]" in entry.warning
        assert "[REDACTED]" in captured.out

    def test_self_review_rejects_title_rewrite(self, monkeypatch):
        original_title = "日本語が読みやすく、自然に繋がること"
        original_html = f"""
        <!DOCTYPE html>
        <html><body>
          <h1>{original_title}</h1>
          <p>音声からスライド動画を作る時に、読みやすさを保ちながら品質を確認します。</p>
        </body></html>
        """
        rewritten_html = """<!DOCTYPE html>
<html><body>
  <h1>読みやすい日本語で自然につなぐ</h1>
  <p>音声からスライド動画を作る時に、読みやすさを保ちながら品質を確認します。</p>
</body></html>
"""

        async def fake_generate(*args, **kwargs):
            return rewritten_html

        monkeypatch.setattr(ai_slide_generator, "safe_gemini_generate", fake_generate)
        collector = TelemetryCollector(job_id="job-self-review-title-diagnostic")
        token = set_current_collector(collector)
        try:
            result = asyncio.run(ai_slide_generator.self_review_slide(
                html=original_html,
                strategy={"_design_mode": "flash_standard", "design_style": {}, "content_analysis": {}},
                gemini_key="dummy-key",
            ))
        finally:
            reset_current_collector(token)

        assert original_title in result
        assert "読みやすい日本語で自然につなぐ" not in result
        diagnostic_entries = [entry for entry in collector.entries if entry.stage == "self_review_diagnostic"]
        assert len(diagnostic_entries) == 1
        diagnostic = diagnostic_entries[0]
        assert diagnostic.provider == "local"
        assert diagnostic.warning == "SelfReview title diagnostic: original_title_present=true improved_title_present=false decision=keep_original"
        assert original_title not in diagnostic.warning

    def test_self_review_title_diagnostic_snapshot_redacts_and_records_slide_number(self, monkeypatch, tmp_path):
        original_title = "日本語が読みやすく、自然に繋がること"
        original_html = f"""<!DOCTYPE html><html><body>
        <h1>{original_title}</h1>
        <p>本文 key=sk-or-v1-SYNTHETIC1234567890abcdef</p>
        </body></html>"""
        rewritten_html = """<!DOCTYPE html><html><body>
        <h1>読みやすい日本語で自然につなぐ</h1>
        <p>本文 key=sk-or-v1-SYNTHETIC1234567890abcdef</p>
        </body></html>"""

        async def fake_generate(*args, **kwargs):
            return rewritten_html

        monkeypatch.setattr(ai_slide_generator, "safe_gemini_generate", fake_generate)
        save_snapshot = ai_slide_generator.save_self_review_title_diagnostic_snapshot
        monkeypatch.setattr(ai_slide_generator, "save_self_review_title_diagnostic_snapshot", lambda *args, **kwargs: save_snapshot(
            *args,
            **kwargs,
            job_id="job-self-review-title-diagnostic",
            output_dir=str(tmp_path),
        ))
        collector = TelemetryCollector(job_id="job-self-review-title-diagnostic")
        token = set_current_collector(collector)
        try:
            result = asyncio.run(ai_slide_generator.self_review_slide(
                html=original_html,
                strategy={"_design_mode": "flash_standard", "design_style": {}, "content_analysis": {}},
                gemini_key="dummy-key",
                slide_number=2,
            ))
        finally:
            reset_current_collector(token)

        assert original_title in result
        diagnostic_entries = [entry for entry in collector.entries if entry.stage == "self_review_diagnostic"]
        assert len(diagnostic_entries) == 1
        assert diagnostic_entries[0].slide_number == 2
        diagnostics_dir = tmp_path / "job-self-review-title-diagnostic_slides" / "self_review_diagnostics"
        original_path = diagnostics_dir / "slide_002_flash_standard_title_rewrite_original.html"
        improved_path = diagnostics_dir / "slide_002_flash_standard_title_rewrite_improved.html"
        diff_path = diagnostics_dir / "slide_002_flash_standard_title_rewrite_diff.patch"
        assert original_path.exists()
        assert improved_path.exists()
        assert diff_path.exists()
        assert "SYNTHETIC1234567890abcdef" not in original_path.read_text(encoding="utf-8")
        assert "SYNTHETIC1234567890abcdef" not in improved_path.read_text(encoding="utf-8")
        assert "SYNTHETIC1234567890abcdef" not in diff_path.read_text(encoding="utf-8")
        assert "[REDACTED]" in diff_path.read_text(encoding="utf-8")

    def test_self_review_error_redacts_stdout(self, monkeypatch, capsys):
        original_html = "<!DOCTYPE html><html><body><h1>安全なタイトル</h1></body></html>"

        async def fake_generate(*args, **kwargs):
            raise RuntimeError("OpenRouter user_id=user_SYNTHETIC1234567890abcdef key=sk-or-v1-1234567890abcdef")

        monkeypatch.setattr(ai_slide_generator, "safe_gemini_generate", fake_generate)

        result = asyncio.run(ai_slide_generator.self_review_slide(
            html=original_html,
            strategy={"_design_mode": "flash_standard", "design_style": {}, "content_analysis": {}},
            gemini_key="dummy-key",
        ))

        captured = capsys.readouterr()
        assert result == original_html
        assert "user_SYNTHETIC1234567890abcdef" not in captured.out
        assert "1234567890abcdef" not in captured.out
        assert "[REDACTED]" in captured.out

    def test_strategy_generation_error_redacts_stdout_and_telemetry(self, monkeypatch, capsys):
        async def fake_generate(*args, **kwargs):
            raise RuntimeError("OpenRouter user_id=user_SYNTHETIC1234567890abcdef key=sk-or-v1-1234567890abcdef")

        monkeypatch.setattr(ai_slide_generator, "safe_gemini_generate", fake_generate)
        collector = TelemetryCollector(job_id="job-strategy-redaction")
        token = set_current_collector(collector)
        try:
            result = asyncio.run(ai_slide_generator.generate_design_strategy(
                outline={"slides": [{"title": "Slide 1", "slide_copy": {"headline": "Slide 1"}}]},
                gemini_key="dummy-key",
                design_mode="flash_standard",
            ))
        finally:
            reset_current_collector(token)

        captured = capsys.readouterr()
        assert result.get("_design_mode") == "flash_standard"
        assert "user_SYNTHETIC1234567890abcdef" not in captured.out
        assert "1234567890abcdef" not in captured.out
        assert "[REDACTED]" in captured.out
        assert collector.entries[0].fallback_reason == "Strategy generation failed"
        assert "user_SYNTHETIC1234567890abcdef" not in collector.entries[0].warning
        assert "1234567890abcdef" not in collector.entries[0].warning
        assert "[REDACTED]" in collector.entries[0].warning


# ---------------------------------------------------------------------------
# Secret redaction
# ---------------------------------------------------------------------------


class TestRedactSecrets:
    def test_redacts_api_key_pattern(self):
        text = "Using key sk-or-v1-abc123def456ghi789jkl012mno345pqr678"
        result = redact_secrets(text)
        assert "abc123" not in result
        assert "sk-or" in result or "[REDACTED]" in result

    def test_redacts_bearer_token(self):
        text = "Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.abc"
        result = redact_secrets(text)
        assert "eyJhbGciOi" not in result

    def test_preserves_normal_text(self):
        text = "model=google/gemini-3-flash-preview tokens=1500"
        result = redact_secrets(text)
        assert result == text

    def test_redacts_gemini_key_pattern(self):
        text = "key=AIzaSyB1234567890abcdefghijklmnopqrstuvwx"
        result = redact_secrets(text)
        assert "1234567890abcdef" not in result

    def test_redacts_openrouter_user_id(self):
        text = "OpenRouter error included 'user_id': 'user_SYNTHETIC1234567890abcdef'"
        result = redact_secrets(text)
        assert "user_SYNTHETIC1234567890abcdef" not in result
        assert "user_[REDACTED]" in result

    def test_handles_empty_and_none(self):
        assert redact_secrets("") == ""
        assert redact_secrets(None) is None

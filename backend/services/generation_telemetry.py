"""
Sprint 1 — Generation telemetry.

Records which model was requested vs. actually used, token counts,
estimated cost, duration, and fallback/warning events for each AI
call during slide generation.

API-key-like strings are redacted before storage.
"""

from __future__ import annotations

import contextvars
import re
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Secret redaction
# ---------------------------------------------------------------------------

# Patterns that look like API keys / bearer tokens.
_SECRET_PATTERNS: List[re.Pattern] = [
    # OpenRouter: sk-or-v1-<hex>
    re.compile(r"(sk-or[-\w]{0,4})\w{10,}"),
    # OpenAI-style: sk-<...>
    re.compile(r"(sk-)\w{10,}"),
    # Google AI: AIzaSy<...>
    re.compile(r"(AIzaSy)\w{10,}"),
    # Provider/user identifiers that can appear inside upstream error payloads.
    re.compile(r"(user_)[A-Za-z0-9_-]{10,}"),
    # Bearer tokens (JWT-like)
    re.compile(r"(Bearer\s+)\S{20,}", re.IGNORECASE),
    # Generic long hex/base64 that looks like a secret (40+ chars)
    re.compile(r"(?<=[=:\s])[A-Za-z0-9+/]{40,}={0,2}(?=\s|$)"),
]


def redact_secrets(text: Optional[str]) -> Optional[str]:
    """Replace API-key-like substrings with [REDACTED].

    Returns *None* unchanged (callers don't need to guard).
    """
    if text is None:
        return None
    if not text:
        return text
    result = text
    for pat in _SECRET_PATTERNS:
        result = pat.sub(lambda m: (m.group(1) if m.groups() else "") + "[REDACTED]", result)
    return result


# ContextVar-based collector for one request/job. This lets lower-level AI
# helpers record telemetry without passing secrets or large objects through
# every call path.
_current_collector: contextvars.ContextVar[Optional["TelemetryCollector"]] = (
    contextvars.ContextVar("generation_telemetry_collector", default=None)
)
_current_design_mode: contextvars.ContextVar[str] = contextvars.ContextVar(
    "generation_telemetry_design_mode", default="flash_standard"
)
_current_stage: contextvars.ContextVar[str] = contextvars.ContextVar(
    "generation_telemetry_stage", default="unknown"
)
_current_slide_number: contextvars.ContextVar[Optional[int]] = contextvars.ContextVar(
    "generation_telemetry_slide_number", default=None
)


def set_current_collector(collector: Optional["TelemetryCollector"]):
    return _current_collector.set(collector)


def reset_current_collector(token) -> None:
    _current_collector.reset(token)


def get_current_collector() -> Optional["TelemetryCollector"]:
    return _current_collector.get()


def set_telemetry_context(
    *,
    design_mode: Optional[str] = None,
    stage: Optional[str] = None,
    slide_number: Optional[int] = None,
) -> Dict[str, Any]:
    """Set request-local telemetry metadata and return reset tokens."""
    tokens: Dict[str, Any] = {}
    if design_mode is not None:
        tokens["design_mode"] = _current_design_mode.set(design_mode)
    if stage is not None:
        tokens["stage"] = _current_stage.set(stage)
    if slide_number is not None:
        tokens["slide_number"] = _current_slide_number.set(slide_number)
    return tokens


def reset_telemetry_context(tokens: Dict[str, Any]) -> None:
    if "slide_number" in tokens:
        _current_slide_number.reset(tokens["slide_number"])
    if "stage" in tokens:
        _current_stage.reset(tokens["stage"])
    if "design_mode" in tokens:
        _current_design_mode.reset(tokens["design_mode"])


def record_current_telemetry(
    *,
    requested_model: str,
    actual_model: str,
    provider: str,
    duration_ms: int,
    input_tokens: Optional[int] = None,
    output_tokens: Optional[int] = None,
    estimated_cost_usd: Optional[float] = None,
    fallback_reason: Optional[str] = None,
    warning: Optional[str] = None,
    stage: Optional[str] = None,
    slide_number: Optional[int] = None,
    design_mode: Optional[str] = None,
) -> Optional["TelemetryEntry"]:
    collector = get_current_collector()
    if collector is None:
        return None
    return collector.record(
        design_mode=design_mode or _current_design_mode.get(),
        stage=stage or _current_stage.get(),
        slide_number=slide_number if slide_number is not None else _current_slide_number.get(),
        requested_model=requested_model,
        actual_model=actual_model,
        provider=provider,
        duration_ms=duration_ms,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        estimated_cost_usd=estimated_cost_usd,
        fallback_reason=fallback_reason,
        warning=warning,
    )


# ---------------------------------------------------------------------------
# Telemetry data
# ---------------------------------------------------------------------------


@dataclass
class TelemetryEntry:
    """One telemetry record for a single AI call or fallback event."""

    job_id: str
    design_mode: str  # "flash_standard" | "pro"
    stage: str  # "strategy" | "slide_html" | "self_review" | "fallback" | "video"
    slide_number: Optional[int]
    requested_model: str
    actual_model: str
    provider: str  # "openrouter" | "gemini" | "openai"
    duration_ms: int

    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    estimated_cost_usd: Optional[float] = None
    fallback_reason: Optional[str] = None
    warning: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        # Redact any secrets that might have leaked into reason/warning
        d["fallback_reason"] = redact_secrets(d.get("fallback_reason"))
        d["warning"] = redact_secrets(d.get("warning"))
        return d


# ---------------------------------------------------------------------------
# Collector — accumulates entries for one generation job
# ---------------------------------------------------------------------------


class TelemetryCollector:
    """Collects telemetry entries for a single generation job."""

    def __init__(self, job_id: str) -> None:
        self.job_id = job_id
        self.entries: List[TelemetryEntry] = []

    def record(
        self,
        *,
        design_mode: str,
        stage: str,
        slide_number: Optional[int] = None,
        requested_model: str,
        actual_model: str,
        provider: str,
        duration_ms: int,
        input_tokens: Optional[int] = None,
        output_tokens: Optional[int] = None,
        estimated_cost_usd: Optional[float] = None,
        fallback_reason: Optional[str] = None,
        warning: Optional[str] = None,
    ) -> TelemetryEntry:
        entry = TelemetryEntry(
            job_id=self.job_id,
            design_mode=design_mode,
            stage=stage,
            slide_number=slide_number,
            requested_model=requested_model,
            actual_model=actual_model,
            provider=provider,
            duration_ms=duration_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost_usd=estimated_cost_usd,
            fallback_reason=redact_secrets(fallback_reason),
            warning=redact_secrets(warning),
        )
        self.entries.append(entry)
        return entry

    def to_list(self) -> List[Dict[str, Any]]:
        return [e.to_dict() for e in self.entries]

    def summary(self) -> Dict[str, Any]:
        total_duration = sum(e.duration_ms for e in self.entries)
        fallback_count = sum(1 for e in self.entries if e.fallback_reason)
        total_input = None
        total_output = None
        total_cost = None

        for e in self.entries:
            if e.input_tokens is not None:
                total_input = (total_input or 0) + e.input_tokens
            if e.output_tokens is not None:
                total_output = (total_output or 0) + e.output_tokens
            if e.estimated_cost_usd is not None:
                total_cost = (total_cost or 0.0) + e.estimated_cost_usd

        entry_count = len(self.entries)
        return {
            "job_id": self.job_id,
            "entry_count": entry_count,
            "total_calls": entry_count,
            "total_duration_ms": total_duration,
            "fallback_count": fallback_count,
            "total_input_tokens": total_input,
            "total_output_tokens": total_output,
            "total_estimated_cost_usd": total_cost,
        }

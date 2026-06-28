"""Sprint 14 — provider response parsing and typography hardening tests."""

from __future__ import annotations

import json

from services.ai_slide_generator import (
    _parse_design_strategy_response,
    harden_generated_html_typography,
    self_review_preserves_slide_title,
)
from services.design_quality_metrics import analyze_design_quality


BASE_STRATEGY = {
    "content_analysis": {
        "core_message": "伝える",
        "emotional_tone": "clear",
        "key_concepts": ["a", "b", "c"],
        "target_audience": "audience",
    },
    "design_style": {
        "concept_name": "Clear Light",
        "concept_description": "desc",
        "color_palette": {
            "primary": "#ffffff",
            "secondary": "#93c5fd",
            "accent": "#38bdf8",
            "background_start": "#0f172a",
            "background_end": "#1e293b",
        },
        "typography_direction": "bold",
        "visual_theme": "light",
    },
}


def test_parse_design_strategy_response_accepts_fenced_json_with_preface():
    raw = "Here is the JSON:\n```json\n" + json.dumps(BASE_STRATEGY, ensure_ascii=False) + "\n```"

    parsed = _parse_design_strategy_response(raw)

    assert parsed["design_style"]["concept_name"] == "Clear Light"


def test_parse_design_strategy_response_accepts_plain_json_with_trailing_note():
    raw = json.dumps(BASE_STRATEGY, ensure_ascii=False) + "\n\n補足: この戦略で進めます。"

    parsed = _parse_design_strategy_response(raw)

    assert parsed["content_analysis"]["core_message"] == "伝える"


def test_harden_generated_html_typography_raises_regular_small_text_above_gate():
    html = """<!DOCTYPE html><html><head><style>
    .title { font-size: 96px; }
    .body-copy { font-size: 16px; }
    .caption { font-size: 14px; }
    .slide-number { font-size: 16px; }
    </style></head><body>
    <h1 class="title">タイトル</h1>
    <p class="body-copy" style="font-size:18px;">本文テキスト</p>
    <div class="caption">装飾キャプション</div>
    <div class="slide-number">01 / 02</div>
    </body></html>"""

    hardened = harden_generated_html_typography(html)
    metrics = analyze_design_quality(hardened)

    assert metrics["small_text_count"] == 0
    assert metrics["quality_gate"] in {"pass", "warn"}
    assert "caption" in hardened  # decorative chrome stays allowed/small


def test_self_review_preserves_slide_title_detects_rewrites():
    original = "<html><body><h1>宇宙意識で生きる</h1><p>本文</p></body></html>"
    improved = "<html><body><h1>意識を変える</h1><p>本文</p></body></html>"

    assert self_review_preserves_slide_title(original, improved) is False
    assert self_review_preserves_slide_title(original, original) is True

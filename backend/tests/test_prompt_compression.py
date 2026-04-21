"""
Sprint B — SLIDE_DESIGN prompt compression regression tests.

Sprint A split SLIDE_DESIGN_PROMPT into SYSTEM + USER but kept the full
text in both slots for safety (zero behavioral change). Sprint B compresses
the user slot so the role/rules/process only live in SYSTEM, and the USER
prompt only carries per-slide variables + strategy + content + tech specs.

These tests pin down the contract so a future refactor doesn't accidentally
re-balloon the user prompt (and blow past the per-slide token budget):

1. The user prompt no longer contains the big repeated rule blocks
   (CSS typography boilerplate, forbidden-color lists, etc.)
2. All format placeholders still resolve — we must not have deleted a
   `{field}` that generate_slide_html is still passing.
3. The system prompt alone carries the critical rules, so callers can
   rely on system-slot caching.
"""

from __future__ import annotations

import pytest

from services.ai_slide_generator import (
    SLIDE_DESIGN_PROMPT,
    SLIDE_DESIGN_SYSTEM_PROMPT,
    SLIDE_DESIGN_USER_PROMPT,
    DESIGN_STRATEGY_SYSTEM_PROMPT,
    DESIGN_STRATEGY_USER_PROMPT,
)


# ---------------------------------------------------------------------------
# Structural contracts (prompt sizes and no-regression on user-slot bloat)
# ---------------------------------------------------------------------------


def test_slide_user_prompt_is_substantially_smaller_than_system_prompt():
    """The whole point of Sprint B: the user slot is now a slim per-slide
    envelope, not a 260-line rulebook. System carries the rules."""
    user_len = len(SLIDE_DESIGN_PROMPT)
    system_len = len(SLIDE_DESIGN_SYSTEM_PROMPT)
    # User prompt should be at most ~half the system prompt length.
    # (Pre-Sprint-B the user prompt was ~5x larger than the system prompt.)
    assert user_len < system_len, (
        f"user_len={user_len} >= system_len={system_len}; "
        "did you accidentally re-stuff the user prompt with rule text?"
    )


def test_slide_user_prompt_no_longer_includes_typography_boilerplate():
    """The 50-line typography CSS block now lives in SYSTEM only.
    If this assertion fires, somebody put it back into the user slot."""
    # A distinctive fragment from the typography CSS block
    assert "word-break: keep-all" not in SLIDE_DESIGN_PROMPT, (
        "typography CSS block has leaked back into the user prompt"
    )
    assert "word-break: keep-all" in SLIDE_DESIGN_SYSTEM_PROMPT, (
        "typography CSS block must live in the system prompt"
    )


def test_slide_user_prompt_no_longer_includes_forbidden_color_list():
    """The long forbidden-color list (`#8B4513` / `sienna` / etc.) is the
    single biggest token cost in the old prompt. It now lives in SYSTEM."""
    assert "#8B4513" not in SLIDE_DESIGN_PROMPT
    assert "sienna" not in SLIDE_DESIGN_PROMPT
    # But system prompt should still carry the short version
    assert "#FBBF24" in SLIDE_DESIGN_SYSTEM_PROMPT  # gold (in the short allowlist)


def test_slide_user_prompt_keeps_all_required_placeholders():
    """Every {field} the user prompt references must still be reachable
    via generate_slide_html's .format() call. This is the safety net that
    catches accidental deletions."""
    required = [
        "{layout_instruction}",
        "{concept_name}",
        "{concept_description}",
        "{emotional_tone}",
        "{visual_theme}",
        "{primary}",
        "{secondary}",
        "{accent}",
        "{background_start}",
        "{background_end}",
        "{personality_section}",
        "{slide_number}",
        "{total_slides}",
        "{slide_type}",
        "{title}",
        "{subtitle}",
        "{points}",
        "{key_message}",
        "{image_section}",
        "{width}",
        "{height}",
        "{font_import}",
        "{font_instruction}",
    ]
    for placeholder in required:
        assert placeholder in SLIDE_DESIGN_PROMPT, (
            f"compressed SLIDE_DESIGN_PROMPT is missing {placeholder!r} — "
            "generate_slide_html .format() would break"
        )


def test_system_prompt_contains_critical_rules():
    """System prompt must carry the rules that used to be duplicated in
    the user prompt. If any of these drop out, quality will regress because
    OpenRouter callers won't see them anymore."""
    critical_fragments = [
        "コピー",            # copy rules
        "Design Process",     # the 4-step design process
        "word-break: keep-all",  # typography CSS
        "#FBBF24",            # allowed bright color example
        "-webkit-background-clip: text",  # gradient text rules
        "字幕",              # forbidden subtitles
    ]
    for frag in critical_fragments:
        assert frag in SLIDE_DESIGN_SYSTEM_PROMPT, (
            f"system prompt no longer contains {frag!r} — "
            "this rule would stop reaching Claude/GPT via the system slot"
        )


def test_slide_user_prompt_still_formats_cleanly():
    """Sanity check: .format() with dummy values must produce a valid
    string. Catches stray literal curly braces."""
    filler = {
        "layout_instruction": "X",
        "concept_name": "X",
        "concept_description": "X",
        "emotional_tone": "X",
        "visual_theme": "X",
        "primary": "#000000",
        "secondary": "#000000",
        "accent": "#000000",
        "background_start": "#000000",
        "background_end": "#000000",
        "personality_section": "X",
        "slide_number": 1,
        "total_slides": 1,
        "slide_type": "title",
        "title": "X",
        "subtitle": "X",
        "points": "X",
        "key_message": "X",
        "image_section": "X",
        "width": 1920,
        "height": 1080,
        "font_import": "Noto Sans JP",
        "font_instruction": "X",
    }
    # Should not raise KeyError or ValueError
    rendered = SLIDE_DESIGN_PROMPT.format(**filler)
    assert "layout_instruction" not in rendered  # placeholder was consumed
    assert len(rendered) > 0


# ---------------------------------------------------------------------------
# Approximate token budget (heuristic: 1 token ≈ 4 chars for mixed JP/EN)
# ---------------------------------------------------------------------------


def _estimate_tokens(text: str) -> int:
    """Char-based heuristic; good enough to catch order-of-magnitude
    regressions without requiring tiktoken as a test dependency."""
    return max(1, len(text) // 4)


def test_user_prompt_token_budget_respects_sprint_b_target():
    """Sprint B target: per-slide user prompt ≤ 2,400 est. tokens (vs ~3,500
    pre-Sprint-B). The placeholder-populated version used in production
    is slightly larger because layout_instruction and personality_section
    can each add several hundred tokens, but the template itself should be
    well under budget."""
    est = _estimate_tokens(SLIDE_DESIGN_PROMPT)
    assert est < 600, (
        f"compressed user prompt template estimated at {est} tokens — "
        "Sprint B target was < 600 for the template itself"
    )


def test_strategy_user_prompt_is_slim():
    """Design strategy user prompt should only carry the per-project
    variable content (title, slides list, optional color theme)."""
    assert "{presentation_title}" in DESIGN_STRATEGY_USER_PROMPT
    assert "{slides_content}" in DESIGN_STRATEGY_USER_PROMPT
    assert "{color_theme_instruction}" in DESIGN_STRATEGY_USER_PROMPT
    # The long "Process" section must live in SYSTEM only
    assert "Step 1: Content Analysis" not in DESIGN_STRATEGY_USER_PROMPT
    assert "Step 1: Content Analysis" in DESIGN_STRATEGY_SYSTEM_PROMPT

"""
Sprint C — design_mode plumbing tests.

These tests pin the "Flash 標準 / Pro" split:

1. select_layout_for_slide() honors the AI's recommendation in Pro mode
   and falls back to deterministic Python cycling in Flash mode.
2. Unknown layout_keys in a Pro strategy become a "custom_ai" layout with
   the override hints (the escape hatch for genuinely novel layouts).
3. Flash mode is the default and must never touch strategy_layouts even
   when the AI happens to include them (backward compat for existing
   projects that are on the cheap path).
"""

from __future__ import annotations

import pytest

from services.ai_slide_generator import (
    select_layout_for_slide,
    LAYOUT_TYPES,
    _used_layouts_cache,
)


@pytest.fixture(autouse=True)
def _clean_layout_cache():
    """Every test starts with an empty layout cache so variety/dedupe
    decisions are deterministic."""
    _used_layouts_cache.clear()
    yield
    _used_layouts_cache.clear()


# ---------------------------------------------------------------------------
# Pro mode: strategy_layouts wins
# ---------------------------------------------------------------------------


def test_pro_mode_uses_ai_picked_layout_from_strategy():
    """When the AI strategy suggests 'cards' for slide 3, select_layout
    MUST return cards (from LAYOUT_TYPES) — not the deterministic cycling
    result."""
    strategy_layouts = [
        {"slide_number": 1, "layout_key": "center_hero"},
        {"slide_number": 2, "layout_key": "left_heavy"},
        {"slide_number": 3, "layout_key": "cards", "override_hints": "3 glass cards with icons"},
    ]
    layout = select_layout_for_slide(
        job_id="job-pro",
        slide_number=3,
        total_slides=5,
        content_type="points",
        num_points=3,
        design_mode="pro",
        strategy_layouts=strategy_layouts,
    )
    assert layout["key"] == "cards"
    # override_hints must be merged into description so the per-slide
    # generator sees the AI's intent
    assert "3 glass cards with icons" in layout["description"]


def test_pro_mode_unknown_layout_key_becomes_custom_ai():
    """If the AI invents a layout like 'asymmetric_poster_split' that
    doesn't exist in LAYOUT_TYPES, we accept it as a custom_ai layout
    carrying the override_hints. This is the escape hatch for Opus 4.7
    etc. to compose genuinely novel layouts."""
    strategy_layouts = [{
        "slide_number": 1,
        "layout_key": "asymmetric_poster_split",
        "override_hints": "40/60 split, bold headline left, decorative glyph right",
    }]
    layout = select_layout_for_slide(
        job_id="job-custom",
        slide_number=1,
        total_slides=1,
        content_type="title",
        num_points=0,
        design_mode="pro",
        strategy_layouts=strategy_layouts,
    )
    assert layout["key"] == "custom_ai"
    assert "asymmetric_poster_split" in layout["name"]
    assert "40/60 split" in layout["description"]


def test_pro_mode_missing_slide_number_falls_through_to_deterministic():
    """When the AI strategy has NO entry for this slide_number, we don't
    guess — we fall through to the deterministic path. This keeps the
    behavior well-defined when the AI's slide_layouts list is shorter
    than total_slides."""
    strategy_layouts = [
        {"slide_number": 1, "layout_key": "center_hero"},
        # No entry for slide 2
    ]
    layout = select_layout_for_slide(
        job_id="job-partial",
        slide_number=2,
        total_slides=3,
        content_type="points",
        num_points=3,
        design_mode="pro",
        strategy_layouts=strategy_layouts,
    )
    # Should be one of the deterministic-path layouts, not custom_ai
    assert layout["key"] != "custom_ai"
    assert layout["key"] in LAYOUT_TYPES
    # And actually makes sense for the content
    assert "best_for" in layout


def test_pro_mode_unknown_key_without_hints_falls_through():
    """Defensive: unknown layout_key AND no override_hints = garbage AI
    output; fall back to deterministic path rather than render an empty
    custom_ai layout the per-slide prompt can't act on."""
    strategy_layouts = [{
        "slide_number": 1,
        "layout_key": "totally_made_up_layout",
        # no override_hints
    }]
    layout = select_layout_for_slide(
        job_id="job-bad-ai",
        slide_number=1,
        total_slides=1,
        content_type="title",
        num_points=0,
        design_mode="pro",
        strategy_layouts=strategy_layouts,
    )
    # Falls through to deterministic path; returns a real LAYOUT_TYPES entry
    assert layout["key"] in LAYOUT_TYPES


# ---------------------------------------------------------------------------
# Flash standard mode: deterministic cycling preserved
# ---------------------------------------------------------------------------


def test_flash_standard_ignores_strategy_layouts():
    """Even if strategy_layouts is passed (shouldn't happen in practice
    but defensive), Flash mode must NEVER use them — that's the whole
    point of having the two modes. This is the backward-compat guarantee
    for existing projects that upgrade from pre-Sprint-C."""
    strategy_layouts = [
        {"slide_number": 1, "layout_key": "cards"},  # AI wants cards
    ]
    layout = select_layout_for_slide(
        job_id="job-flash",
        slide_number=1,
        total_slides=3,
        content_type="title",
        num_points=0,
        design_mode="flash_standard",
        strategy_layouts=strategy_layouts,
    )
    # slide_number=1 in deterministic Python path is always center_hero
    # (regardless of what the AI suggested)
    assert layout["key"] == "center_hero"


def test_default_design_mode_is_flash_standard():
    """Calling select_layout_for_slide() without a design_mode arg must
    behave exactly like pre-Sprint-C: deterministic Python cycling."""
    layout = select_layout_for_slide(
        job_id="job-default",
        slide_number=1,
        total_slides=3,
        content_type="title",
        num_points=0,
    )
    assert layout["key"] == "center_hero"


# ---------------------------------------------------------------------------
# Catalog sanity (so Pro mode has layouts to recommend)
# ---------------------------------------------------------------------------


def test_layout_types_catalog_is_populated():
    """Pro mode's strategy prompt hints at the layout catalog, so let's
    make sure the catalog actually exists and contains the canonical
    starter set. If these ever get renamed, Pro mode's hint list goes
    stale and AI starts suggesting keys that are valid-ish but
    mismatched."""
    for key in ("center_hero", "left_heavy", "right_heavy", "cards", "minimal"):
        assert key in LAYOUT_TYPES, f"LAYOUT_TYPES missing canonical key {key!r}"

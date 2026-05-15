"""
Sprint 2 — Design quality metrics tests (TDD).

Verifies that:
- Small font-size (e.g. 18px) is detected as fail/warn.
- clamp() with small lower bound is flagged as warn.
- Large title + 32px body passes.
- Empty HTML doesn't crash.
- rem/em units are converted approximately.
- Inline style and <style> blocks are both parsed.
- 20px or smaller regular text is flagged.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from services.design_quality_metrics import (
    analyze_font_sizes,
    analyze_design_quality,
    analyze_design_quality_with_browser_layout,
    analyze_screenshot_blank_area,
)
from services.ai_slide_generator import build_design_quality_metrics, generate_fallback_html


# ---------------------------------------------------------------------------
# Font-size extraction
# ---------------------------------------------------------------------------


class TestAnalyzeFontSizes:
    def test_inline_px_extraction(self):
        html = '<div style="font-size: 18px;">small text</div>'
        sizes = analyze_font_sizes(html)
        assert 18.0 in sizes

    def test_style_block_extraction(self):
        html = """
        <style>
        .title { font-size: 82px; }
        .body { font-size: 32px; }
        </style>
        <h1 class="title">Big</h1>
        <p class="body">Normal</p>
        """
        sizes = analyze_font_sizes(html)
        assert 82.0 in sizes
        assert 32.0 in sizes

    def test_raw_extraction_includes_global_and_slide_chrome_sizes(self):
        html = """
        <style>
        body { font-size: 16px; }
        .title { font-size: 84px; }
        .body { font-size: 32px; }
        .slide-number { font-size: 16px; }
        </style>
        """
        sizes = analyze_font_sizes(html)
        assert sizes.count(16.0) == 2
        assert 84.0 in sizes
        assert 32.0 in sizes

    def test_rem_conversion(self):
        html = '<p style="font-size: 2rem;">text</p>'
        sizes = analyze_font_sizes(html)
        # 2rem ≈ 32px (base 16px)
        assert 32.0 in sizes

    def test_em_conversion(self):
        html = '<p style="font-size: 1.5em;">text</p>'
        sizes = analyze_font_sizes(html)
        # 1.5em ≈ 24px (base 16px)
        assert 24.0 in sizes

    def test_clamp_extracts_lower_bound(self):
        html = '<p style="font-size: clamp(1rem, 2vw, 2rem);">text</p>'
        sizes = analyze_font_sizes(html)
        # clamp lower bound: 1rem = 16px
        assert 16.0 in sizes

    def test_empty_html(self):
        sizes = analyze_font_sizes("")
        assert sizes == []

    def test_no_font_size(self):
        html = "<div>no font info</div>"
        sizes = analyze_font_sizes(html)
        assert sizes == []


# ---------------------------------------------------------------------------
# Full quality analysis
# ---------------------------------------------------------------------------


class TestAnalyzeDesignQuality:
    def test_small_body_text_is_fail(self):
        html = """
        <style>
        .title { font-size: 72px; }
        .body { font-size: 18px; }
        </style>
        <h1 class="title">Title</h1>
        <p class="body">This is body text that is too small</p>
        """
        result = analyze_design_quality(html)
        assert result["quality_gate"] in ("fail", "warn")
        assert result["min_font_size_px"] == 18.0
        assert result["small_text_count"] >= 1

    def test_large_title_normal_body_passes(self):
        html = """
        <style>
        .title { font-size: 82px; }
        .subtitle { font-size: 40px; }
        .body { font-size: 32px; }
        .footnote { font-size: 24px; }
        </style>
        <h1 class="title">Big Title</h1>
        <h2 class="subtitle">Subtitle</h2>
        <p class="body">Body text</p>
        <span class="footnote">Note</span>
        """
        result = analyze_design_quality(html)
        assert result["quality_gate"] == "pass"
        assert result["title_font_size_px"] == 82.0
        assert result["body_font_size_px_min"] >= 24.0
        assert result["small_text_count"] == 0

    def test_20px_text_is_flagged(self):
        html = '<p style="font-size: 20px;">tiny text</p>'
        result = analyze_design_quality(html)
        assert result["quality_gate"] in ("fail", "warn")
        assert result["small_text_count"] >= 1

    def test_slide_chrome_and_global_defaults_do_not_fail_large_content(self):
        html = """
        <style>
        body { font-size: 16px; }
        .title { font-size: 84px; }
        .body { font-size: 32px; }
        .slide-number { font-size: 16px; }
        </style>
        <h1 class="title">Readable title</h1>
        <p class="body">Readable body text</p>
        <div class="slide-number">01 / 02</div>
        """
        result = analyze_design_quality(html)
        assert result["quality_gate"] == "pass"
        assert result["min_font_size_px"] == 32.0
        assert result["small_text_count"] == 0

    def test_inline_slide_chrome_is_ignored_even_when_style_precedes_class(self):
        html = """
        <h1 style="font-size: 84px;">Readable title</h1>
        <p style="font-size: 32px;">Readable body text</p>
        <div style="font-size: 16px;" class="slide-number">01 / 02</div>
        """
        result = analyze_design_quality(html)
        assert result["quality_gate"] == "pass"
        assert result["min_font_size_px"] == 32.0
        assert result["small_text_count"] == 0

    def test_grouped_selector_keeps_content_selector_when_mixed_with_body(self):
        html = """
        <style>
        body, .body { font-size: 32px; }
        .title { font-size: 84px; }
        .slide-number { font-size: 16px; }
        </style>
        <h1 class="title">Readable title</h1>
        <p class="body">Readable body text</p>
        <div class="slide-number">01 / 02</div>
        """
        result = analyze_design_quality(html)
        assert result["quality_gate"] == "pass"
        assert result["min_font_size_px"] == 32.0
        assert result["small_text_count"] == 0

    def test_decorative_support_text_does_not_fail_readable_slide(self):
        html = """
        <style>
        .title { font-size: 84px; }
        .body { font-size: 32px; }
        .decorative-label { font-size: 16px; }
        .footer-note { font-size: 18px; }
        </style>
        <div class="decorative-label">SECTION 02</div>
        <h1 class="title">Readable title</h1>
        <p class="body">Readable body text</p>
        <div class="footer-note">Supplemental footer marker</div>
        """

        result = analyze_design_quality(html)

        assert result["quality_gate"] == "pass"
        assert result["min_font_size_px"] == 32.0
        assert result["small_text_count"] == 0

    def test_inline_decorative_support_text_does_not_fail_readable_slide(self):
        html = """
        <div class="section-label" style="font-size: 16px;">SECTION 02</div>
        <h1 style="font-size: 84px;">Readable title</h1>
        <p style="font-size: 32px;">Readable body text</p>
        <div class="caption" style="font-size: 18px;">Supplemental visual caption</div>
        """

        result = analyze_design_quality(html)

        assert result["quality_gate"] == "pass"
        assert result["min_font_size_px"] == 32.0
        assert result["small_text_count"] == 0

    def test_pro_fallback_section_label_does_not_fail_quality_gate(self):
        html = generate_fallback_html(
            {
                "title": "Readable title",
                "points": ["Readable body point", "Another readable body point"],
            },
            slide_number=2,
            total_slides=2,
            strategy={
                "_design_mode": "pro",
                "design_style": {
                    "color_palette": {
                        "primary": "#F59E0B",
                        "secondary": "#8B5CF6",
                        "accent": "#06B6D4",
                    }
                },
            },
        )

        result = analyze_design_quality(html, fallback_used=True)

        assert result["quality_gate"] == "pass"
        assert result["small_text_count"] == 0

    def test_browser_layout_counts_large_title_as_main_occupancy_without_wrapper_class(self):
        html = """<!DOCTYPE html><html><head><style>
        body { width: 1920px; height: 1080px; margin: 0; display: flex; align-items: center; justify-content: center; }
        h1 { font-size: 112px; line-height: 1.3; width: 1200px; min-height: 560px; text-align: center; }
        </style></head><body>
        <h1>日本語の読みやすさと復元確認</h1>
        </body></html>"""

        result = analyze_design_quality_with_browser_layout(html)

        assert result["main_element_occupancy_ratio"] >= 0.30
        assert result["quality_gate"] == "pass"
        assert not any("主役要素の画面占有率" in warning for warning in result["warnings"])

    def test_browser_layout_metric_does_not_execute_generated_scripts(self):
        html = """<!DOCTYPE html><html><head><style>
        body { width: 1920px; height: 1080px; margin: 0; display: flex; align-items: center; justify-content: center; }
        h1 { font-size: 112px; line-height: 1.3; width: 1200px; min-height: 560px; text-align: center; }
        </style><script>
        document.addEventListener('DOMContentLoaded', () => {
          document.querySelector('h1').style.display = 'none';
        });
        </script></head><body>
        <h1>日本語の読みやすさと復元確認</h1>
        </body></html>"""

        result = analyze_design_quality_with_browser_layout(html)

        assert result["main_element_occupancy_ratio"] >= 0.30
        assert result["quality_gate"] == "pass"

    def test_clamp_small_lower_bound_warns(self):
        html = '<p style="font-size: clamp(0.5rem, 2vw, 2rem);">text</p>'
        result = analyze_design_quality(html)
        # 0.5rem = 8px — too small
        assert result["quality_gate"] in ("fail", "warn")
        assert len(result["warnings"]) > 0

    def test_empty_html_does_not_crash(self):
        result = analyze_design_quality("")
        assert result["quality_gate"] in ("pass", "warn")
        assert result["min_font_size_px"] is None
        assert result["small_text_count"] == 0

    def test_fallback_used_flag(self):
        result = analyze_design_quality("", fallback_used=True)
        assert result["fallback_used"] is True

    def test_result_contains_required_keys(self):
        html = '<p style="font-size: 32px;">ok</p>'
        result = analyze_design_quality(html)
        required_keys = {
            "min_font_size_px",
            "title_font_size_px",
            "body_font_size_px_min",
            "small_text_count",
            "fallback_used",
            "quality_gate",
            "warnings",
        }
        assert required_keys.issubset(result.keys())

    def test_title_detection_uses_largest_font(self):
        html = """
        <h1 style="font-size: 96px;">Title</h1>
        <p style="font-size: 36px;">Body</p>
        """
        result = analyze_design_quality(html)
        assert result["title_font_size_px"] == 96.0

    def test_warn_when_title_below_target_but_above_minimum(self):
        """Title at 60px: above 56px minimum but below 72px target → warn."""
        html = """
        <h1 style="font-size: 60px;">Title</h1>
        <p style="font-size: 32px;">Body</p>
        """
        result = analyze_design_quality(html)
        assert result["quality_gate"] == "warn"
        # Should have a warning about title being below target
        title_warnings = [w for w in result["warnings"] if "title" in w.lower() or "72" in w]
        assert title_warnings

    def test_detects_underused_canvas_when_main_group_is_too_small(self):
        html = """
        <section class="slide">
          <div class="main-card" style="width: 320px; height: 180px;">
            <h1 style="font-size: 84px;">Title</h1>
            <p style="font-size: 32px;">Body text</p>
          </div>
        </section>
        """

        result = analyze_design_quality(html)

        assert result["main_element_occupancy_ratio"] == pytest.approx(0.0625)
        assert result["blank_area_ratio_estimate"] == pytest.approx(0.9375)
        assert result["quality_gate"] == "warn"
        assert any("画面" in warning or "canvas" in warning.lower() for warning in result["warnings"])

    def test_large_main_group_canvas_occupancy_passes(self):
        html = """
        <section class="slide">
          <div class="hero-layout" style="width: 960px; height: 540px;">
            <h1 style="font-size: 84px;">Title</h1>
            <p style="font-size: 32px;">Body text</p>
          </div>
        </section>
        """

        result = analyze_design_quality(html)

        assert result["main_element_occupancy_ratio"] == pytest.approx(0.5625)
        assert result["blank_area_ratio_estimate"] == pytest.approx(0.4375)
        assert result["quality_gate"] == "pass"

    def test_detects_underused_canvas_from_style_block_class_rule(self):
        html = """
        <style>
          .main-card {
            width: 320px;
            height: 180px;
          }
          .main-card h1 { font-size: 84px; }
          .main-card p { font-size: 32px; }
        </style>
        <section class="slide">
          <div class="main-card">
            <h1>Title</h1>
            <p>Body text</p>
          </div>
        </section>
        """

        result = analyze_design_quality(html)

        assert result["main_element_occupancy_ratio"] == pytest.approx(0.0625)
        assert result["blank_area_ratio_estimate"] == pytest.approx(0.9375)
        assert result["quality_gate"] == "warn"

    def test_large_main_group_from_style_block_id_rule_passes(self):
        html = """
        <style>
          #heroLayout {
            width: 75%;
            height: 75%;
          }
          #heroLayout h1 { font-size: 84px; }
          #heroLayout p { font-size: 32px; }
        </style>
        <section class="slide">
          <div id="heroLayout">
            <h1>Title</h1>
            <p>Body text</p>
          </div>
        </section>
        """

        result = analyze_design_quality(html)

        assert result["main_element_occupancy_ratio"] == pytest.approx(0.5625)
        assert result["blank_area_ratio_estimate"] == pytest.approx(0.4375)
        assert result["quality_gate"] == "pass"

    def test_ignores_large_decorative_style_block_shapes_for_occupancy(self):
        html = """
        <style>
          .glow-bg { width: 1600px; height: 1600px; }
          .main-card { width: 320px; height: 180px; }
          .main-card h1 { font-size: 84px; }
          .main-card p { font-size: 32px; }
        </style>
        <section class="slide">
          <div class="glow-bg"></div>
          <div class="main-card">
            <h1>Title</h1>
            <p>Body text</p>
          </div>
        </section>
        """

        result = analyze_design_quality(html)

        assert result["main_element_occupancy_ratio"] == pytest.approx(0.0625)
        assert result["quality_gate"] == "warn"

    def test_estimates_occupancy_from_max_width_and_min_height_style_rule(self):
        html = """
        <style>
          .content-frame {
            max-width: 960px;
            min-height: 540px;
          }
          .content-frame h1 { font-size: 84px; }
          .content-frame p { font-size: 32px; }
        </style>
        <section class="slide">
          <div class="content-frame">
            <h1>Title</h1>
            <p>Body text</p>
          </div>
        </section>
        """

        result = analyze_design_quality(html)

        assert result["main_element_occupancy_ratio"] == pytest.approx(0.5625)
        assert result["quality_gate"] == "pass"

    def test_estimates_occupancy_from_viewport_units(self):
        html = """
        <style>
          .stage {
            width: 80vw;
            height: 60vh;
          }
          .stage h1 { font-size: 84px; }
          .stage p { font-size: 32px; }
        </style>
        <section class="slide">
          <div class="stage">
            <h1>Title</h1>
            <p>Body text</p>
          </div>
        </section>
        """

        result = analyze_design_quality(html)

        assert result["main_element_occupancy_ratio"] == pytest.approx(0.48)
        assert result["quality_gate"] == "pass"

    def test_estimates_occupancy_from_style_rule_with_leading_css_comment(self):
        html = """
        <style>
          /* メインコンテナ */ .main {
            width: 960px;
            height: 540px;
          }
          .main h1 { font-size: 84px; }
          .main p { font-size: 32px; }
        </style>
        <section class="slide">
          <div class="main">
            <h1>Title</h1>
            <p>Body text</p>
          </div>
        </section>
        """

        result = analyze_design_quality(html)

        assert result["main_element_occupancy_ratio"] == pytest.approx(0.5625)
        assert result["quality_gate"] == "pass"

    def test_browser_layout_estimates_auto_height_main_content(self):
        html = """
        <style>
          body { margin: 0; }
          .slide { width: 1280px; height: 720px; display: grid; place-items: center; }
          .main-content {
            width: 960px;
            padding: 96px 80px;
            box-sizing: border-box;
          }
          .main-content h1 { font-size: 84px; line-height: 1.12; margin: 0 0 36px; }
          .main-content p { font-size: 32px; line-height: 1.45; margin: 0; }
        </style>
        <section class="slide">
          <div class="main-content">
            <h1>Title</h1>
            <p>Browser computed layout can measure this auto-height content block.</p>
          </div>
        </section>
        """

        static_result = analyze_design_quality(html)
        browser_result = analyze_design_quality_with_browser_layout(html)

        assert static_result["main_element_occupancy_ratio"] is None
        assert browser_result["main_element_occupancy_ratio"] is not None
        assert browser_result["main_element_occupancy_ratio"] >= 0.30
        assert browser_result["blank_area_ratio_estimate"] == pytest.approx(
            1.0 - browser_result["main_element_occupancy_ratio"]
        )
        assert browser_result["quality_gate"] == "pass"

    def test_browser_layout_estimates_real_artifact_container_class(self):
        html = """
        <style>
          body {
            margin: 0;
            width: 1280px;
            height: 720px;
            display: flex;
            align-items: center;
            justify-content: center;
          }
          .container {
            position: relative;
            z-index: 2;
            text-align: center;
            max-width: 1120px;
            width: 100%;
          }
          .eyebrow { font-size: 24px; margin-bottom: 56px; }
          h1 { font-size: 92px; line-height: 1.24; margin: 0 auto; }
        </style>
        <div class="glow"></div>
        <div class="container">
          <div class="eyebrow">VOISLIDE</div>
          <h1>音声から<br/>スライド動画へ</h1>
        </div>
        """

        static_result = analyze_design_quality(html)
        browser_result = analyze_design_quality_with_browser_layout(html)

        assert static_result["main_element_occupancy_ratio"] is None
        assert browser_result["main_element_occupancy_ratio"] is not None
        assert browser_result["main_element_occupancy_ratio"] >= 0.30
        assert browser_result["quality_gate"] == "pass"

    def test_browser_layout_overrides_tiny_static_decorative_occupancy_with_real_content(self):
        html = """
        <style>
          body { margin: 0; }
          .slide { width: 1920px; height: 1080px; position: relative; display: flex; align-items: center; justify-content: center; }
          .spark { width: 24px; height: 12px; position: absolute; top: 40px; left: 40px; }
          .content {
            width: 1478px;
            padding: 96px 0;
            box-sizing: border-box;
            text-align: center;
          }
          .content h1 { font-size: 72px; line-height: 1.3; margin: 0 0 32px; }
          .content p { font-size: 32px; line-height: 1.4; margin: 0; }
        </style>
        <section class="slide">
          <div class="spark"></div>
          <div class="content">
            <h1>音声からスライド動画を作る流れ</h1>
            <p>A STEP-BY-STEP PRODUCTION GUIDE</p>
          </div>
        </section>
        """

        static_result = analyze_design_quality(html)
        browser_result = analyze_design_quality_with_browser_layout(html)

        assert static_result["main_element_occupancy_ratio"] is not None
        assert static_result["main_element_occupancy_ratio"] < 0.01
        assert browser_result["main_element_occupancy_ratio"] >= 0.30
        assert browser_result["quality_gate"] == "pass"

    def test_browser_layout_detects_japanese_title_horizontal_clipping(self):
        html = """
        <style>
          body {
            margin: 0;
            width: 1280px;
            height: 720px;
            display: grid;
            place-items: center;
          }
          h1 {
            font-size: 128px;
            line-height: 1.18;
            letter-spacing: 0.02em;
            max-width: 92%;
            padding: 0 20px;
            white-space: normal;
            overflow: visible;
            overflow-wrap: normal;
            word-break: keep-all;
            line-break: strict;
            text-wrap: balance;
          }
        </style>
        <h1>音声からスライド動画を作る流れ</h1>
        """

        result = analyze_design_quality_with_browser_layout(html)

        assert result["text_clipping_detected"] is True
        assert result["quality_gate"] == "warn"
        assert any("タイトル" in warning and "横幅" in warning for warning in result["warnings"])


class TestAnalyzeScreenshotBlankArea:
    def test_detects_sparse_screenshot_blank_area(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            image_path = Path(tmpdir) / "sparse.png"
            image = Image.new("RGB", (1280, 720), "white")
            draw = ImageDraw.Draw(image)
            draw.rectangle((540, 290, 740, 430), fill=(20, 40, 80))
            image.save(image_path)

            result = analyze_screenshot_blank_area(str(image_path))

        assert result["screenshot_blank_area_ratio"] >= 0.90
        assert result["screenshot_content_occupancy_ratio"] <= 0.10
        assert result["quality_gate"] == "warn"
        assert any("空白" in warning for warning in result["warnings"])

    def test_dense_screenshot_blank_area_passes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            image_path = Path(tmpdir) / "dense.png"
            image = Image.new("RGB", (1280, 720), "white")
            draw = ImageDraw.Draw(image)
            draw.rectangle((120, 90, 1160, 630), fill=(20, 40, 80))
            image.save(image_path)

            result = analyze_screenshot_blank_area(str(image_path))

        assert result["screenshot_blank_area_ratio"] <= 0.40
        assert result["screenshot_content_occupancy_ratio"] >= 0.60
        assert result["quality_gate"] == "pass"
        assert result["warnings"] == []

    def test_detects_underused_content_on_colored_background(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            image_path = Path(tmpdir) / "colored_sparse.png"
            image = Image.new("RGB", (1280, 720), (72, 102, 190))
            draw = ImageDraw.Draw(image)
            draw.rectangle((540, 290, 740, 430), fill=(245, 248, 255))
            image.save(image_path)

            result = analyze_screenshot_blank_area(str(image_path))

        assert result["screenshot_content_occupancy_ratio"] >= 0.90
        assert result["screenshot_visual_content_occupancy_ratio"] <= 0.10
        assert result["screenshot_visual_blank_area_ratio"] >= 0.90
        assert result["quality_gate"] == "warn"
        assert any("背景" in warning or "密度" in warning for warning in result["warnings"])

    def test_dense_content_on_colored_background_passes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            image_path = Path(tmpdir) / "colored_dense.png"
            image = Image.new("RGB", (1280, 720), (72, 102, 190))
            draw = ImageDraw.Draw(image)
            draw.rectangle((120, 90, 1160, 630), fill=(245, 248, 255))
            image.save(image_path)

            result = analyze_screenshot_blank_area(str(image_path))

        assert result["screenshot_visual_content_occupancy_ratio"] >= 0.60
        assert result["screenshot_visual_blank_area_ratio"] <= 0.40
        assert result["quality_gate"] == "pass"
        assert result["warnings"] == []


class TestDesignQualityIntegrationHelpers:
    def test_build_design_quality_metrics_adds_slide_numbers_and_fallback_flags(self):
        html_contents = [
            '''<div class="container" style="width: 1680px; height: 640px">
                <h1 style="font-size: 82px">Title</h1><p style="font-size: 32px">Body</p>
            </div>''',
            '<h1 style="font-size: 72px">Title</h1><p style="font-size: 18px">Tiny</p>',
        ]

        metrics = build_design_quality_metrics(html_contents, fallback_slide_numbers={2})

        assert len(metrics) == 2
        assert metrics[0]["slide_number"] == 1
        assert metrics[0]["fallback_used"] is False
        assert metrics[0]["quality_gate"] == "pass"
        assert metrics[1]["slide_number"] == 2
        assert metrics[1]["fallback_used"] is True
        assert metrics[1]["quality_gate"] in ("fail", "warn")

"""Sprint 15 — title preservation prompt and typography/metric refinements."""

from __future__ import annotations

from services.ai_slide_generator import (
    AI_SELF_REVIEW_PROMPT,
    finalize_generated_html_for_render,
    harden_generated_html_typography,
)
from services.design_quality_metrics import analyze_design_quality, analyze_design_quality_with_browser_layout


def test_self_review_prompt_forbids_rewriting_title_text_meaning_subject_or_ending():
    """Self-review may improve styles, but not user-facing title wording."""
    prompt = AI_SELF_REVIEW_PROMPT

    assert "タイトル文字列" in prompt
    assert "主語" in prompt
    assert "語尾" in prompt
    assert "意味" in prompt
    assert "書き換え" in prompt


def test_harden_generated_html_typography_raises_too_small_titles_to_pass_threshold():
    html = """<!DOCTYPE html><html><head><style>
    h1 { font-size: 48px; }
    .body { font-size: 32px; }
    </style></head><body>
    <h1>音声の流れに合わせて、スライドが自然に繋がること</h1>
    <p class="body">読みやすい本文</p>
    </body></html>"""

    hardened = harden_generated_html_typography(html)
    metrics = analyze_design_quality(hardened)

    assert metrics["title_font_size_px"] >= 72.0
    assert metrics["quality_gate"] == "pass"


def test_harden_generated_html_typography_raises_regular_card_body_text_to_body_minimum():
    html = """<!DOCTYPE html><html><head><style>
    h1 { font-size: 82px; }
    .card-body { font-size: 24px; }
    .card-label { font-size: 14px; }
    .page-number { font-size: 12px; }
    </style></head><body>
    <h1>日本語が読みやすく、自然に繋がること</h1>
    <div class="card-label">01 READABILITY</div>
    <p class="card-body">日本語が読みやすく、余白が詰まりすぎていないこと</p>
    <div class="page-number">02 / 02</div>
    </body></html>"""

    hardened = harden_generated_html_typography(html)
    metrics = analyze_design_quality(hardened)

    assert metrics["body_font_size_px_min"] >= 28.0
    assert metrics["small_text_count"] == 0
    assert metrics["quality_gate"] == "pass"


def test_harden_generated_html_typography_prevents_title_clipping_rules():
    html = """<!DOCTYPE html><html><head><style>
    h1.headline {
      font-size: 82px;
      width: 560px;
      overflow: hidden;
      white-space: nowrap;
      word-break: keep-all;
      text-overflow: clip;
    }
    .body { font-size: 32px; }
    </style></head><body>
    <h1 class="headline">音声からスライド動画を作る流れを確認します</h1>
    <p class="body">品質評価用サンプル</p>
    </body></html>"""

    hardened = harden_generated_html_typography(html)

    assert "white-space: normal" in hardened
    assert "text-wrap: balance" in hardened
    assert "word-break: keep-all" in hardened
    assert "overflow-wrap: anywhere" not in hardened
    assert "font-size: 72px" in hardened
    assert "font-size: 82px" not in hardened
    assert "text-overflow: clip" not in hardened
    assert "white-space: nowrap" not in hardened


def test_harden_generated_html_typography_prevents_browser_japanese_title_one_character_wraps():
    html = """<!DOCTYPE html><html><head><style>
    h1.title { font-size: 96px; width: 520px; word-break: normal; overflow-wrap: anywhere; }
    .body { font-size: 32px; }
    </style></head><body>
    <h1 class="title">日本語の読みやすさと復元確認</h1>
    <p class="body">品質評価用サンプル</p>
    </body></html>"""

    hardened = harden_generated_html_typography(html)

    assert "word-break: keep-all" in hardened
    assert "overflow-wrap: normal" in hardened
    assert "line-break: strict" in hardened
    assert "text-wrap: balance" in hardened
    assert "overflow-wrap: anywhere" not in hardened


def test_harden_generated_html_typography_repairs_bad_japanese_title_breaks():
    html = """<!DOCTYPE html><html><head><style>
    h1.title { font-size: 72px; white-space: normal; }
    .body { font-size: 32px; }
    </style></head><body>
    <h1 class="title">音声からスライ<br/>ド動画を作<br/>る流れを確認します</h1>
    <p class="body">品質評価用サンプル</p>
    </body></html>"""

    hardened = harden_generated_html_typography(html)

    assert "スライ<br" not in hardened
    assert "作<br" not in hardened
    assert "スライド動画" in hardened
    assert "作る流れ" in hardened


def test_harden_generated_html_typography_preserves_intentional_japanese_title_line_breaks():
    html = """<!DOCTYPE html><html><head><style>
    h1.title { font-size: 72px; white-space: normal; }
    .body { font-size: 32px; }
    </style></head><body>
    <h1 class="title">音声からスライ<br/>ド動画を作る<br/>流れを確認します</h1>
    <p class="body">品質評価用サンプル</p>
    </body></html>"""

    hardened = harden_generated_html_typography(html)

    assert "スライ<br" not in hardened
    assert "スライド動画を作る<br/>流れ" in hardened


def test_harden_generated_html_typography_repairs_title_breaks_in_headline_divs():
    html = """<!DOCTYPE html><html><head><style>
    .headline { font-size: 72px; white-space: normal; }
    .body { font-size: 32px; }
    </style></head><body>
    <div class="headline">音声からスライ<br/>ド動画を作<br/>る流れを確認します</div>
    <p class="body">品質評価用サンプル</p>
    </body></html>"""

    hardened = harden_generated_html_typography(html)

    assert "スライ<br" not in hardened
    assert "作<br" not in hardened
    assert "スライド動画" in hardened
    assert "作る流れ" in hardened


def test_finalize_generated_html_for_render_rehardens_self_review_oversized_title():
    html = """<!DOCTYPE html><html><head><style>
    body {
      width: 1920px;
      height: 1080px;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 80px;
      box-sizing: border-box;
    }
    .hero { max-width: 1680px; text-align: center; }
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
    .body { font-size: 32px; }
    </style></head><body>
    <div class="hero"><h1>音声からスライド動画を作る流れ</h1></div>
    <p class="body">品質評価用サンプル</p>
    </body></html>"""

    finalized = finalize_generated_html_for_render(
        html,
        {"title": "音声からスライド動画を作る流れ"},
        1,
        2,
        {},
    )
    metrics = analyze_design_quality_with_browser_layout(finalized)

    assert "font-size: 72px" in finalized
    assert "max-width: 100%" in finalized
    assert metrics["text_clipping_detected"] is False
    assert metrics["quality_gate"] in {"pass", "warn"}
    assert not any("文字がはみ出" in warning for warning in metrics["warnings"])


def test_finalize_generated_html_for_render_wraps_title_only_slide_in_main_content_container():
    html = """<!DOCTYPE html><html><head><style>
    body {
      width: 1920px;
      height: 1080px;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      padding: 80px 120px;
      box-sizing: border-box;
    }
    .eyebrow { font-size: 24px; margin-bottom: 70px; }
    h1 { font-size: 72px; line-height: 1.3; max-width: 100%; text-align: center; }
    .brand { position: absolute; bottom: 56px; left: 80px; font-size: 28px; }
    .slide-number { position: absolute; bottom: 56px; right: 80px; font-size: 18px; }
    </style></head><body>
    <div class="eyebrow">VERIFICATION</div>
    <h1>日本語の読みやすさと<br/>復元確認</h1>
    <div class="brand">CLEAR VOICE</div>
    <div class="slide-number">02 / 02</div>
    </body></html>"""

    finalized = finalize_generated_html_for_render(
        html,
        {"title": "日本語の読みやすさと 復元確認"},
        2,
        2,
        {"_design_mode": "flash_standard"},
    )
    metrics = analyze_design_quality_with_browser_layout(finalized)

    assert "voislide-main-content" in finalized
    assert metrics["main_element_occupancy_ratio"] >= 0.30
    assert metrics["text_clipping_detected"] is False
    assert metrics["quality_gate"] == "pass"


def test_design_quality_ignores_decorative_pseudo_element_labels():
    html = """<!DOCTYPE html><html><head><style>
    h1 { font-size: 82px; }
    .step.active::before { content: 'NOW'; font-size: 12px; }
    .card.highlight::before { content: 'KEY'; font-size: 20px; }
    .brand { font-size: 20px; }
    .key-text { font-size: 32px; }
    .key-text small { font-size: 15px; }
    .card-body { font-size: 28px; }
    </style></head><body>
    <h1>音声からスライド動画を作る流れを確認します</h1>
    <div class="brand">QUIET · PRECISION</div>
    <div class="key-text">大事なポイントは3つあります<small>KEY POINTS</small></div>
    <div class="card-body">話した内容が正しく文字として残ること</div>
    </body></html>"""

    metrics = analyze_design_quality(html)

    assert metrics["small_text_count"] == 0
    assert metrics["quality_gate"] == "pass"


def test_design_quality_ignores_card_labels_but_counts_card_body_text():
    html = """<!DOCTYPE html><html><head><style>
    h1 { font-size: 82px; }
    .card-label { font-size: 14px; }
    .card-body { font-size: 20px; }
    .footer-label { font-size: 12px; }
    .page-number { font-size: 12px; }
    </style></head><body>
    <h1>日本語が読みやすく、自然に繋がること</h1>
    <div class="card-label">01 READABILITY</div>
    <p class="card-body">日本語が読みやすく、余白が詰まりすぎていないこと</p>
    <div class="footer-label">QUALITY ESSENTIALS</div>
    <div class="page-number">02 / 02</div>
    </body></html>"""

    metrics = analyze_design_quality(html)

    assert metrics["small_text_count"] == 1
    assert metrics["quality_gate"] == "fail"
    assert "20px以下" in "\n".join(metrics["warnings"])

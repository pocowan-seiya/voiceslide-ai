"""
Sprint 2 — Design quality metrics.

Extracts font-size declarations from HTML/CSS and evaluates them
against landscape 16:9 thresholds.

Thresholds (px):
  - title/headline:  72+ target, 56 minimum
  - subtitle:        36+ target, 30 minimum
  - body/card text:  32+ target, 28 minimum
  - footnote:        24+ minimum
  - 20px or below:   forbidden for regular text

Supports inline style, <style> blocks, px/rem/em/clamp().
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

# Base size for rem/em → px conversion (browser default)
_BASE_PX = 16.0

# Thresholds
_TITLE_TARGET_PX = 72.0
_TITLE_MIN_PX = 56.0
_SUBTITLE_TARGET_PX = 36.0
_SUBTITLE_MIN_PX = 30.0
_BODY_TARGET_PX = 32.0
_BODY_MIN_PX = 28.0
_FOOTNOTE_MIN_PX = 24.0
_FORBIDDEN_MAX_PX = 20.0  # ≤ 20px regular text is forbidden


# ---------------------------------------------------------------------------
# Font-size extraction
# ---------------------------------------------------------------------------

# Matches: font-size: 32px / 2rem / 1.5em
_RE_FONT_SIZE_SIMPLE = re.compile(
    r"font-size\s*:\s*([\d.]+)\s*(px|rem|em)",
    re.IGNORECASE,
)

# Matches: font-size: clamp(1rem, 2vw, 3rem)
_RE_FONT_SIZE_CLAMP = re.compile(
    r"font-size\s*:\s*clamp\(\s*([\d.]+)\s*(px|rem|em)\s*,",
    re.IGNORECASE,
)

_RE_STYLE_BLOCK = re.compile(r"<style[^>]*>(.*?)</style>", re.IGNORECASE | re.DOTALL)
_RE_CSS_RULE = re.compile(r"([^{}]+)\{([^{}]*)\}", re.DOTALL)
_RE_CSS_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
_RE_START_TAG = re.compile(
    r"<([a-zA-Z][\w:-]*)([^>]*)>",
    re.IGNORECASE | re.DOTALL,
)
_RE_STYLE_ATTR = re.compile(r"style\s*=\s*(['\"])(.*?)\1", re.IGNORECASE | re.DOTALL)
_RE_CLASS_ATTR = re.compile(r"class\s*=\s*(['\"])(.*?)\1", re.IGNORECASE | re.DOTALL)
_RE_ID_ATTR = re.compile(r"id\s*=\s*(['\"])(.*?)\1", re.IGNORECASE | re.DOTALL)
_RE_WIDTH_DECL = re.compile(r"(?:^|[;\s])width\s*:\s*([\d.]+)\s*(px|rem|em|%|vw|vh)", re.IGNORECASE)
_RE_HEIGHT_DECL = re.compile(r"(?:^|[;\s])height\s*:\s*([\d.]+)\s*(px|rem|em|%|vw|vh)", re.IGNORECASE)
_RE_MAX_WIDTH_DECL = re.compile(r"(?:^|[;\s])max-width\s*:\s*([\d.]+)\s*(px|rem|em|%|vw|vh)", re.IGNORECASE)
_RE_MIN_HEIGHT_DECL = re.compile(r"(?:^|[;\s])min-height\s*:\s*([\d.]+)\s*(px|rem|em|%|vw|vh)", re.IGNORECASE)

_CANVAS_WIDTH_PX = 1280.0
_CANVAS_HEIGHT_PX = 720.0
_CANVAS_AREA_PX = _CANVAS_WIDTH_PX * _CANVAS_HEIGHT_PX
_MAIN_OCCUPANCY_MIN = 0.30
_SCREENSHOT_CONTENT_OCCUPANCY_MIN = 0.30
_SCREENSHOT_VISUAL_CONTENT_OCCUPANCY_MIN = 0.10
_SCREENSHOT_BLANK_RGB_THRESHOLD = 245
_SCREENSHOT_BACKGROUND_DIFF_THRESHOLD = 45

_NON_CONTENT_SELECTORS = (
    "body",
    "html",
    "*",
    ":root",
)
_NON_CONTENT_CLASS_OR_ID_PARTS = (
    "slide-number",
    "page-number",
    # Decorative/supporting labels should not fail a readable slide.
    # They are intentionally small visual chrome, not body copy.
    "decorative",
    "footer",
    "caption",
    "supplemental",
    "section-label",
    "eyebrow",
    "kicker",
    "badge",
    "meta",
    # Sprint 15: card/step labels are supporting navigation chrome. The
    # accompanying Japanese explanation/body text must still be evaluated.
    "card-label",
    "point-label",
    "step-label",
    "stat-label",
    "brand",
    "key-text small",
    "key-message small",
)
_OCCUPANCY_DECORATIVE_CLASS_OR_ID_PARTS = (
    "background",
    "bg-",
    "-bg",
    "glow",
    "circle",
    "wave",
    "grid",
    "accent",
    "underline",
    "corner",
    "dot",
    "line-",
    "-line",
)
_OCCUPANCY_WRAPPER_CLASS_OR_ID_PARTS = (
    "slide",
    "canvas",
    "wrapper",
)


def _to_px(value: float, unit: str) -> float:
    """Convert a CSS length value to approximate px."""
    unit = unit.lower()
    if unit == "px":
        return value
    if unit in ("rem", "em"):
        return value * _BASE_PX
    return value  # fallback: treat as px


def analyze_font_sizes(html: str) -> List[float]:
    """Extract all font-size values from HTML/CSS as px floats.

    Scans both inline ``style="..."`` attributes and ``<style>`` blocks.
    For ``clamp()``, extracts the **lower bound** (first argument).
    """
    if not html:
        return []

    sizes: List[float] = []

    # Simple font-size declarations
    for m in _RE_FONT_SIZE_SIMPLE.finditer(html):
        val = float(m.group(1))
        unit = m.group(2)
        sizes.append(_to_px(val, unit))

    # clamp() lower bounds
    for m in _RE_FONT_SIZE_CLAMP.finditer(html):
        val = float(m.group(1))
        unit = m.group(2)
        sizes.append(_to_px(val, unit))

    return sizes


def _font_sizes_from_declarations(css: str) -> List[float]:
    """Extract font sizes from a CSS declaration block."""
    sizes: List[float] = []
    for m in _RE_FONT_SIZE_SIMPLE.finditer(css):
        sizes.append(_to_px(float(m.group(1)), m.group(2)))
    for m in _RE_FONT_SIZE_CLAMP.finditer(css):
        sizes.append(_to_px(float(m.group(1)), m.group(2)))
    return sizes


def _normalize_css_selector(selector: str) -> str:
    """Remove leading CSS comments that appear before real selectors."""
    return _RE_CSS_COMMENT.sub(" ", selector).strip()


def _is_non_content_selector(selector: str) -> bool:
    """Return True when every selector is page default or slide chrome."""
    selector = _normalize_css_selector(selector)
    selectors = [s.strip().lower() for s in selector.split(",") if s.strip()]
    if not selectors:
        return False
    return all(
        item in _NON_CONTENT_SELECTORS
        or "::before" in item
        or "::after" in item
        or any(part in item for part in _NON_CONTENT_CLASS_OR_ID_PARTS)
        for item in selectors
    )


def _attrs_have_non_content_marker(attrs: str) -> bool:
    """Detect inline styles on known slide chrome elements."""
    class_match = _RE_CLASS_ATTR.search(attrs)
    if class_match:
        classes = class_match.group(2).lower()
        if any(part in classes for part in _NON_CONTENT_CLASS_OR_ID_PARTS):
            return True

    id_match = _RE_ID_ATTR.search(attrs)
    if id_match:
        el_id = id_match.group(2).lower()
        if any(part in el_id for part in _NON_CONTENT_CLASS_OR_ID_PARTS):
            return True

    return False


def _selector_matches_attrs(selector: str, attrs: str) -> bool:
    """Match simple class/id CSS selectors against one element's attributes.

    This intentionally supports only deterministic, low-risk selectors for the
    first HTML/CSS occupancy pass. Complex layout inference belongs in a later
    screenshot/browser sprint.
    """
    class_match = _RE_CLASS_ATTR.search(attrs)
    classes = set(class_match.group(2).lower().split()) if class_match else set()
    id_match = _RE_ID_ATTR.search(attrs)
    el_id = id_match.group(2).lower() if id_match else ""

    for raw_selector in _normalize_css_selector(selector).split(","):
        item = raw_selector.strip().lower()
        if not item or item in _NON_CONTENT_SELECTORS:
            continue
        # Keep this first pass conservative: use the target part before
        # descendant/pseudo-class syntax, e.g. `.hero` from `.hero h1`.
        item = item.split()[0]
        item = item.split(":", 1)[0]
        if item.startswith(".") and item[1:] in classes:
            return True
        if item.startswith("#") and item[1:] == el_id:
            return True
    return False


def _has_occupancy_decorative_marker(text: str) -> bool:
    lowered = text.lower()
    return any(part in lowered for part in _OCCUPANCY_DECORATIVE_CLASS_OR_ID_PARTS)


def _attrs_have_occupancy_decorative_marker(attrs: str) -> bool:
    class_match = _RE_CLASS_ATTR.search(attrs)
    if class_match and _has_occupancy_decorative_marker(class_match.group(2)):
        return True
    id_match = _RE_ID_ATTR.search(attrs)
    if id_match and _has_occupancy_decorative_marker(id_match.group(2)):
        return True
    return False


def _has_occupancy_wrapper_marker(text: str) -> bool:
    lowered = text.lower()
    return any(part in lowered for part in _OCCUPANCY_WRAPPER_CLASS_OR_ID_PARTS)


def _attrs_have_occupancy_wrapper_marker(attrs: str) -> bool:
    class_match = _RE_CLASS_ATTR.search(attrs)
    if class_match and _has_occupancy_wrapper_marker(class_match.group(2)):
        return True
    id_match = _RE_ID_ATTR.search(attrs)
    if id_match and _has_occupancy_wrapper_marker(id_match.group(2)):
        return True
    return False


def _analyze_content_font_sizes(html: str) -> List[float]:
    """Extract font sizes that should participate in the quality gate.

    Raw ``analyze_font_sizes`` intentionally reports every declaration. The
    gate needs a narrower view so global defaults and slide counters do not
    create false failures for otherwise readable slides.
    """
    if not html:
        return []

    sizes: List[float] = []

    for style_match in _RE_STYLE_BLOCK.finditer(html):
        css = style_match.group(1)
        for rule_match in _RE_CSS_RULE.finditer(css):
            selector = _normalize_css_selector(rule_match.group(1))
            declarations = rule_match.group(2)
            if _is_non_content_selector(selector):
                continue
            sizes.extend(_font_sizes_from_declarations(declarations))

    html_without_style_blocks = _RE_STYLE_BLOCK.sub("", html)
    for tag_match in _RE_START_TAG.finditer(html_without_style_blocks):
        attrs = tag_match.group(2)
        style_match = _RE_STYLE_ATTR.search(attrs)
        if not style_match:
            continue
        inline_style = style_match.group(2)
        if _attrs_have_non_content_marker(attrs):
            continue
        sizes.extend(_font_sizes_from_declarations(inline_style))

    return sizes


def _css_length_to_px(value: float, unit: str, axis_px: float) -> Optional[float]:
    """Convert width/height declarations to px for a 1280x720 landscape canvas."""
    unit = unit.lower()
    if unit == "%":
        return axis_px * value / 100.0
    if unit == "vw":
        return _CANVAS_WIDTH_PX * value / 100.0
    if unit == "vh":
        return _CANVAS_HEIGHT_PX * value / 100.0
    return _to_px(value, unit)


def _extract_dimension_px(
    style: str,
    primary_regex: re.Pattern[str],
    axis_px: float,
    fallback_regex: Optional[re.Pattern[str]] = None,
) -> Optional[float]:
    match = primary_regex.search(style)
    if not match and fallback_regex is not None:
        match = fallback_regex.search(style)
    if not match:
        return None
    return _css_length_to_px(float(match.group(1)), match.group(2), axis_px)


def _estimate_main_element_occupancy_ratio(html: str) -> Optional[float]:
    """Estimate the largest content element occupancy from HTML/CSS dimensions.

    This deterministic HTML/CSS-only estimate intentionally avoids screenshot
    analysis. It returns a ratio only when a content element exposes both width
    and height through inline styles or a matching simple class/id rule from a
    ``<style>`` block; otherwise it returns None rather than guessing.
    """
    if not html:
        return None

    max_area = 0.0
    css_dimension_rules: List[tuple[str, float, float]] = []
    for style_match in _RE_STYLE_BLOCK.finditer(html):
        css = style_match.group(1)
        for rule_match in _RE_CSS_RULE.finditer(css):
            selector = _normalize_css_selector(rule_match.group(1))
            declarations = rule_match.group(2)
            if (
                _is_non_content_selector(selector)
                or _has_occupancy_decorative_marker(selector)
                or _has_occupancy_wrapper_marker(selector)
            ):
                continue
            width = _extract_dimension_px(declarations, _RE_WIDTH_DECL, _CANVAS_WIDTH_PX, _RE_MAX_WIDTH_DECL)
            height = _extract_dimension_px(declarations, _RE_HEIGHT_DECL, _CANVAS_HEIGHT_PX, _RE_MIN_HEIGHT_DECL)
            if width is None or height is None:
                continue
            if width <= 0 or height <= 0:
                continue
            css_dimension_rules.append((selector, width, height))

    html_without_style_blocks = _RE_STYLE_BLOCK.sub("", html)
    for tag_match in _RE_START_TAG.finditer(html_without_style_blocks):
        attrs = tag_match.group(2)
        if (
            _attrs_have_non_content_marker(attrs)
            or _attrs_have_occupancy_decorative_marker(attrs)
            or _attrs_have_occupancy_wrapper_marker(attrs)
        ):
            continue

        style_match = _RE_STYLE_ATTR.search(attrs)
        if style_match:
            inline_style = style_match.group(2)
            width = _extract_dimension_px(inline_style, _RE_WIDTH_DECL, _CANVAS_WIDTH_PX, _RE_MAX_WIDTH_DECL)
            height = _extract_dimension_px(inline_style, _RE_HEIGHT_DECL, _CANVAS_HEIGHT_PX, _RE_MIN_HEIGHT_DECL)
            if width is not None and height is not None and width > 0 and height > 0:
                max_area = max(max_area, min(width * height, _CANVAS_AREA_PX))

        for selector, width, height in css_dimension_rules:
            if _selector_matches_attrs(selector, attrs):
                max_area = max(max_area, min(width * height, _CANVAS_AREA_PX))

    if max_area <= 0:
        return None
    return round(max_area / _CANVAS_AREA_PX, 6)


def analyze_screenshot_blank_area(image_path: str) -> Dict[str, Any]:
    """Estimate blank/content area from a rendered slide screenshot.

    The near-white metric catches obvious white-background blank space. The
    background-difference metric catches the next failure mode: a colored or
    gradient-like background filling the canvas while the actual foreground
    content remains too small.
    """
    warnings: List[str] = []
    path = Path(image_path)
    if not path.exists():
        return {
            "screenshot_blank_area_ratio": None,
            "screenshot_content_occupancy_ratio": None,
            "screenshot_visual_blank_area_ratio": None,
            "screenshot_visual_content_occupancy_ratio": None,
            "quality_gate": "warn",
            "warnings": [f"スクリーンショットが見つかりません: {image_path}"],
        }

    try:
        from PIL import Image
    except Exception:
        return {
            "screenshot_blank_area_ratio": None,
            "screenshot_content_occupancy_ratio": None,
            "screenshot_visual_blank_area_ratio": None,
            "screenshot_visual_content_occupancy_ratio": None,
            "quality_gate": "warn",
            "warnings": ["Pillowが利用できないためスクリーンショット空白率を計測できません。"],
        }

    with Image.open(path) as image:
        rgba = image.convert("RGBA")
        width, height = rgba.size
        if width <= 0 or height <= 0:
            return {
                "screenshot_blank_area_ratio": None,
                "screenshot_content_occupancy_ratio": None,
                "screenshot_visual_blank_area_ratio": None,
                "screenshot_visual_content_occupancy_ratio": None,
                "quality_gate": "warn",
                "warnings": ["スクリーンショットのサイズが不正です。"],
            }

        total = width * height
        threshold = _SCREENSHOT_BLANK_RGB_THRESHOLD
        diff_threshold = _SCREENSHOT_BACKGROUND_DIFF_THRESHOLD
        pixels = list(rgba.getdata())

        corner_points = (
            rgba.getpixel((0, 0)),
            rgba.getpixel((width - 1, 0)),
            rgba.getpixel((0, height - 1)),
            rgba.getpixel((width - 1, height - 1)),
        )
        opaque_corners = [pixel for pixel in corner_points if pixel[3] > 8]
        if opaque_corners:
            background_rgb = tuple(
                sum(pixel[index] for pixel in opaque_corners) / len(opaque_corners)
                for index in range(3)
            )
        else:
            background_rgb = (255.0, 255.0, 255.0)

        content_pixels = 0
        visual_content_pixels = 0
        for r, g, b, a in pixels:
            if a <= 8:
                continue
            if not (r >= threshold and g >= threshold and b >= threshold):
                content_pixels += 1

            background_diff = abs(r - background_rgb[0]) + abs(g - background_rgb[1]) + abs(b - background_rgb[2])
            if background_diff >= diff_threshold:
                visual_content_pixels += 1

    content_ratio = round(content_pixels / total, 6)
    blank_ratio = round(1.0 - content_ratio, 6)
    visual_content_ratio = round(visual_content_pixels / total, 6)
    visual_blank_ratio = round(1.0 - visual_content_ratio, 6)
    gate = "pass"
    if content_ratio < _SCREENSHOT_CONTENT_OCCUPANCY_MIN:
        gate = "warn"
        warnings.append(
            f"スクリーンショット上の空白率が{blank_ratio:.2f}です。"
            f"主な表示要素は{_SCREENSHOT_CONTENT_OCCUPANCY_MIN:.2f}以上の面積利用が目標です。"
        )
    if visual_content_ratio < _SCREENSHOT_VISUAL_CONTENT_OCCUPANCY_MIN:
        gate = "warn"
        warnings.append(
            f"背景との差分で見た表示密度が{visual_content_ratio:.2f}です。"
            f"主な表示要素は{_SCREENSHOT_VISUAL_CONTENT_OCCUPANCY_MIN:.2f}以上の密度が目標です。"
        )

    return {
        "screenshot_blank_area_ratio": blank_ratio,
        "screenshot_content_occupancy_ratio": content_ratio,
        "screenshot_visual_blank_area_ratio": visual_blank_ratio,
        "screenshot_visual_content_occupancy_ratio": visual_content_ratio,
        "quality_gate": gate,
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# Quality analysis
# ---------------------------------------------------------------------------


def _estimate_main_element_occupancy_ratio_with_browser(html: str) -> Optional[float]:
    """Measure the largest likely content group after browser layout.

    This is intentionally separate from the deterministic HTML/CSS-only metric.
    It uses Chromium's computed layout for cases where width is declared but
    height is auto. To avoid a full-slide wrapper masking underused content, it
    only considers likely content containers and skips body/html/slide chrome.
    """
    if not html:
        return None

    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        return None

    candidate_markers = (
        "main",
        "content",
        "hero",
        "card",
        "container",
        "layout",
        "frame",
        "stage",
        "panel",
        "message",
    )
    wrapper_markers = (
        "slide",
        "background",
        "bg-",
        "-bg",
        "wrapper",
        "canvas",
    )

    script = r"""
    ({ candidateMarkers, wrapperMarkers, canvasWidth, canvasHeight, decorativeMarkers }) => {
      const canvasArea = canvasWidth * canvasHeight;
      const elements = Array.from(document.body.querySelectorAll('*'));
      let maxArea = 0;

      for (const el of elements) {
        const tag = el.tagName.toLowerCase();
        if (['html', 'body', 'style', 'script', 'svg', 'path'].includes(tag)) continue;

        const markerText = `${el.className || ''} ${el.id || ''}`.toLowerCase();
        if (decorativeMarkers.some(marker => markerText.includes(marker))) continue;
        if (wrapperMarkers.some(marker => markerText.includes(marker)) && !candidateMarkers.some(marker => markerText.includes(marker))) continue;
        if (!candidateMarkers.some(marker => markerText.includes(marker)) && !['main', 'article'].includes(tag)) continue;

        const rect = el.getBoundingClientRect();
        if (!Number.isFinite(rect.width) || !Number.isFinite(rect.height)) continue;
        if (rect.width <= 0 || rect.height <= 0) continue;

        const style = window.getComputedStyle(el);
        if (style.display === 'none' || style.visibility === 'hidden' || Number(style.opacity || '1') === 0) continue;

        const text = (el.textContent || '').replace(/\s+/g, ' ').trim();
        if (text.length === 0) continue;

        const area = Math.min(rect.width * rect.height, canvasArea);
        maxArea = Math.max(maxArea, area);
      }

      if (maxArea <= 0) return null;
      return Math.round((maxArea / canvasArea) * 1000000) / 1000000;
    }
    """

    browser = None
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
            page = browser.new_page(viewport={"width": int(_CANVAS_WIDTH_PX), "height": int(_CANVAS_HEIGHT_PX)})
            page.set_content(html, wait_until="load")
            try:
                page.evaluate("document.fonts ? document.fonts.ready : Promise.resolve()")
            except Exception:
                pass
            page.wait_for_timeout(100)
            ratio = page.evaluate(
                script,
                {
                    "candidateMarkers": list(candidate_markers),
                    "wrapperMarkers": list(wrapper_markers),
                    "canvasWidth": _CANVAS_WIDTH_PX,
                    "canvasHeight": _CANVAS_HEIGHT_PX,
                    "decorativeMarkers": list(_OCCUPANCY_DECORATIVE_CLASS_OR_ID_PARTS),
                },
            )
            browser.close()
            browser = None
            if ratio is None:
                return None
            return float(ratio)
    except Exception:
        return None


def _detect_title_clipping_with_browser(html: str) -> bool:
    """Detect title elements whose rendered text overflows their layout box."""
    if not html:
        return False

    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        return False

    script = r"""
    () => {
      const titleSelector = 'h1, h2, .title, .headline, .main-title';
      const titles = Array.from(document.querySelectorAll(titleSelector));
      for (const el of titles) {
        const text = (el.textContent || '').replace(/\s+/g, '').trim();
        if (text.length < 4) continue;
        const rect = el.getBoundingClientRect();
        if (!Number.isFinite(rect.width) || !Number.isFinite(rect.height)) continue;
        if (rect.width <= 0 || rect.height <= 0) continue;
        const style = window.getComputedStyle(el);
        if (style.display === 'none' || style.visibility === 'hidden' || Number(style.opacity || '1') === 0) continue;
        const horizontalOverflow = el.scrollWidth > el.clientWidth + 4;
        const verticalTolerance = Math.max(6, Math.ceil(el.clientHeight * 0.04));
        const verticalOverflow = el.scrollHeight > el.clientHeight + verticalTolerance;
        if (horizontalOverflow || verticalOverflow) return true;
      }
      return false;
    }
    """

    browser = None
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
            page = browser.new_page(viewport={"width": int(_CANVAS_WIDTH_PX), "height": int(_CANVAS_HEIGHT_PX)})
            page.set_content(html, wait_until="load")
            try:
                page.evaluate("document.fonts ? document.fonts.ready : Promise.resolve()")
            except Exception:
                pass
            page.wait_for_timeout(100)
            detected = bool(page.evaluate(script))
            browser.close()
            browser = None
            return detected
    except Exception:
        return False


def analyze_design_quality_with_browser_layout(
    html: str,
    fallback_used: bool = False,
) -> Dict[str, Any]:
    """Analyze design quality, filling browser-derived layout warnings."""
    result = analyze_design_quality(html, fallback_used=fallback_used)

    title_clipping_detected = _detect_title_clipping_with_browser(html)
    if title_clipping_detected:
        result["text_clipping_detected"] = True
        if result.get("quality_gate") == "pass":
            result["quality_gate"] = "warn"
        result.setdefault("warnings", []).append(
            "タイトル要素の横幅または高さが不足し、ブラウザ描画で文字がはみ出しています。"
        )

    static_occupancy_ratio = result.get("main_element_occupancy_ratio")
    if static_occupancy_ratio is not None and static_occupancy_ratio >= _MAIN_OCCUPANCY_MIN:
        return result

    occupancy_ratio = _estimate_main_element_occupancy_ratio_with_browser(html)
    if occupancy_ratio is None:
        return result

    if static_occupancy_ratio is not None and occupancy_ratio <= static_occupancy_ratio:
        return result

    result["main_element_occupancy_ratio"] = occupancy_ratio
    result["blank_area_ratio_estimate"] = round(1.0 - occupancy_ratio, 6)

    existing_warnings = result.setdefault("warnings", [])
    result["warnings"] = [
        warning
        for warning in existing_warnings
        if "主役要素の画面占有率" not in warning
    ]

    if occupancy_ratio < _MAIN_OCCUPANCY_MIN:
        if result.get("quality_gate") == "pass":
            result["quality_gate"] = "warn"
        result.setdefault("warnings", []).append(
            f"主役要素の画面占有率が{occupancy_ratio:.2f}です。"
            f"目標は{_MAIN_OCCUPANCY_MIN:.2f}以上です。"
        )
    elif result.get("quality_gate") == "warn" and not result.get("warnings"):
        result["quality_gate"] = "pass"

    return result


def analyze_design_quality(
    html: str,
    fallback_used: bool = False,
) -> Dict[str, Any]:
    """Analyze HTML slide for design quality.

    Returns a dict with:
      - min_font_size_px
      - title_font_size_px  (largest detected size)
      - body_font_size_px_min  (smallest detected size excluding title)
      - small_text_count  (count of sizes ≤ 20px)
      - fallback_used
      - quality_gate  ("pass" | "warn" | "fail")
      - warnings  (list of human-readable strings)
    """
    sizes = _analyze_content_font_sizes(html)
    occupancy_ratio = _estimate_main_element_occupancy_ratio(html)
    blank_area_ratio = round(1.0 - occupancy_ratio, 6) if occupancy_ratio is not None else None
    warnings: List[str] = []
    gate = "pass"

    if not sizes:
        return {
            "min_font_size_px": None,
            "title_font_size_px": None,
            "body_font_size_px_min": None,
            "main_element_occupancy_ratio": occupancy_ratio,
            "blank_area_ratio_estimate": blank_area_ratio,
            "text_clipping_detected": False,
            "small_text_count": 0,
            "fallback_used": fallback_used,
            "quality_gate": "pass",
            "warnings": [],
        }

    sorted_sizes = sorted(sizes)
    min_size = sorted_sizes[0]
    max_size = sorted_sizes[-1]

    # Title = largest font size found
    title_size = max_size
    # Body min = smallest normal/body-sized text. A 24px footnote is allowed
    # when the slide also has real body text at 28px+.
    body_candidates = [s for s in sizes if s >= _BODY_MIN_PX]
    body_min = min(body_candidates) if body_candidates else min_size

    # Count forbidden small text (≤ 20px)
    small_text_count = sum(1 for s in sizes if s <= _FORBIDDEN_MAX_PX)

    # --- Quality gate rules ---

    # FAIL: any text ≤ 20px
    if small_text_count > 0:
        gate = "fail"
        warnings.append(
            f"{small_text_count}個のフォントサイズが20px以下です（最小: {min_size}px）。"
            f"通常テキストで20px以下は禁止です。"
        )

    # FAIL: body text below absolute minimum (28px)
    if body_min < _BODY_MIN_PX and gate != "fail":
        if body_min <= _FORBIDDEN_MAX_PX:
            gate = "fail"
        else:
            gate = "warn"
        warnings.append(
            f"本文フォントサイズが{body_min}pxです。最低{_BODY_MIN_PX}px必要です。"
        )

    # WARN: title below target (72px) but above minimum (56px)
    if title_size < _TITLE_TARGET_PX:
        if title_size < _TITLE_MIN_PX:
            if gate != "fail":
                gate = "fail"
            warnings.append(
                f"タイトルフォントサイズが{title_size}pxです。最低{_TITLE_MIN_PX}px必要です。"
            )
        elif gate == "pass":
            gate = "warn"
            warnings.append(
                f"タイトルフォントサイズが{title_size}pxです。目標は{_TITLE_TARGET_PX}px以上です。"
            )

    # WARN: detectable main content group uses too little of the 16:9 canvas.
    # This catches the common failure mode: a small centered card with readable
    # text, surrounded by plain empty space. If dimensions are not declared, we
    # leave screenshot-based occupancy to a later QA sprint instead of guessing.
    if occupancy_ratio is not None and occupancy_ratio < _MAIN_OCCUPANCY_MIN and gate == "pass":
        gate = "warn"
        warnings.append(
            f"主役要素の画面占有率が{occupancy_ratio:.2f}です。"
            f"目標は{_MAIN_OCCUPANCY_MIN:.2f}以上です。"
        )

    return {
        "min_font_size_px": min_size,
        "title_font_size_px": title_size,
        "body_font_size_px_min": body_min,
        "main_element_occupancy_ratio": occupancy_ratio,
        "blank_area_ratio_estimate": blank_area_ratio,
        "text_clipping_detected": False,
        "small_text_count": small_text_count,
        "fallback_used": fallback_used,
        "quality_gate": gate,
        "warnings": warnings,
    }

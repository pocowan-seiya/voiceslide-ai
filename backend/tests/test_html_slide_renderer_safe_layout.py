import asyncio

from playwright.async_api import async_playwright

from services.html_slide_renderer import _apply_render_safe_text_layout


def test_apply_render_safe_text_layout_moves_bottom_heavy_headline_inside_canvas():
    async def run():
        html = """<!doctype html><html><head><style>
        body { width: 1920px; height: 1080px; margin: 0; overflow: hidden; position: relative; }
        .headline {
            position: absolute;
            left: 140px;
            top: 930px;
            width: 1640px;
            font-size: 96px;
            line-height: 1.18;
            font-weight: 900;
        }
        </style></head><body>
            <div class="headline">大切なのは、売り込みっぽいページではなく、その人のサービスの温度感が伝わることです</div>
        </body></html>"""

        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page(viewport={"width": 1920, "height": 1080})
            await page.set_content(html)
            before = await page.eval_on_selector(
                ".headline",
                "el => { const r = el.getBoundingClientRect(); return { bottom: r.bottom }; }",
            )
            await _apply_render_safe_text_layout(page, 1920, 1080)
            after = await page.eval_on_selector(
                ".headline",
                "el => { const r = el.getBoundingClientRect(); return { bottom: r.bottom, adjusted: el.dataset.voislideRenderSafeAdjusted, fontSize: getComputedStyle(el).fontSize }; }",
            )
            await browser.close()
            return before, after

    before, after = asyncio.run(run())

    assert before["bottom"] > 1080
    assert after["bottom"] <= 1048
    assert float(after["fontSize"].replace("px", "")) < 96


def test_apply_render_safe_text_layout_ignores_slide_number_chrome():
    async def run():
        html = """<!doctype html><html><head><style>
        body { width: 1920px; height: 1080px; margin: 0; overflow: hidden; position: relative; }
        .slide-number {
            position: absolute;
            right: -20px;
            bottom: -20px;
            font-size: 44px;
        }
        </style></head><body>
            <div class="slide-number">05 / 10</div>
        </body></html>"""

        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page(viewport={"width": 1920, "height": 1080})
            await page.set_content(html)
            await _apply_render_safe_text_layout(page, 1920, 1080)
            adjusted = await page.eval_on_selector(
                ".slide-number",
                "el => el.dataset.voislideRenderSafeAdjusted || ''",
            )
            await browser.close()
            return adjusted

    assert asyncio.run(run()) == ""

"""
VoiceSlide AI - Slide Renderer
Uses Playwright to render HTML templates to high-quality PNG images
"""

import os
import asyncio
from typing import List, Dict, Any
from playwright.async_api import async_playwright

from services.slide_templates import render_template
from config import OUTPUT_DIR, VIDEO_WIDTH, VIDEO_HEIGHT


async def render_slide_to_image(html_content: str, output_path: str) -> str:
    """
    Render HTML content to PNG image using Playwright
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        
        page = await browser.new_page(
            viewport={"width": VIDEO_WIDTH, "height": VIDEO_HEIGHT}
        )
        
        # Set content and wait for fonts to load
        await page.set_content(html_content)
        await page.wait_for_timeout(500)  # Wait for fonts/styles
        
        # Take screenshot
        await page.screenshot(path=output_path, type="png")
        
        await browser.close()
    
    return output_path


async def render_all_slides(slides: List[Dict[str, Any]], job_id: str) -> List[str]:
    """
    Render all slides to images
    """
    slides_dir = os.path.join(OUTPUT_DIR, f"{job_id}_slides")
    os.makedirs(slides_dir, exist_ok=True)
    
    image_paths = []
    total_slides = len(slides)
    
    for i, slide in enumerate(slides):
        # Determine template type
        template_type = determine_template_type(slide)
        
        # Prepare slide data
        slide_data = prepare_slide_data(slide, i + 1, total_slides)
        
        # Render HTML
        html_content = render_template(template_type, slide_data)
        
        # Save to image
        output_path = os.path.join(slides_dir, f"slide_{i+1:03d}.png")
        await render_slide_to_image(html_content, output_path)
        
        image_paths.append(output_path)
    
    return image_paths


def determine_template_type(slide: Dict[str, Any]) -> str:
    """
    Determine the best template type based on slide content
    """
    slide_type = slide.get("template_type", "")
    
    if slide_type:
        return slide_type
    
    # Auto-detect based on content
    title = slide.get("title", "")
    points = slide.get("points", [])
    stages = slide.get("stages", [])
    steps = slide.get("steps", [])
    columns = slide.get("columns", [])
    before = slide.get("before", {})
    
    # Check for specific content patterns
    if stages:
        return "flow"
    
    if steps and len(steps) == 4:
        return "four_steps"
    
    if columns and len(columns) == 3:
        return "three_columns"
    
    if before:
        return "comparison"
    
    if slide.get("is_title", False) or not points:
        return "title"
    
    if slide.get("has_image", False):
        return "content_image"
    
    return "key_points"


def prepare_slide_data(slide: Dict[str, Any], slide_number: int, total_slides: int) -> Dict[str, Any]:
    """
    Prepare and enrich slide data for rendering
    """
    data = slide.copy()
    data["slide_number"] = f"{slide_number:02d}"
    
    # Ensure required fields exist
    if "section" not in data:
        data["section"] = ""
    
    if "subtitle" not in data:
        data["subtitle"] = ""
    
    # Convert simple points to structured format if needed
    if "points" in data and isinstance(data["points"], list):
        if data["points"] and isinstance(data["points"][0], str):
            # Convert string points to structured points for content_image template
            structured_points = []
            icons = ["🎯", "💡", "⚡", "✨"]
            for i, point in enumerate(data["points"]):
                structured_points.append({
                    "icon": icons[i % len(icons)],
                    "title": point,
                    "description": ""
                })
            data["structured_points"] = structured_points
    
    return data


async def render_single_slide(
    slide: Dict[str, Any],
    job_id: str,
    slide_number: int,
    total_slides: int
) -> str:
    """
    Render a single slide (for preview purposes)
    """
    slides_dir = os.path.join(OUTPUT_DIR, f"{job_id}_slides")
    os.makedirs(slides_dir, exist_ok=True)
    
    template_type = determine_template_type(slide)
    slide_data = prepare_slide_data(slide, slide_number, total_slides)
    html_content = render_template(template_type, slide_data)
    
    output_path = os.path.join(slides_dir, f"slide_{slide_number:03d}.png")
    await render_slide_to_image(html_content, output_path)
    
    return output_path

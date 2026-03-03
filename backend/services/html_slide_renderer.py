"""
VoiceSlide AI - HTML Slide Renderer
Renders HTML slides to PNG images using Playwright
"""

import os
import base64
from typing import Dict, Any, List, Optional
from io import BytesIO
from PIL import Image

from config import OUTPUT_DIR, VIDEO_WIDTH, VIDEO_HEIGHT


# HTML template with embedded CSS
BASE_HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;700;900&display=swap" rel="stylesheet">
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            width: {width}px;
            height: {height}px;
            font-family: 'Noto Sans JP', sans-serif;
            background: {background};
            color: {text_color};
            overflow: hidden;
            position: relative;
        }}
        
        .background-image {{
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            object-fit: cover;
            opacity: 0.4;
            z-index: 0;
        }}
        
        .overlay {{
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: linear-gradient(135deg, rgba(0,0,0,0.6) 0%, rgba(0,0,0,0.3) 100%);
            z-index: 1;
        }}
        
        .content {{
            position: relative;
            z-index: 2;
            width: 100%;
            height: 100%;
            padding: 60px 80px;
            display: flex;
            flex-direction: column;
        }}
        
        .section-label {{
            font-size: 14px;
            font-weight: 500;
            text-transform: uppercase;
            letter-spacing: 3px;
            color: {accent_color};
            margin-bottom: 12px;
        }}
        
        .title {{
            font-size: 48px;
            font-weight: 900;
            line-height: 1.2;
            margin-bottom: 20px;
        }}
        
        .title .emphasis {{
            color: {primary_color};
        }}
        
        .subtitle {{
            font-size: 20px;
            font-weight: 400;
            color: {text_secondary};
            margin-bottom: 40px;
        }}
        
        .slide-number {{
            display: none;  /* Hidden per user request */
            position: absolute;
            bottom: 30px;
            right: 40px;
            font-size: 14px;
            color: {text_secondary};
        }}
        
        /* Layout: Three Columns */
        .columns-container {{
            display: flex;
            gap: 30px;
            flex: 1;
            align-items: center;
        }}
        
        .column-card {{
            flex: 1;
            background: rgba(255,255,255,0.05);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 20px;
            padding: 40px 30px;
            text-align: center;
            position: relative;
        }}
        
        .column-card::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 50%;
            transform: translateX(-50%);
            width: 60%;
            height: 4px;
            background: linear-gradient(90deg, {primary_color}, {secondary_color});
            border-radius: 0 0 4px 4px;
        }}
        
        .column-icon {{
            font-size: 48px;
            margin-bottom: 20px;
            display: flex;
            justify-content: center;
            align-items: center;
            width: 80px;
            height: 80px;
            background: rgba(255,255,255,0.1);
            border-radius: 50%;
            margin: 0 auto 20px;
        }}
        
        .column-title {{
            font-size: 24px;
            font-weight: 700;
            margin-bottom: 10px;
        }}
        
        .column-subtitle {{
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 2px;
            color: {text_secondary};
            margin-bottom: 20px;
        }}
        
        .column-description {{
            font-size: 14px;
            line-height: 1.8;
            color: {text_secondary};
        }}
        
        /* Layout: Flow */
        .flow-container {{
            display: flex;
            align-items: center;
            justify-content: center;
            flex: 1;
            gap: 20px;
        }}
        
        .flow-step {{
            flex: 1;
            text-align: center;
            position: relative;
        }}
        
        .flow-arrow {{
            font-size: 32px;
            color: {text_secondary};
            flex-shrink: 0;
        }}
        
        .flow-icon {{
            width: 80px;
            height: 80px;
            border-radius: 50%;
            background: linear-gradient(135deg, {primary_color}, {secondary_color});
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 36px;
            margin: 0 auto 20px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.3);
        }}
        
        .flow-icon.step-1 {{ background: linear-gradient(135deg, #8B5CF6, #6366F1); }}
        .flow-icon.step-2 {{ background: linear-gradient(135deg, #06B6D4, #0891B2); }}
        .flow-icon.step-3 {{ background: linear-gradient(135deg, #F59E0B, #D97706); }}
        
        .flow-title {{
            font-size: 22px;
            font-weight: 700;
            margin-bottom: 8px;
        }}
        
        .flow-subtitle {{
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 2px;
            color: {text_secondary};
            margin-bottom: 20px;
        }}
        
        .flow-card {{
            background: rgba(255,255,255,0.05);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 16px;
            padding: 24px;
            margin-top: 10px;
        }}
        
        .flow-description {{
            font-size: 14px;
            line-height: 1.7;
            color: {text_secondary};
        }}
        
        /* Layout: Key Points */
        .points-container {{
            display: flex;
            gap: 60px;
            flex: 1;
            align-items: flex-start;
        }}
        
        .points-list {{
            flex: 1;
        }}
        
        .point-item {{
            display: flex;
            align-items: flex-start;
            margin-bottom: 30px;
            padding-left: 20px;
            border-left: 3px solid {primary_color};
        }}
        
        .point-icon {{
            font-size: 24px;
            margin-right: 16px;
            flex-shrink: 0;
        }}
        
        .point-content {{
            flex: 1;
        }}
        
        .point-title {{
            font-size: 22px;
            font-weight: 700;
            margin-bottom: 8px;
        }}
        
        .point-description {{
            font-size: 15px;
            line-height: 1.7;
            color: {text_secondary};
        }}
        
        /* Layout: Title Slide */
        .title-slide {{
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            text-align: center;
            height: 100%;
        }}
        
        .title-slide .title {{
            font-size: 64px;
            margin-bottom: 30px;
        }}
        
        .title-slide .subtitle {{
            font-size: 24px;
            max-width: 800px;
        }}
        
        /* Layout: Quote */
        .quote-container {{
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            text-align: center;
            flex: 1;
        }}
        
        .quote-mark {{
            font-size: 80px;
            color: {primary_color};
            opacity: 0.5;
            line-height: 1;
        }}
        
        .quote-text {{
            font-size: 32px;
            font-weight: 500;
            line-height: 1.6;
            max-width: 900px;
            margin: 30px 0;
        }}
        
        .quote-author {{
            font-size: 16px;
            color: {text_secondary};
        }}
        
        /* Bottom quote bar */
        .bottom-quote {{
            position: absolute;
            bottom: 60px;
            left: 80px;
            right: 80px;
            text-align: center;
            font-size: 16px;
            color: {text_secondary};
            font-style: italic;
        }}
    </style>
</head>
<body>
    {background_image_tag}
    <div class="overlay"></div>
    <div class="content">
        {content}
    </div>
    <div class="slide-number">{slide_number} / {total_slides}</div>
</body>
</html>
"""


def generate_slide_html(
    slide: Dict[str, Any],
    design: Dict[str, Any],
    slide_number: int,
    total_slides: int,
    background_image_base64: Optional[str] = None,
    video_width: int = VIDEO_WIDTH,
    video_height: int = VIDEO_HEIGHT
) -> str:
    """
    Generate HTML for a slide based on content and design
    """
    colors = design.get("colors", {})
    layout_type = design.get("layout_type", "key_points")
    emphasis_words = design.get("emphasis_words", [])
    icons = design.get("icons", [])
    
    # Extract data from slide_copy structure (from outline generator)
    slide_copy = slide.get("slide_copy", {})
    
    # Get title - try multiple sources
    title = (
        slide_copy.get("headline") or 
        slide.get("title") or 
        slide.get("headline") or 
        ""
    )
    
    # Get subtitle
    subtitle = (
        slide_copy.get("subheadline") or 
        slide.get("subtitle") or 
        slide.get("subheadline") or 
        ""
    )
    
    # Get points - try bullet_points from slide_copy first
    raw_points = (
        slide_copy.get("bullet_points") or 
        slide.get("points") or 
        slide.get("bullet_points") or 
        []
    )
    
    # Convert bullet points to structured format for templates
    points = []
    for p in raw_points:
        if isinstance(p, str):
            points.append({"title": p, "description": ""})
        elif isinstance(p, dict):
            points.append(p)
    
    # Get key message
    key_message = slide_copy.get("key_message") or slide.get("key_message") or ""
    
    # Get section label
    section = slide.get("section", "")
    
    # Create enriched slide data
    enriched_slide = {
        "title": title,
        "subtitle": subtitle,
        "points": points,
        "key_message": key_message,
        "section": section,
        "bottom_quote": key_message,  # Use key_message as bottom quote
        "author": "",
    }
    
    # Apply emphasis to title
    for word in emphasis_words:
        if word in title:
            title = title.replace(word, f'<span class="emphasis">{word}</span>')
    
    # Generate content based on layout
    if layout_type == "title":
        content = generate_title_layout(enriched_slide, title)
    elif layout_type == "flow":
        content = generate_flow_layout(enriched_slide, title, icons)
    elif layout_type == "three_columns":
        content = generate_columns_layout(enriched_slide, title, icons)
    elif layout_type == "quote":
        content = generate_quote_layout(enriched_slide, title)
    else:  # key_points
        content = generate_points_layout(enriched_slide, title, icons)
    
    # Background image tag
    bg_tag = ""
    if background_image_base64:
        bg_tag = f'<img class="background-image" src="data:image/png;base64,{background_image_base64}" />'
    
    # Generate full HTML
    html = BASE_HTML_TEMPLATE.format(
        width=video_width,
        height=video_height,
        background=colors.get("background", "linear-gradient(135deg, #0f172a 0%, #1e293b 100%)"),
        text_color=colors.get("text", "#FFFFFF"),
        text_secondary=colors.get("text_secondary", "#94A3B8"),
        primary_color=colors.get("primary", "#F59E0B"),
        secondary_color=colors.get("secondary", "#8B5CF6"),
        accent_color=colors.get("accent", "#06B6D4"),
        background_image_tag=bg_tag,
        content=content,
        slide_number=slide_number,
        total_slides=total_slides
    )
    
    return html


def generate_title_layout(slide: Dict, title: str) -> str:
    """Generate title slide layout"""
    subtitle = slide.get("subtitle", "")
    section = slide.get("section", "")
    
    return f"""
    <div class="title-slide">
        {f'<div class="section-label">{section}</div>' if section else ''}
        <h1 class="title">{title}</h1>
        {f'<p class="subtitle">{subtitle}</p>' if subtitle else ''}
    </div>
    """


def generate_flow_layout(slide: Dict, title: str, icons: List[str]) -> str:
    """Generate flow/process layout with 3 steps"""
    points = slide.get("points", [])
    section = slide.get("section", "")
    subtitle = slide.get("subtitle", "")
    
    steps_html = ""
    for i, point in enumerate(points[:3]):
        icon = icons[i] if i < len(icons) else "✨"
        
        if isinstance(point, dict):
            pt_title = point.get("title", "")
            pt_desc = point.get("description", "")
            pt_subtitle = point.get("subtitle", "")
        else:
            pt_title = str(point)
            pt_desc = ""
            pt_subtitle = ""
        
        steps_html += f"""
        <div class="flow-step">
            <div class="flow-icon step-{i+1}">{icon}</div>
            <div class="flow-title">{pt_title}</div>
            <div class="flow-subtitle">{pt_subtitle}</div>
            <div class="flow-card">
                <div class="flow-description">{pt_desc}</div>
            </div>
        </div>
        """
        
        if i < len(points[:3]) - 1:
            steps_html += '<div class="flow-arrow">›</div>'
    
    return f"""
    {f'<div class="section-label">{section}</div>' if section else ''}
    <h1 class="title">{title}</h1>
    {f'<p class="subtitle">{subtitle}</p>' if subtitle else ''}
    <div class="flow-container">
        {steps_html}
    </div>
    """


def generate_columns_layout(slide: Dict, title: str, icons: List[str]) -> str:
    """Generate three columns layout"""
    points = slide.get("points", [])
    section = slide.get("section", "")
    subtitle = slide.get("subtitle", "")
    bottom_quote = slide.get("bottom_quote", "")
    
    columns_html = ""
    for i, point in enumerate(points[:3]):
        icon = icons[i] if i < len(icons) else "✨"
        
        if isinstance(point, dict):
            pt_title = point.get("title", "")
            pt_desc = point.get("description", "")
            pt_subtitle = point.get("subtitle", "")
        else:
            pt_title = str(point)
            pt_desc = ""
            pt_subtitle = ""
        
        columns_html += f"""
        <div class="column-card">
            <div class="column-icon">{icon}</div>
            <div class="column-title">{pt_title}</div>
            <div class="column-subtitle">{pt_subtitle}</div>
            <div class="column-description">{pt_desc}</div>
        </div>
        """
    
    return f"""
    {f'<div class="section-label">{section}</div>' if section else ''}
    <h1 class="title">{title}</h1>
    {f'<p class="subtitle">{subtitle}</p>' if subtitle else ''}
    <div class="columns-container">
        {columns_html}
    </div>
    {f'<div class="bottom-quote">「{bottom_quote}」</div>' if bottom_quote else ''}
    """


def generate_points_layout(slide: Dict, title: str, icons: List[str]) -> str:
    """Generate key points list layout"""
    points = slide.get("points", [])
    section = slide.get("section", "")
    subtitle = slide.get("subtitle", "")
    
    points_html = ""
    for i, point in enumerate(points[:5]):
        icon = icons[i] if i < len(icons) else "•"
        
        if isinstance(point, dict):
            pt_title = point.get("title", "")
            pt_desc = point.get("description", "")
        else:
            pt_title = str(point)
            pt_desc = ""
        
        points_html += f"""
        <div class="point-item">
            <span class="point-icon">{icon}</span>
            <div class="point-content">
                <div class="point-title">{pt_title}</div>
                {f'<div class="point-description">{pt_desc}</div>' if pt_desc else ''}
            </div>
        </div>
        """
    
    return f"""
    {f'<div class="section-label">{section}</div>' if section else ''}
    <h1 class="title">{title}</h1>
    {f'<p class="subtitle">{subtitle}</p>' if subtitle else ''}
    <div class="points-container">
        <div class="points-list">
            {points_html}
        </div>
    </div>
    """


def generate_quote_layout(slide: Dict, title: str) -> str:
    """Generate quote layout"""
    subtitle = slide.get("subtitle", "")
    author = slide.get("author", "")
    
    return f"""
    <div class="quote-container">
        <div class="quote-mark">❝</div>
        <div class="quote-text">{title}</div>
        {f'<div class="quote-author">— {author}</div>' if author else ''}
    </div>
    """


async def render_html_to_image(
    html: str, 
    output_path: str,
    video_width: int = VIDEO_WIDTH,
    video_height: int = VIDEO_HEIGHT
) -> str:
    """
    Render HTML to PNG image using Playwright
    """
    from playwright.async_api import async_playwright
    
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": video_width, "height": video_height})
        
        await page.set_content(html)
        
        # Wait for fonts to load
        await page.wait_for_timeout(1000)
        
        # Take screenshot
        await page.screenshot(path=output_path, type="png")
        
        await browser.close()
    
    return output_path


async def generate_html_slides(
    slides: List[Dict[str, Any]],
    designs: List[Dict[str, Any]],
    job_id: str,
    background_images: Optional[List[bytes]] = None,
    video_width: int = VIDEO_WIDTH,
    video_height: int = VIDEO_HEIGHT
) -> List[str]:
    """
    Generate all slide images from HTML
    """
    slides_dir = os.path.join(OUTPUT_DIR, f"{job_id}_slides")
    os.makedirs(slides_dir, exist_ok=True)
    
    image_paths = []
    total_slides = len(slides)
    
    for i, (slide, design) in enumerate(zip(slides, designs)):
        slide_number = i + 1
        
        # Get background image if available
        bg_base64 = None
        if background_images and i < len(background_images) and background_images[i]:
            bg_base64 = base64.b64encode(background_images[i]).decode('utf-8')
        
        # Generate HTML
        html = generate_slide_html(
            slide=slide,
            design=design,
            slide_number=slide_number,
            total_slides=total_slides,
            background_image_base64=bg_base64,
            video_width=video_width,
            video_height=video_height
        )
        
        # Render to image
        output_path = os.path.join(slides_dir, f"slide_{slide_number:03d}.png")
        await render_html_to_image(html, output_path, video_width=video_width, video_height=video_height)
        
        image_paths.append(output_path)
        print(f"[HTML Renderer] Generated slide {slide_number}/{total_slides}")
    
    return image_paths

"""
VoiceSlide AI - Enhanced Slide Image Generator
Creates professional, designable slide images with per-slide image generation
Inspired by Genspark's design aesthetic
"""

import os
import base64
from typing import List, Dict, Any
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
import google.generativeai as genai
from io import BytesIO
import math

from config import GEMINI_API_KEY, OUTPUT_DIR, VIDEO_WIDTH, VIDEO_HEIGHT


# Configure Gemini
genai.configure(api_key=GEMINI_API_KEY)


# Professional color palettes for slides
SLIDE_THEMES = {
    "modern": {
        "bg_gradient": [(15, 23, 42), (30, 41, 59)],  # Dark blue gradient
        "accent": (99, 102, 241),  # Indigo
        "text_primary": (255, 255, 255),
        "text_secondary": (148, 163, 184),
    },
    "minimal": {
        "bg_gradient": [(17, 24, 39), (31, 41, 55)],  # Dark gray
        "accent": (16, 185, 129),  # Emerald
        "text_primary": (255, 255, 255),
        "text_secondary": (156, 163, 175),
    },
    "bold": {
        "bg_gradient": [(88, 28, 135), (124, 58, 237)],  # Purple gradient
        "accent": (251, 191, 36),  # Amber
        "text_primary": (255, 255, 255),
        "text_secondary": (196, 181, 253),
    },
    "professional": {
        "bg_gradient": [(15, 23, 42), (23, 37, 84)],  # Navy
        "accent": (59, 130, 246),  # Blue
        "text_primary": (255, 255, 255),
        "text_secondary": (148, 163, 184),
    },
    "warm": {
        "bg_gradient": [(30, 27, 24), (55, 48, 42)],  # Warm dark
        "accent": (249, 115, 22),  # Orange
        "text_primary": (255, 255, 255),
        "text_secondary": (168, 162, 158),
    }
}


async def generate_slide_images(
    slides: List[Dict[str, Any]],
    job_id: str
) -> List[str]:
    """
    Generate professional slide images with per-slide illustrations
    """
    slides_dir = os.path.join(OUTPUT_DIR, f"{job_id}_slides")
    os.makedirs(slides_dir, exist_ok=True)
    
    image_paths = []
    total_slides = len(slides)
    
    for i, slide in enumerate(slides):
        # Choose theme based on slide style or rotate through themes
        style = slide.get("style", "modern")
        theme = SLIDE_THEMES.get(style, SLIDE_THEMES["modern"])
        
        # Create base slide with gradient background
        base_image = create_professional_background(theme, i, total_slides)
        
        # Generate illustration for this slide
        illustration = await generate_slide_illustration(
            slide.get("title", ""),
            slide.get("points", []),
            slide.get("background_description", "")
        )
        
        # Compose final slide
        final_image = compose_slide_layout(
            base_image=base_image,
            illustration=illustration,
            title=slide.get("title", ""),
            points=slide.get("points", []),
            theme=theme,
            slide_number=i + 1,
            total_slides=total_slides,
            layout_type=determine_layout_type(slide)
        )
        
        # Save image
        image_path = os.path.join(slides_dir, f"slide_{i+1:03d}.png")
        final_image.save(image_path, "PNG", quality=95)
        image_paths.append(image_path)
    
    return image_paths


def create_professional_background(theme: Dict, slide_index: int, total_slides: int) -> Image.Image:
    """
    Create a professional gradient background with subtle patterns
    """
    image = Image.new("RGB", (VIDEO_WIDTH, VIDEO_HEIGHT))
    draw = ImageDraw.Draw(image)
    
    start_color, end_color = theme["bg_gradient"]
    
    # Create diagonal gradient for more dynamic look
    for y in range(VIDEO_HEIGHT):
        for x in range(VIDEO_WIDTH):
            # Diagonal gradient factor
            factor = (x / VIDEO_WIDTH * 0.5 + y / VIDEO_HEIGHT * 0.5)
            
            r = int(start_color[0] + (end_color[0] - start_color[0]) * factor)
            g = int(start_color[1] + (end_color[1] - start_color[1]) * factor)
            b = int(start_color[2] + (end_color[2] - start_color[2]) * factor)
            
            image.putpixel((x, y), (r, g, b))
    
    # Add subtle geometric pattern overlay
    overlay = Image.new("RGBA", (VIDEO_WIDTH, VIDEO_HEIGHT), (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    
    accent = theme["accent"]
    
    # Draw subtle decorative elements
    # Top-right corner accent
    for i in range(3):
        offset = i * 40
        overlay_draw.arc(
            [VIDEO_WIDTH - 200 + offset, -100 + offset, VIDEO_WIDTH + 100 - offset, 200 - offset],
            0, 90,
            fill=(*accent, 20),
            width=3
        )
    
    # Bottom-left corner accent
    for i in range(3):
        offset = i * 40
        overlay_draw.arc(
            [-100 + offset, VIDEO_HEIGHT - 200 + offset, 200 - offset, VIDEO_HEIGHT + 100 - offset],
            180, 270,
            fill=(*accent, 20),
            width=3
        )
    
    # Subtle grid lines
    for i in range(0, VIDEO_WIDTH, 100):
        overlay_draw.line([(i, 0), (i, VIDEO_HEIGHT)], fill=(*accent, 8), width=1)
    for i in range(0, VIDEO_HEIGHT, 100):
        overlay_draw.line([(0, i), (VIDEO_WIDTH, i)], fill=(*accent, 8), width=1)
    
    # Composite overlay
    image = image.convert("RGBA")
    image = Image.alpha_composite(image, overlay)
    
    return image.convert("RGB")


async def generate_slide_illustration(title: str, points: List[str], description: str) -> Image.Image:
    """
    Generate an illustration for the slide using Gemini
    """
    try:
        model = genai.GenerativeModel("gemini-2.0-flash-exp")
        
        content_summary = f"{title}. {'. '.join(points[:2])}" if points else title
        
        prompt = f"""Generate an illustration for a presentation slide.
Topic: {content_summary}
Additional context: {description if description else 'Professional business context'}

Requirements:
- Clean, modern illustration style
- Suitable for business/professional presentation
- Colors should be vibrant but not overwhelming
- Simple iconographic or flat design style
- No text or words in the image
- Square aspect ratio
- White or transparent background preferred"""
        
        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                response_modalities=["image", "text"]
            )
        )
        
        # Extract image from response
        for part in response.candidates[0].content.parts:
            if hasattr(part, 'inline_data') and part.inline_data.mime_type.startswith('image/'):
                image_data = base64.b64decode(part.inline_data.data)
                image = Image.open(BytesIO(image_data))
                return image
        
        return None
        
    except Exception as e:
        print(f"Illustration generation failed: {e}")
        return None


def determine_layout_type(slide: Dict[str, Any]) -> str:
    """
    Determine the best layout for this slide based on content
    """
    title = slide.get("title", "")
    points = slide.get("points", [])
    
    if not points:
        return "title_only"  # Big centered title
    elif len(points) <= 2:
        return "image_right"  # Image on right, text on left
    elif len(points) >= 4:
        return "grid"  # Grid layout for many points
    else:
        return "image_left"  # Image on left, text on right


def compose_slide_layout(
    base_image: Image.Image,
    illustration: Image.Image,
    title: str,
    points: List[str],
    theme: Dict,
    slide_number: int,
    total_slides: int,
    layout_type: str = "image_right"
) -> Image.Image:
    """
    Compose the final slide with professional layout
    """
    image = base_image.copy()
    draw = ImageDraw.Draw(image)
    
    # Load fonts
    title_font = load_font(56)
    point_font = load_font(32)
    number_font = load_font(18)
    
    accent = theme["accent"]
    text_primary = theme["text_primary"]
    text_secondary = theme["text_secondary"]
    
    if layout_type == "title_only":
        # Big centered title slide
        draw_centered_title(draw, title, title_font, text_primary, image.size)
        
    elif layout_type == "image_right":
        # Text on left, image on right
        text_area_width = VIDEO_WIDTH * 0.55
        
        # Draw accent line
        draw.rectangle(
            [60, 150, 70, 250],
            fill=accent
        )
        
        # Draw title
        draw_wrapped_text(
            draw, title, title_font, text_primary,
            x=90, y=150, max_width=text_area_width - 100
        )
        
        # Draw points
        point_y = 280
        for i, point in enumerate(points[:4]):
            # Bullet point with accent color
            draw.ellipse([90, point_y + 12, 100, point_y + 22], fill=accent)
            draw_wrapped_text(
                draw, point, point_font, text_secondary,
                x=120, y=point_y, max_width=text_area_width - 130
            )
            point_y += 70
        
        # Add illustration on right
        if illustration:
            add_illustration(image, illustration, "right")
    
    elif layout_type == "image_left":
        # Image on left, text on right
        text_x = VIDEO_WIDTH * 0.45
        
        # Draw accent line
        draw.rectangle(
            [text_x, 150, text_x + 10, 250],
            fill=accent
        )
        
        # Draw title
        draw_wrapped_text(
            draw, title, title_font, text_primary,
            x=text_x + 30, y=150, max_width=VIDEO_WIDTH - text_x - 100
        )
        
        # Draw points
        point_y = 280
        for i, point in enumerate(points[:4]):
            draw.ellipse([text_x + 30, point_y + 12, text_x + 40, point_y + 22], fill=accent)
            draw_wrapped_text(
                draw, point, point_font, text_secondary,
                x=text_x + 60, y=point_y, max_width=VIDEO_WIDTH - text_x - 150
            )
            point_y += 70
        
        # Add illustration on left
        if illustration:
            add_illustration(image, illustration, "left")
    
    elif layout_type == "grid":
        # Title at top, points in grid
        draw_wrapped_text(
            draw, title, title_font, text_primary,
            x=60, y=80, max_width=VIDEO_WIDTH - 120
        )
        
        # Grid of points
        cols = 2
        rows = math.ceil(len(points[:6]) / cols)
        cell_width = (VIDEO_WIDTH - 120) // cols
        cell_height = (VIDEO_HEIGHT - 250) // rows
        
        for i, point in enumerate(points[:6]):
            row = i // cols
            col = i % cols
            x = 60 + col * cell_width
            y = 200 + row * cell_height
            
            # Card background
            draw.rounded_rectangle(
                [x, y, x + cell_width - 20, y + cell_height - 20],
                radius=15,
                fill=(*accent, 30) if isinstance(accent, tuple) and len(accent) == 3 else (99, 102, 241, 30)
            )
            
            # Point text
            draw_wrapped_text(
                draw, point, point_font, text_primary,
                x=x + 20, y=y + 30, max_width=cell_width - 60
            )
    
    # Slide number
    draw.text(
        (VIDEO_WIDTH - 80, VIDEO_HEIGHT - 50),
        f"{slide_number} / {total_slides}",
        font=number_font,
        fill=text_secondary
    )
    
    return image


def load_font(size: int) -> ImageFont.FreeTypeFont:
    """
    Load a font with fallback options
    """
    font_paths = [
        "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc", 
        "/Library/Fonts/Arial Unicode.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    ]
    
    for font_path in font_paths:
        if os.path.exists(font_path):
            try:
                return ImageFont.truetype(font_path, size)
            except Exception:
                continue
    
    return ImageFont.load_default()


def draw_centered_title(draw: ImageDraw.Draw, text: str, font: ImageFont.FreeTypeFont, color: tuple, size: tuple):
    """
    Draw a large centered title
    """
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    x = (size[0] - text_width) // 2
    y = size[1] // 2 - 50
    
    # Shadow
    draw.text((x + 3, y + 3), text, font=font, fill=(0, 0, 0, 128))
    draw.text((x, y), text, font=font, fill=color)


def draw_wrapped_text(draw: ImageDraw.Draw, text: str, font: ImageFont.FreeTypeFont, color: tuple, x: int, y: int, max_width: int):
    """
    Draw text with word wrapping
    """
    words = text.split()
    lines = []
    current_line = ""
    
    for word in words:
        test_line = f"{current_line} {word}".strip()
        bbox = draw.textbbox((0, 0), test_line, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current_line = test_line
        else:
            if current_line:
                lines.append(current_line)
            current_line = word
    
    if current_line:
        lines.append(current_line)
    
    line_height = font.size + 10
    for i, line in enumerate(lines[:3]):  # Max 3 lines
        draw.text((x, y + i * line_height), line, font=font, fill=color)


def add_illustration(base_image: Image.Image, illustration: Image.Image, position: str):
    """
    Add illustration to the slide
    """
    # Resize illustration
    max_size = int(VIDEO_HEIGHT * 0.6)
    illustration.thumbnail((max_size, max_size), Image.LANCZOS)
    
    # Calculate position
    if position == "right":
        x = VIDEO_WIDTH - illustration.width - 60
    else:  # left
        x = 60
    y = (VIDEO_HEIGHT - illustration.height) // 2
    
    # Add subtle shadow effect
    shadow = Image.new("RGBA", illustration.size, (0, 0, 0, 50))
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=10))
    
    # Paste with alpha if available
    if illustration.mode == "RGBA":
        base_image.paste(shadow, (x + 10, y + 10), shadow)
        base_image.paste(illustration, (x, y), illustration)
    else:
        base_image.paste(shadow, (x + 10, y + 10), shadow)
        base_image.paste(illustration, (x, y))

"""
VoiceSlide AI - Image Generation Service
Uses Gemini Imagen to generate custom images for slides
"""

import base64
from typing import Optional, Dict, Any, List
import google.generativeai as genai

from config import GEMINI_API_KEY


async def generate_slide_image(
    prompt: str,
    gemini_key: Optional[str] = None
) -> Optional[Dict[str, str]]:
    """
    Generate an image using Gemini Imagen
    Returns base64 encoded image data
    """
    key = gemini_key or GEMINI_API_KEY
    if not key:
        print("[Image Gen] No Gemini API key")
        return None
    
    genai.configure(api_key=key)
    
    # Build detailed prompt for slide-appropriate image
    full_prompt = f"""Generate a high-quality, professional image for a presentation slide.

Style requirements:
- Dark, moody color palette suitable for overlay text
- Abstract or conceptual (no text or words in the image)
- Professional and modern aesthetic
- Smooth gradients and subtle lighting
- 16:9 aspect ratio composition

Content: {prompt}

The image should be suitable as a slide background or accent image, with areas dark enough for white text overlay."""

    try:
        # Use Gemini with image generation capability
        model = genai.GenerativeModel("gemini-2.0-flash-exp")
        
        response = model.generate_content(
            full_prompt,
            generation_config=genai.GenerationConfig(
                response_modalities=["image", "text"]
            )
        )
        
        # Extract image from response
        for part in response.candidates[0].content.parts:
            if hasattr(part, 'inline_data') and part.inline_data.mime_type.startswith('image/'):
                image_data = part.inline_data.data
                mime_type = part.inline_data.mime_type
                
                # Convert to base64 data URL
                b64_data = base64.b64encode(image_data).decode('utf-8')
                data_url = f"data:{mime_type};base64,{b64_data}"
                
                print(f"[Image Gen] Successfully generated image")
                return {
                    "url": data_url,
                    "base64_url": data_url,
                    "photographer": "AI Generated (Gemini Imagen)",
                    "alt_description": prompt[:100]
                }
        
        print("[Image Gen] No image in response")
        return None
        
    except Exception as e:
        print(f"[Image Gen] Error: {e}")
        return None


def extract_image_keywords(slide: Dict[str, Any], strategy: Dict[str, Any]) -> List[str]:
    """
    Extract keywords from slide content for image generation prompt
    """
    slide_copy = slide.get("slide_copy", {})
    analysis = strategy.get("content_analysis", {})
    style = strategy.get("design_style", {})
    
    keywords = []
    
    # From slide content
    title = slide_copy.get("headline") or slide.get("title", "")
    if title:
        keywords.append(title)
    
    # From key concepts in strategy
    key_concepts = analysis.get("key_concepts", [])
    keywords.extend(key_concepts[:3])
    
    # From visual theme
    visual_theme = style.get("visual_theme", "")
    if visual_theme:
        keywords.append(visual_theme)
    
    return keywords


def build_image_prompt(keywords: List[str], slide_type: str) -> str:
    """
    Build a detailed prompt for image generation based on slide content
    """
    keyword_str = ", ".join(keywords[:3]) if keywords else "business technology"
    
    # Adjust style based on slide type
    if "タイトル" in slide_type or "表紙" in slide_type:
        style = "dramatic, hero image, cinematic lighting"
    elif "フロー" in slide_type or "プロセス" in slide_type:
        style = "abstract flow, dynamic movement, connected elements"
    elif "ポイント" in slide_type:
        style = "clean, organized, professional"
    elif "引用" in slide_type or "メッセージ" in slide_type:
        style = "atmospheric, emotional, inspirational"
    else:
        style = "professional, modern, abstract"
    
    return f"{keyword_str}, {style}, dark background, suitable for presentation slide"


async def get_image_for_slide(
    keywords: List[str],
    slide_type: str = "",
    gemini_key: Optional[str] = None
) -> Optional[Dict[str, str]]:
    """
    Get a generated image for a slide based on keywords
    """
    prompt = build_image_prompt(keywords, slide_type)
    return await generate_slide_image(prompt, gemini_key)

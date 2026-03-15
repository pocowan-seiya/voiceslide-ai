"""
VoiceSlide AI - AI-Driven Slide Design
Analyzes slide content and determines optimal design for each slide
"""

import json
from typing import Dict, Any, List, Optional
import google.generativeai as genai

from config import GEMINI_API_KEY
from services.ai_utils import safe_gemini_generate


# Design templates available
LAYOUT_TYPES = [
    "title",           # Big centered title with background
    "flow",            # 3-step flow diagram with icons
    "three_columns",   # 3 parallel cards
    "key_points",      # Bullet list with accent line
    "quote",           # Centered quote
    "comparison",      # Before/After or left/right comparison
    "content_image",   # Text + image layout
]

# Color schemes
COLOR_SCHEMES = {
    "cosmic": {
        "primary": "#F59E0B",      # Amber/Gold
        "secondary": "#8B5CF6",    # Purple
        "accent": "#06B6D4",       # Cyan
        "background": "linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f0f23 100%)",
        "text": "#FFFFFF",
        "text_secondary": "#94A3B8"
    },
    "professional": {
        "primary": "#3B82F6",      # Blue
        "secondary": "#1E40AF",    # Dark Blue
        "accent": "#10B981",       # Emerald
        "background": "linear-gradient(135deg, #0f172a 0%, #1e293b 100%)",
        "text": "#FFFFFF",
        "text_secondary": "#CBD5E1"
    },
    "warm": {
        "primary": "#F97316",      # Orange
        "secondary": "#EA580C",    # Dark Orange
        "accent": "#FBBF24",       # Amber
        "background": "linear-gradient(135deg, #1c1917 0%, #292524 100%)",
        "text": "#FFFFFF",
        "text_secondary": "#D6D3D1"
    },
    "elegant": {
        "primary": "#A855F7",      # Purple
        "secondary": "#7C3AED",    # Violet
        "accent": "#EC4899",       # Pink
        "background": "linear-gradient(135deg, #0c0a1d 0%, #1e1b4b 100%)",
        "text": "#FFFFFF",
        "text_secondary": "#C4B5FD"
    },
    "minimal": {
        "primary": "#6366F1",      # Indigo
        "secondary": "#4F46E5",    # Darker Indigo
        "accent": "#22D3EE",       # Cyan
        "background": "linear-gradient(135deg, #111827 0%, #1f2937 100%)",
        "text": "#FFFFFF",
        "text_secondary": "#9CA3AF"
    }
}

# Icon suggestions for common concepts
CONCEPT_ICONS = {
    "input": "📥", "output": "📤", "process": "⚙️", "idea": "💡",
    "growth": "📈", "money": "💰", "time": "⏰", "people": "👥",
    "target": "🎯", "star": "⭐", "check": "✅", "warning": "⚠️",
    "heart": "❤️", "fire": "🔥", "rocket": "🚀", "brain": "🧠",
    "book": "📚", "search": "🔍", "message": "💬", "link": "🔗",
    "filter": "🔄", "value": "💎", "reach": "📡", "business": "💼"
}


DESIGN_ANALYSIS_PROMPT = """あなたはプレゼンテーションデザインの専門家です。
スライドの内容を分析し、最適なデザインを決定してください。

# スライド情報
タイトル: {title}
サブタイトル: {subtitle}
ポイント: {points}
スライド番号: {slide_number} / {total_slides}

# 決定する項目

1. **layout_type**: 以下から最適なレイアウトを選択
   - "title": タイトルスライド（最初のスライドや大きなセクション区切り）
   - "flow": 3ステップのフロー図（プロセスや手順）
   - "three_columns": 3カラムカード（並列な概念）
   - "key_points": ポイントリスト（要点の列挙）
   - "quote": 引用（印象的なフレーズ）
   - "content_image": コンテンツ+画像

2. **color_scheme**: 以下から配色を選択
   - "cosmic": 宇宙的（ゴールド・パープル）- 哲学的・壮大なテーマ
   - "professional": プロフェッショナル（ブルー系）- ビジネス用
   - "warm": 温かみ（オレンジ系）- 情熱的・エネルギー
   - "elegant": エレガント（パープル・ピンク）- 洗練された印象
   - "minimal": ミニマル（インディゴ）- シンプル・モダン

3. **background_prompt**: 背景画像生成用のプロンプト（英語、50語以内）
   例: "abstract cosmic nebula with stars, deep blue and purple gradient, professional"

4. **icons**: 各ポイントに適した絵文字アイコン（配列）

5. **emphasis_words**: タイトル内で強調すべき単語（ゴールドで表示）

# 出力形式（JSON）
```json
{{
    "layout_type": "three_columns",
    "color_scheme": "cosmic",
    "background_prompt": "abstract cosmic nebula...",
    "icons": ["💡", "🔄", "🎯"],
    "emphasis_words": ["価値", "波及"]
}}
```

JSONのみを出力してください。
"""


async def analyze_slide_design(
    slide: Dict[str, Any],
    slide_number: int,
    total_slides: int,
    gemini_key: Optional[str] = None,
    model_name: str = "gemini-3-flash-preview"
) -> Dict[str, Any]:
    """
    Analyze slide content and determine optimal design
    """
    key = gemini_key or GEMINI_API_KEY
    if not key:
        raise ValueError("Gemini API key is required")
    
    genai.configure(api_key=key)
    
    # Extract data from slide_copy structure (from outline generator)
    slide_copy = slide.get("slide_copy", {})
    
    title = (
        slide_copy.get("headline") or 
        slide.get("title") or 
        ""
    )
    subtitle = (
        slide_copy.get("subheadline") or 
        slide.get("subtitle") or 
        ""
    )
    raw_points = (
        slide_copy.get("bullet_points") or 
        slide.get("points") or 
        []
    )
    key_message = slide_copy.get("key_message") or ""
    
    # Format points for prompt
    if isinstance(raw_points, list):
        points_str = "\n".join([f"- {p}" if isinstance(p, str) else f"- {p.get('title', '')}" for p in raw_points])
    else:
        points_str = str(raw_points)
    
    prompt = DESIGN_ANALYSIS_PROMPT.format(
        title=title,
        subtitle=f"{subtitle}\nキーメッセージ: {key_message}" if key_message else subtitle,
        points=points_str,
        slide_number=slide_number,
        total_slides=total_slides
    )
    
    try:
        # Try available models
        model_names = [model_name, "gemini-1.5-flash-latest", "gemini-pro"]
        
        for model_name in model_names:
            try:
                response_text = await safe_gemini_generate(
                    model_name,
                    prompt,
                    key,
                    config=genai.GenerationConfig(
                        response_mime_type="application/json",
                        temperature=0.7
                    )
                )
                
                design = json.loads(response_text)
                
                # Validate and fill defaults
                design = validate_design(design, slide, slide_number, total_slides)
                
                print(f"[Design AI] Slide {slide_number}: {design['layout_type']} / {design['color_scheme']}")
                return design
                
            except Exception as e:
                print(f"[Design AI] Model {model_name} failed: {str(e)[:80]}")
                continue
        
        # Fallback to rule-based design
        return get_fallback_design(slide, slide_number, total_slides)
        
    except Exception as e:
        print(f"[Design AI] Error: {e}")
        return get_fallback_design(slide, slide_number, total_slides)


def validate_design(design: Dict, slide: Dict, slide_number: int, total_slides: int) -> Dict:
    """Validate and fill missing design fields"""
    
    # Ensure layout_type is valid
    if design.get("layout_type") not in LAYOUT_TYPES:
        design["layout_type"] = determine_layout_from_content(slide, slide_number, total_slides)
    
    # Ensure color_scheme is valid
    if design.get("color_scheme") not in COLOR_SCHEMES:
        design["color_scheme"] = "cosmic"
    
    # Ensure background_prompt exists
    if not design.get("background_prompt"):
        design["background_prompt"] = "abstract gradient background, professional, modern design"
    
    # Ensure icons is a list
    if not isinstance(design.get("icons"), list):
        design["icons"] = []
    
    # Ensure emphasis_words is a list
    if not isinstance(design.get("emphasis_words"), list):
        design["emphasis_words"] = []
    
    # Add color scheme details
    design["colors"] = COLOR_SCHEMES[design["color_scheme"]]
    
    return design


def determine_layout_from_content(slide: Dict, slide_number: int, total_slides: int) -> str:
    """Rule-based layout determination"""
    slide_copy = slide.get("slide_copy", {})
    points = slide_copy.get("bullet_points") or slide.get("points", [])
    title = slide_copy.get("headline") or slide.get("title", "")
    
    # First slide is usually title
    if slide_number == 1:
        return "title"
    
    # Last slide could be conclusion
    if slide_number == total_slides:
        return "title"
    
    # Based on number of points
    if not points:
        return "quote"
    elif len(points) == 3:
        # Check if it's a flow/process
        if any(word in title for word in ["ステップ", "プロセス", "流れ", "手順", "→"]):
            return "flow"
        return "three_columns"
    elif len(points) <= 4:
        return "key_points"
    else:
        return "key_points"


def get_fallback_design(slide: Dict, slide_number: int, total_slides: int) -> Dict:
    """Generate fallback design when AI fails"""
    layout = determine_layout_from_content(slide, slide_number, total_slides)
    
    # Get points count from slide_copy
    slide_copy = slide.get("slide_copy", {})
    points = slide_copy.get("bullet_points") or slide.get("points", [])
    
    # Cycle through color schemes
    schemes = list(COLOR_SCHEMES.keys())
    scheme = schemes[(slide_number - 1) % len(schemes)]
    
    return {
        "layout_type": layout,
        "color_scheme": scheme,
        "background_prompt": "abstract gradient with subtle geometric patterns, professional",
        "icons": ["💡", "⭐", "🎯", "✨", "🚀"][:len(points)],
        "emphasis_words": [],
        "colors": COLOR_SCHEMES[scheme]
    }


async def generate_background_image(
    prompt: str,
    gemini_key: Optional[str] = None,
    model_name: str = "gemini-3-flash-preview"
) -> Optional[bytes]:
    """
    Generate background image using Gemini
    """
    key = gemini_key or GEMINI_API_KEY
    if not key:
        return None
    
    genai.configure(api_key=key)
    
    try:
        model = genai.GenerativeModel(model_name)
        
        full_prompt = f"""Generate a professional presentation slide background image.
Style: {prompt}
Requirements:
- Dark, muted colors suitable for text overlay
- No text or words in the image
- Smooth gradients and subtle patterns
- 16:9 aspect ratio
- Professional, modern aesthetic
- Slightly blurred or abstract to not distract from content"""
        
        response = model.generate_content(
            full_prompt,
            generation_config=genai.GenerationConfig(
                response_modalities=["image", "text"]
            )
        )
        
        # Extract image data
        for part in response.candidates[0].content.parts:
            if hasattr(part, 'inline_data') and part.inline_data.mime_type.startswith('image/'):
                import base64
                return base64.b64decode(part.inline_data.data)
        
        return None
        
    except Exception as e:
        print(f"[Background Gen] Error: {e}")
        return None

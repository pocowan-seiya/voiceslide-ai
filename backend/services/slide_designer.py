"""
VoiceSlide AI v3 - 高品質AIスライドデザイナー
Geminiを使用してレイアウト・デザイン・画像を丁寧に生成
"""

import os
import json
import asyncio
import base64
from typing import Dict, Any, List, Optional
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import google.generativeai as genai
from openai import OpenAI
import httpx

from config import GEMINI_API_KEY, OPENAI_API_KEY, OUTPUT_DIR

# Initialize clients
genai.configure(api_key=GEMINI_API_KEY)
openai_client = OpenAI(api_key=OPENAI_API_KEY)


# スライドデザイン決定用プロンプト
SLIDE_DESIGN_PROMPT = """あなたはプロのプレゼンテーションデザイナーです。

以下のスライド情報に基づいて、最適なレイアウトとデザインを決定してください。

## スライド情報
- スライド番号: {slide_num} / {total_slides}
- タイトル: {headline}
- サブタイトル: {subheadline}
- ポイント数: {bullet_count}
- キーメッセージ: {key_message}
- スライドの役割: {slide_role}

## 決定すべき項目

以下のJSON形式で回答してください：

{{
  "layout_type": "title_centered / two_column / bullet_list / image_left / image_right / quote / data_focus / closing",
  "background_style": "solid_dark / gradient_diagonal / gradient_radial / subtle_pattern",
  "accent_position": "top_bar / left_bar / bottom_accent / corner_accent / none",
  "visual_element": {{
    "type": "none / icon / abstract_shape / photo / illustration",
    "description": "ビジュアル要素の説明（画像生成プロンプト用）",
    "position": "background / left / right / center / corner"
  }},
  "text_alignment": "left / center / right",
  "emphasis_style": "highlight_box / underline / glow / bold_color / none",
  "color_mood": "professional / energetic / calm / modern / warm",
  "recommended_font_size": {{
    "headline": 60,
    "subheadline": 32,
    "body": 28
  }}
}}

スライドの内容と役割に最適なデザインを選んでください。
"""


async def generate_slides_from_outline(
    outline: Dict[str, Any],
    job_id: str,
    template: str = "modern_dark"
) -> Dict[str, Any]:
    """
    アウトラインから高品質スライド画像を生成
    各スライドをGeminiでデザイン決定してから生成
    """
    slides = outline.get("slides", [])
    presentation_title = outline.get("presentation_title", "プレゼンテーション")
    
    if not slides:
        raise ValueError("アウトラインにスライドがありません")
    
    # 出力ディレクトリを作成
    slides_dir = os.path.join(OUTPUT_DIR, f"{job_id}_slides")
    os.makedirs(slides_dir, exist_ok=True)
    
    generated_images = []
    slide_contents = []
    
    for i, slide in enumerate(slides):
        slide_num = slide.get("number", i + 1)
        print(f"🎨 スライド {slide_num}/{len(slides)} をデザイン中...")
        
        # スライドコピーを取得
        slide_copy = slide.get("slide_copy", {})
        headline = slide_copy.get("headline") or slide.get("title", f"スライド {slide_num}")
        subheadline = slide_copy.get("subheadline", "")
        bullet_points = slide_copy.get("bullet_points", [])
        key_message = slide_copy.get("key_message", "")
        keywords = slide.get("keywords", [])
        visual_suggestion = slide.get("visual_suggestion", {})
        
        # Geminiでデザイン決定を取得
        design_decision = await get_design_decision(
            slide_num=slide_num,
            total_slides=len(slides),
            headline=headline,
            subheadline=subheadline,
            bullet_count=len(bullet_points),
            key_message=key_message,
            slide_role=visual_suggestion.get("type", "content")
        )
        
        # スライド画像パス
        image_path = os.path.join(slides_dir, f"slide_{slide_num:02d}.png")
        
        # 高品質スライドを生成
        await create_premium_slide(
            output_path=image_path,
            slide_num=slide_num,
            total_slides=len(slides),
            headline=headline,
            subheadline=subheadline,
            bullet_points=bullet_points[:5],
            key_message=key_message,
            keywords=keywords[:5],
            design=design_decision,
            is_title_slide=(slide_num == 1),
            presentation_title=presentation_title
        )
        
        generated_images.append(image_path)
        slide_contents.append({
            "number": slide_num,
            "title": headline,
            "keywords": keywords,
            "image_path": image_path
        })
        
        print(f"✅ スライド {slide_num}/{len(slides)} 完成")
    
    return {
        "images": generated_images,
        "contents": slide_contents,
        "slide_count": len(generated_images),
        "slide_previews": [
            f"/outputs/{job_id}_slides/slide_{i+1:02d}.png" 
            for i in range(len(generated_images))
        ]
    }


async def get_design_decision(
    slide_num: int,
    total_slides: int,
    headline: str,
    subheadline: str,
    bullet_count: int,
    key_message: str,
    slide_role: str
) -> Dict[str, Any]:
    """
    Geminiを使用してスライドのデザイン決定を取得
    """
    prompt = SLIDE_DESIGN_PROMPT.format(
        slide_num=slide_num,
        total_slides=total_slides,
        headline=headline,
        subheadline=subheadline or "なし",
        bullet_count=bullet_count,
        key_message=key_message or "なし",
        slide_role=slide_role
    )
    
    try:
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                temperature=0.7
            )
        )
        design = json.loads(response.text)
        return design
    except Exception as e:
        print(f"デザイン決定エラー: {e}")
        # デフォルトのデザイン
        return get_default_design(slide_num, total_slides)


def get_default_design(slide_num: int, total_slides: int) -> Dict[str, Any]:
    """デフォルトのデザイン設定"""
    if slide_num == 1:
        return {
            "layout_type": "title_centered",
            "background_style": "gradient_diagonal",
            "accent_position": "none",
            "visual_element": {"type": "none", "description": "", "position": ""},
            "text_alignment": "center",
            "emphasis_style": "glow",
            "color_mood": "modern",
            "recommended_font_size": {"headline": 72, "subheadline": 36, "body": 28}
        }
    elif slide_num == total_slides:
        return {
            "layout_type": "closing",
            "background_style": "gradient_radial",
            "accent_position": "bottom_accent",
            "visual_element": {"type": "abstract_shape", "description": "アクセント", "position": "corner"},
            "text_alignment": "center",
            "emphasis_style": "glow",
            "color_mood": "warm",
            "recommended_font_size": {"headline": 60, "subheadline": 32, "body": 28}
        }
    else:
        return {
            "layout_type": "bullet_list",
            "background_style": "solid_dark",
            "accent_position": "left_bar",
            "visual_element": {"type": "icon", "description": "アイコン", "position": "corner"},
            "text_alignment": "left",
            "emphasis_style": "highlight_box",
            "color_mood": "professional",
            "recommended_font_size": {"headline": 56, "subheadline": 28, "body": 26}
        }


async def create_premium_slide(
    output_path: str,
    slide_num: int,
    total_slides: int,
    headline: str,
    subheadline: str,
    bullet_points: List[str],
    key_message: str,
    keywords: List[str],
    design: Dict[str, Any],
    is_title_slide: bool = False,
    presentation_title: str = ""
) -> None:
    """
    高品質なスライド画像を生成
    """
    # スライドサイズ (16:9)
    width, height = 1920, 1080
    
    # カラーパレット（デザインのムードに基づく）
    colors = get_color_palette(design.get("color_mood", "modern"))
    
    # 画像を作成
    img = Image.new('RGB', (width, height), colors["bg"])
    draw = ImageDraw.Draw(img)
    
    # 背景スタイルを適用
    apply_background_style(img, draw, design.get("background_style", "solid_dark"), colors)
    
    # アクセント要素を追加
    apply_accent(draw, design.get("accent_position", "left_bar"), colors, width, height)
    
    # フォントを読み込み
    fonts = load_fonts(design.get("recommended_font_size", {}))
    
    # レイアウトタイプに応じてコンテンツを配置
    layout_type = design.get("layout_type", "bullet_list")
    text_align = design.get("text_alignment", "left")
    
    if is_title_slide or layout_type == "title_centered":
        render_title_slide(
            draw, width, height, presentation_title, subheadline,
            fonts, colors, design
        )
    elif layout_type == "closing":
        render_closing_slide(
            draw, width, height, headline, key_message,
            fonts, colors, design
        )
    else:
        render_content_slide(
            draw, width, height, slide_num, total_slides,
            headline, subheadline, bullet_points, key_message, keywords,
            fonts, colors, design
        )
    
    # スライド番号（タイトルスライド以外）
    if not is_title_slide:
        slide_info = f"{slide_num} / {total_slides}"
        draw.text((width - 60, height - 40), slide_info, 
                  font=fonts["small"], fill=colors["muted"], anchor="rm")
    
    # 高品質で保存
    img.save(output_path, "PNG", quality=95)


def get_color_palette(mood: str) -> Dict[str, str]:
    """カラーパレットを取得"""
    palettes = {
        "modern": {
            "bg": "#0a0a0f",
            "primary": "#06b6d4",
            "secondary": "#8b5cf6",
            "text": "#ffffff",
            "muted": "#64748b",
            "accent": "#22d3ee",
            "highlight": "#06b6d4"
        },
        "professional": {
            "bg": "#0f172a",
            "primary": "#3b82f6",
            "secondary": "#1e40af",
            "text": "#f1f5f9",
            "muted": "#94a3b8",
            "accent": "#60a5fa",
            "highlight": "#3b82f6"
        },
        "energetic": {
            "bg": "#18181b",
            "primary": "#f97316",
            "secondary": "#ea580c",
            "text": "#ffffff",
            "muted": "#71717a",
            "accent": "#fb923c",
            "highlight": "#f97316"
        },
        "calm": {
            "bg": "#0c1222",
            "primary": "#10b981",
            "secondary": "#059669",
            "text": "#f0fdf4",
            "muted": "#6b7280",
            "accent": "#34d399",
            "highlight": "#10b981"
        },
        "warm": {
            "bg": "#1c1917",
            "primary": "#f59e0b",
            "secondary": "#d97706",
            "text": "#fffbeb",
            "muted": "#78716c",
            "accent": "#fbbf24",
            "highlight": "#f59e0b"
        }
    }
    return palettes.get(mood, palettes["modern"])


def apply_background_style(img: Image, draw: ImageDraw, style: str, colors: Dict[str, str]) -> None:
    """背景スタイルを適用"""
    width, height = img.size
    
    if style == "gradient_diagonal":
        # 対角グラデーション
        for y in range(height):
            for x in range(width):
                ratio = (x + y) / (width + height)
                r1, g1, b1 = hex_to_rgb(colors["bg"])
                r2, g2, b2 = hex_to_rgb(colors["secondary"])
                r = int(r1 + (r2 - r1) * ratio * 0.3)
                g = int(g1 + (g2 - g1) * ratio * 0.3)
                b = int(b1 + (b2 - b1) * ratio * 0.3)
                img.putpixel((x, y), (r, g, b))
    
    elif style == "gradient_radial":
        # 放射グラデーション（中央から）
        cx, cy = width // 2, height // 2
        max_dist = ((width/2)**2 + (height/2)**2) ** 0.5
        for y in range(height):
            for x in range(width):
                dist = ((x - cx)**2 + (y - cy)**2) ** 0.5
                ratio = dist / max_dist
                r1, g1, b1 = hex_to_rgb(colors["secondary"])
                r2, g2, b2 = hex_to_rgb(colors["bg"])
                r = int(r1 + (r2 - r1) * ratio)
                g = int(g1 + (g2 - g1) * ratio)
                b = int(b1 + (b2 - b1) * ratio)
                # 薄い効果
                r = int((r * 0.4 + hex_to_rgb(colors["bg"])[0] * 0.6))
                g = int((g * 0.4 + hex_to_rgb(colors["bg"])[1] * 0.6))
                b = int((b * 0.4 + hex_to_rgb(colors["bg"])[2] * 0.6))
                img.putpixel((x, y), (r, g, b))
    
    elif style == "subtle_pattern":
        # 微妙なドットパターン
        draw.rectangle([0, 0, width, height], fill=colors["bg"])
        for y in range(0, height, 40):
            for x in range(0, width, 40):
                draw.ellipse([x-1, y-1, x+1, y+1], fill=colors["muted"])


def apply_accent(draw: ImageDraw, accent_type: str, colors: Dict[str, str], width: int, height: int) -> None:
    """アクセント要素を追加"""
    if accent_type == "top_bar":
        draw.rectangle([0, 0, width, 6], fill=colors["primary"])
    elif accent_type == "left_bar":
        draw.rectangle([0, 0, 8, height], fill=colors["primary"])
    elif accent_type == "bottom_accent":
        draw.rectangle([0, height - 6, width, height], fill=colors["primary"])
    elif accent_type == "corner_accent":
        # 角の装飾
        draw.polygon([(0, 0), (150, 0), (0, 150)], fill=colors["primary"])
        draw.polygon([(width, height), (width - 150, height), (width, height - 150)], fill=colors["secondary"])


def load_fonts(sizes: Dict[str, int]) -> Dict[str, ImageFont.FreeTypeFont]:
    """フォントを読み込み"""
    headline_size = sizes.get("headline", 60)
    subheadline_size = sizes.get("subheadline", 32)
    body_size = sizes.get("body", 28)
    
    font_paths = [
        "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc",
        "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    
    def try_load_font(size: int, bold: bool = False):
        for path in font_paths:
            if bold and "W6" not in path and "Bold" not in path:
                continue
            try:
                return ImageFont.truetype(path, size)
            except:
                continue
        return ImageFont.load_default()
    
    return {
        "headline": try_load_font(headline_size, bold=True),
        "subheadline": try_load_font(subheadline_size),
        "body": try_load_font(body_size),
        "small": try_load_font(22)
    }


def render_title_slide(draw, width, height, title, subtitle, fonts, colors, design):
    """タイトルスライドを描画"""
    # 中央配置
    title_y = height // 2 - 60
    
    # タイトル装飾（グロー効果）
    if design.get("emphasis_style") == "glow":
        for offset in [(2, 2), (-2, -2), (2, -2), (-2, 2)]:
            draw.text((width // 2 + offset[0], title_y + offset[1]), title, 
                      font=fonts["headline"], fill=colors["primary"], anchor="mm")
    
    draw.text((width // 2, title_y), title, 
              font=fonts["headline"], fill=colors["text"], anchor="mm")
    
    if subtitle:
        draw.text((width // 2, title_y + 100), subtitle, 
                  font=fonts["subheadline"], fill=colors["accent"], anchor="mm")
    
    # 下部のアクセントライン
    line_y = height // 2 + 50
    draw.rectangle([width//2 - 150, line_y, width//2 + 150, line_y + 4], fill=colors["primary"])


def render_closing_slide(draw, width, height, headline, key_message, fonts, colors, design):
    """クロージングスライドを描画"""
    # 感謝メッセージを中央に
    draw.text((width // 2, height // 2 - 30), headline, 
              font=fonts["headline"], fill=colors["text"], anchor="mm")
    
    if key_message:
        draw.text((width // 2, height // 2 + 60), key_message, 
                  font=fonts["subheadline"], fill=colors["accent"], anchor="mm")


def render_content_slide(draw, width, height, slide_num, total_slides,
                         headline, subheadline, bullet_points, key_message, keywords,
                         fonts, colors, design):
    """コンテンツスライドを描画"""
    y_offset = 100
    left_margin = 120
    
    # ヘッドライン
    headline_lines = wrap_text(headline, fonts["headline"], width - 250)
    for line in headline_lines[:2]:
        draw.text((left_margin, y_offset), line, font=fonts["headline"], fill=colors["text"])
        y_offset += 80
    
    # サブヘッドライン
    if subheadline:
        y_offset += 10
        draw.text((left_margin, y_offset), subheadline, font=fonts["subheadline"], fill=colors["accent"])
        y_offset += 50
    
    # 区切り線
    y_offset += 20
    draw.rectangle([left_margin, y_offset, left_margin + 200, y_offset + 4], fill=colors["primary"])
    y_offset += 40
    
    # 箇条書き
    for i, point in enumerate(bullet_points):
        if y_offset > height - 200:
            break
        
        # 箇条書きの点（グラデーション風）
        bullet_colors = [colors["primary"], colors["secondary"], colors["accent"]]
        bullet_color = bullet_colors[i % len(bullet_colors)]
        draw.ellipse([left_margin, y_offset + 10, left_margin + 14, y_offset + 24], fill=bullet_color)
        
        # テキスト
        point_lines = wrap_text(point, fonts["body"], width - 300)
        for j, line in enumerate(point_lines[:2]):
            draw.text((left_margin + 35, y_offset), line, font=fonts["body"], fill=colors["text"])
            y_offset += 40
        y_offset += 15
    
    # キーメッセージ（ハイライトボックス）
    if key_message and y_offset < height - 150:
        msg_y = height - 130
        # 背景ボックス
        box_padding = 20
        draw.rounded_rectangle(
            [left_margin - box_padding, msg_y - box_padding, 
             width - left_margin + box_padding, msg_y + 50 + box_padding],
            radius=10,
            fill=hex_to_rgba(colors["primary"], 30)
        )
        draw.text((left_margin + 10, msg_y), f"💡 {key_message[:70]}", 
                  font=fonts["body"], fill=colors["accent"])
    
    # キーワード（タグ）
    if keywords:
        kw_y = height - 60
        kw_x = width - 100
        for kw in reversed(keywords[:3]):
            kw_width = len(kw) * 18 + 20
            draw.rounded_rectangle(
                [kw_x - kw_width, kw_y - 12, kw_x, kw_y + 18],
                radius=12,
                fill=hex_to_rgba(colors["secondary"], 40)
            )
            draw.text((kw_x - kw_width // 2, kw_y + 3), kw, 
                      font=fonts["small"], fill=colors["muted"], anchor="mm")
            kw_x -= kw_width + 10


def wrap_text(text: str, font, max_width: int) -> List[str]:
    """テキストを指定幅で折り返し"""
    words = text.replace("　", " ").split()
    lines = []
    current_line = ""
    
    for word in words:
        test_line = f"{current_line} {word}".strip()
        try:
            bbox = font.getbbox(test_line)
            text_width = bbox[2] - bbox[0]
        except:
            text_width = len(test_line) * 30
        
        if text_width <= max_width:
            current_line = test_line
        else:
            if current_line:
                lines.append(current_line)
            current_line = word
    
    if current_line:
        lines.append(current_line)
    
    return lines if lines else [text[:50]]


def hex_to_rgb(hex_color: str) -> tuple:
    """16進数カラーをRGBタプルに変換"""
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def hex_to_rgba(hex_color: str, alpha: int) -> tuple:
    """16進数カラーをRGBAタプルに変換（alpha: 0-255）"""
    r, g, b = hex_to_rgb(hex_color)
    return (r, g, b, alpha)

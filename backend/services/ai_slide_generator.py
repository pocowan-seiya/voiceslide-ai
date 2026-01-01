"""
VoiceSlide AI - AI Design Architect
Professional-grade slide design using 3-step process:
1. Content Analysis
2. Design Style Definition
3. Slide Structure & Layout Generation
"""

import json
import base64
from typing import Dict, Any, List, Optional
import google.generativeai as genai

from config import GEMINI_API_KEY, VIDEO_WIDTH, VIDEO_HEIGHT


# =============================================================================
# STEP 1 & 2: Design Strategy Generation
# =============================================================================

DESIGN_STRATEGY_PROMPT = """# Role definition
あなたは、世界最高峰のクリエイティブエージェンシーに所属する「AIデザインアーキテクト」です。
あなたの使命は、提供されたプレゼンテーション全体の内容を深く理解し、統一感のある「オーダーメイドのスライドデザイン戦略」を設計することです。

# User Input Content
プレゼンテーションタイトル: {presentation_title}

スライド内容:
{slides_content}

---

# Process

### Step 1: Content Analysis (内容の分析)
1. **Core Message:** 最も伝えたい核心的なメッセージ（1文）
2. **Emotional Tone:** コンテンツが持つ感情的なトーン
3. **Key Concepts:** デザインのモチーフとなり得る重要なキーワード（3〜5個）
4. **Target Audience:** 想定される読者層

### Step 2: Design Style Definition (デザインスタイルの定義)
1. **Concept Name:** デザインのテーマ名と概要
2. **Color Palette:** 
   - primary: メインカラー (HEX)
   - secondary: サブカラー (HEX)
   - accent: アクセントカラー (HEX)
   - background_start: 背景グラデーション開始色 (HEX)
   - background_end: 背景グラデーション終了色 (HEX)
3. **Typography Direction:** タイトル用と本文用のスタイル方向性
4. **Visual Theme:** ビジュアルの方向性（抽象的な幾何学、有機的なライン、未来的、温かみなど）

# Output Format (JSON)
```json
{{
  "content_analysis": {{
    "core_message": "...",
    "emotional_tone": "...",
    "key_concepts": ["...", "...", "..."],
    "target_audience": "..."
  }},
  "design_style": {{
    "concept_name": "...",
    "concept_description": "...",
    "color_palette": {{
      "primary": "#...",
      "secondary": "#...",
      "accent": "#...",
      "background_start": "#...",
      "background_end": "#..."
    }},
    "typography_direction": "...",
    "visual_theme": "..."
  }}
}}
```

JSONのみを出力してください。
"""


# =============================================================================
# STEP 3: Individual Slide Design
# =============================================================================

SLIDE_DESIGN_PROMPT = """# Role
あなたはAIデザインアーキテクトです。以下のデザイン戦略に基づき、1枚の完璧なスライドをHTML/CSSで作成してください。

# Design Strategy
コンセプト: {concept_name}
説明: {concept_description}
感情トーン: {emotional_tone}
ビジュアルテーマ: {visual_theme}

カラーパレット:
- Primary: {primary}
- Secondary: {secondary}
- Accent: {accent}
- Background: {background_start} → {background_end}

# Slide Content
スライド番号: {slide_number} / {total_slides}
スライドタイプ: {slide_type}

タイトル: {title}
サブタイトル: {subtitle}
ポイント:
{points}
キーメッセージ: {key_message}

{image_section}

# Design Requirements

1. **サイズ**: 幅{width}px × 高さ{height}px
2. **フォント**: 'Noto Sans JP'を使用
3. **構成**: 「1枚のポスター」のように完成された美しい構図

## Layout Principles
- **視線誘導**: Z型またはF型の自然な視線の流れ
- **余白**: 呼吸感のある適切な余白（要素を詰め込みすぎない）
- **グリッド**: 暗黙のグリッドラインに沿った配置
- **階層**: 情報の重要度に応じた視覚的階層

## Visual Elements
スライドタイプに応じて適切なレイアウトを選択:

### タイトルスライドの場合
- 全画面背景グラデーション
- センター配置の大きなタイトル
- グラデーションテキストまたはアクセントカラーのハイライト
- 控えめなサブタイトル

### コンセプト・フロー図の場合
- 3ステップを視覚的に接続（矢印やライン）
- 各ステップにアイコン（絵文字）とラベル
- グラスモーフィズムカード
- 下部に印象的なキーメッセージ

### ポイントリストの場合
- 左右2分割レイアウト（テキスト + ビジュアル空間）
- 番号付きまたはアイコン付きのポイント
- アクセントカラーの左ボーダー
- 各ポイントに説明テキスト

### 引用・メッセージの場合
- 大きな引用符マーク
- センター配置の印象的なテキスト
- 控えめな背景装飾

## CSS Techniques to Use
- `linear-gradient` for backgrounds
- `backdrop-filter: blur()` for glass effects
- `-webkit-background-clip: text` for gradient text
- `box-shadow` for depth
- Appropriate `border-radius`
- Subtle `transform` for visual interest

# Output
完全なHTML（<!DOCTYPE html>から</html>まで）を出力してください。
CSSはすべて<style>タグ内に記述。
外部リソースはGoogle Fonts（Noto Sans JP）のみ。
説明は不要です。HTMLのみ。
"""

# Image section template for prompts
IMAGE_SECTION_TEMPLATE = """
# 使用する画像
以下の画像をスライドに効果的に配置してください：
- 画像URL: {image_url}
- 撮影者: {photographer} (Unsplash)

画像の配置オプション:
1. 背景画像として全面に配置（暗いオーバーレイ付き）
2. 右半分に配置（左にテキスト）
3. 上部バナーとして配置

**必ず画像を使用してください。**
<img>タグのsrc属性にそのまま画像URLを使用してください。
"""


def determine_slide_type(slide: Dict, slide_number: int, total_slides: int) -> str:
    """Determine the type of slide based on content and position"""
    slide_copy = slide.get("slide_copy", {})
    points = slide_copy.get("bullet_points") or slide.get("points", [])
    title = slide_copy.get("headline") or slide.get("title", "")
    
    if slide_number == 1:
        return "表紙（タイトルスライド）"
    elif slide_number == total_slides:
        return "まとめ・クロージング"
    elif not points:
        return "引用・メッセージ"
    elif len(points) == 3:
        if any(word in title for word in ["ステップ", "プロセス", "流れ", "→"]):
            return "フロー・プロセス図"
        return "3つのポイント・コンセプト提示"
    elif len(points) >= 4:
        return "要点リスト"
    else:
        return "コンテンツスライド"


async def generate_design_strategy(
    outline: Dict[str, Any],
    gemini_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Step 1 & 2: Analyze content and define design strategy
    """
    key = gemini_key or GEMINI_API_KEY
    if not key:
        raise ValueError("Gemini API key is required")
    
    genai.configure(api_key=key)
    
    # Format slides content
    slides = outline.get("slides", [])
    slides_content = ""
    for i, slide in enumerate(slides):
        slide_copy = slide.get("slide_copy", {})
        title = slide_copy.get("headline") or slide.get("title", "")
        points = slide_copy.get("bullet_points") or []
        key_msg = slide_copy.get("key_message") or ""
        
        slides_content += f"\n## スライド {i+1}: {title}\n"
        if points:
            slides_content += "ポイント:\n" + "\n".join([f"- {p}" for p in points]) + "\n"
        if key_msg:
            slides_content += f"キーメッセージ: {key_msg}\n"
    
    prompt = DESIGN_STRATEGY_PROMPT.format(
        presentation_title=outline.get("presentation_title", "プレゼンテーション"),
        slides_content=slides_content
    )
    
    try:
        model = genai.GenerativeModel("gemini-2.0-flash-exp")
        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                temperature=0.7
            )
        )
        
        strategy = json.loads(response.text)
        print(f"[Design Architect] Strategy: {strategy['design_style']['concept_name']}")
        return strategy
        
    except Exception as e:
        print(f"[Design Architect] Strategy generation failed: {e}")
        return get_fallback_strategy()


def get_fallback_strategy() -> Dict[str, Any]:
    """Fallback design strategy"""
    return {
        "content_analysis": {
            "core_message": "価値あるアウトプット",
            "emotional_tone": "知的で洗練された",
            "key_concepts": ["価値", "アウトプット", "成長"],
            "target_audience": "ビジネスパーソン"
        },
        "design_style": {
            "concept_name": "Cosmic Professional",
            "concept_description": "宇宙的な広がりと知的な深みを感じさせる、プロフェッショナルなデザイン",
            "color_palette": {
                "primary": "#F59E0B",
                "secondary": "#8B5CF6",
                "accent": "#06B6D4",
                "background_start": "#0f172a",
                "background_end": "#1e293b"
            },
            "typography_direction": "力強いサンセリフ体、クリーンで現代的",
            "visual_theme": "抽象的な幾何学と宇宙的なグラデーション"
        }
    }


async def generate_slide_html(
    slide: Dict[str, Any],
    slide_number: int,
    total_slides: int,
    strategy: Dict[str, Any],
    gemini_key: Optional[str] = None,
    image_info: Optional[Dict[str, str]] = None
) -> str:
    """
    Step 3: Generate individual slide HTML based on strategy
    """
    key = gemini_key or GEMINI_API_KEY
    if not key:
        raise ValueError("Gemini API key is required")
    
    genai.configure(api_key=key)
    
    # Extract slide content
    slide_copy = slide.get("slide_copy", {})
    title = slide_copy.get("headline") or slide.get("title", "")
    subtitle = slide_copy.get("subheadline") or slide.get("subtitle", "")
    raw_points = slide_copy.get("bullet_points") or slide.get("points", [])
    key_message = slide_copy.get("key_message") or ""
    
    # Format points
    points_str = "\n".join([f"- {p}" if isinstance(p, str) else f"- {p}" for p in raw_points]) if raw_points else "(なし)"
    
    # Extract strategy
    style = strategy.get("design_style", {})
    analysis = strategy.get("content_analysis", {})
    colors = style.get("color_palette", {})
    
    slide_type = determine_slide_type(slide, slide_number, total_slides)
    
    # Build image section if image provided
    if image_info:
        image_section = IMAGE_SECTION_TEMPLATE.format(
            image_url=image_info.get("url", ""),
            photographer=image_info.get("photographer", "Unknown")
        )
    else:
        image_section = ""
    
    prompt = SLIDE_DESIGN_PROMPT.format(
        concept_name=style.get("concept_name", "Modern Professional"),
        concept_description=style.get("concept_description", ""),
        emotional_tone=analysis.get("emotional_tone", "知的で洗練された"),
        visual_theme=style.get("visual_theme", ""),
        primary=colors.get("primary", "#F59E0B"),
        secondary=colors.get("secondary", "#8B5CF6"),
        accent=colors.get("accent", "#06B6D4"),
        background_start=colors.get("background_start", "#0f172a"),
        background_end=colors.get("background_end", "#1e293b"),
        slide_number=slide_number,
        total_slides=total_slides,
        slide_type=slide_type,
        title=title,
        subtitle=subtitle,
        points=points_str,
        key_message=key_message,
        image_section=image_section,
        width=VIDEO_WIDTH,
        height=VIDEO_HEIGHT
    )
    
    try:
        model = genai.GenerativeModel("gemini-2.0-flash-exp")
        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                temperature=0.8,
                max_output_tokens=4096
            )
        )
        
        html = response.text.strip()
        
        # Extract HTML from markdown code block if present
        if "```html" in html:
            html = html.split("```html")[1].split("```")[0].strip()
        elif "```" in html:
            html = html.split("```")[1].split("```")[0].strip()
        
        if not html.startswith("<!DOCTYPE") and not html.startswith("<html"):
            print(f"[Design Architect] Invalid HTML for slide {slide_number}, using fallback")
            return generate_fallback_html(slide, slide_number, total_slides, strategy)
        
        print(f"[Design Architect] Generated slide {slide_number}: {slide_type}")
        return html
        
    except Exception as e:
        print(f"[Design Architect] Slide {slide_number} error: {e}")
        return generate_fallback_html(slide, slide_number, total_slides, strategy)


def generate_fallback_html(
    slide: Dict[str, Any],
    slide_number: int,
    total_slides: int,
    strategy: Dict[str, Any]
) -> str:
    """Generate fallback HTML using strategy colors"""
    slide_copy = slide.get("slide_copy", {})
    style = strategy.get("design_style", {})
    colors = style.get("color_palette", {})
    
    title = slide_copy.get("headline") or slide.get("title", "")
    subtitle = slide_copy.get("subheadline") or slide.get("subtitle", "")
    raw_points = slide_copy.get("bullet_points") or slide.get("points", [])
    key_message = slide_copy.get("key_message") or ""
    
    primary = colors.get("primary", "#F59E0B")
    secondary = colors.get("secondary", "#8B5CF6")
    accent = colors.get("accent", "#06B6D4")
    bg_start = colors.get("background_start", "#0f172a")
    bg_end = colors.get("background_end", "#1e293b")
    
    points_html = ""
    icons = ["💡", "⭐", "🎯", "✨", "🚀", "💎"]
    for i, point in enumerate(raw_points):
        point_text = point if isinstance(point, str) else str(point)
        icon = icons[i % len(icons)]
        points_html += f'''
        <div class="point">
            <span class="icon">{icon}</span>
            <span class="text">{point_text}</span>
        </div>
        '''
    
    return f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;700;900&display=swap" rel="stylesheet">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            width: {VIDEO_WIDTH}px;
            height: {VIDEO_HEIGHT}px;
            font-family: 'Noto Sans JP', sans-serif;
            background: linear-gradient(135deg, {bg_start} 0%, {bg_end} 100%);
            color: #fff;
            padding: 60px 80px;
            display: flex;
            flex-direction: column;
            position: relative;
        }}
        .title {{
            font-size: 48px;
            font-weight: 900;
            margin-bottom: 16px;
            background: linear-gradient(135deg, {primary}, {accent});
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }}
        .subtitle {{
            font-size: 20px;
            color: #94A3B8;
            margin-bottom: 40px;
        }}
        .points {{
            flex: 1;
            display: flex;
            flex-direction: column;
            gap: 24px;
        }}
        .point {{
            display: flex;
            align-items: center;
            gap: 16px;
            padding: 24px;
            background: rgba(255,255,255,0.05);
            backdrop-filter: blur(10px);
            border-radius: 16px;
            border-left: 4px solid {primary};
        }}
        .icon {{ font-size: 28px; }}
        .text {{ font-size: 18px; line-height: 1.6; }}
        .key-message {{
            margin-top: auto;
            padding: 24px;
            text-align: center;
            font-size: 18px;
            color: #94A3B8;
            font-style: italic;
            border-top: 1px solid rgba(255,255,255,0.1);
        }}
        .slide-number {{
            position: absolute;
            bottom: 30px;
            right: 40px;
            font-size: 14px;
            color: #64748B;
        }}
    </style>
</head>
<body>
    <h1 class="title">{title}</h1>
    {f'<p class="subtitle">{subtitle}</p>' if subtitle else ''}
    <div class="points">
        {points_html}
    </div>
    {f'<div class="key-message">「{key_message}」</div>' if key_message else ''}
    <div class="slide-number">{slide_number} / {total_slides}</div>
</body>
</html>'''


async def generate_all_custom_slides(
    slides: List[Dict[str, Any]],
    job_id: str,
    gemini_key: Optional[str] = None,
    outline: Optional[Dict[str, Any]] = None
) -> List[str]:
    """
    Generate all slides using the AI Design Architect approach
    """
    import os
    from playwright.async_api import async_playwright
    from config import OUTPUT_DIR
    
    slides_dir = os.path.join(OUTPUT_DIR, f"{job_id}_slides")
    os.makedirs(slides_dir, exist_ok=True)
    
    # Step 1 & 2: Generate design strategy for the entire presentation
    if outline is None:
        outline = {"slides": slides}
    
    print("[Design Architect] Analyzing content and defining design strategy...")
    strategy = await generate_design_strategy(outline, gemini_key)
    
    # Save strategy and slide data for later use (feedback editing)
    save_slide_data(job_id, slides, strategy)
    
    # Step 3: Generate each slide with consistent strategy
    image_paths = []
    html_contents = []
    total_slides = len(slides)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        
        for i, slide in enumerate(slides):
            slide_number = i + 1
            
            # Step 3a: Fetch stock image for slide
            image_info = None
            try:
                from services.stock_images import get_image_for_slide, extract_image_keywords
                keywords = extract_image_keywords(slide, strategy)
                if keywords:
                    image_info = await get_image_for_slide(keywords)
                    if image_info:
                        print(f"[Design Architect] Fetched image for slide {slide_number}")
            except Exception as e:
                print(f"[Design Architect] Image fetch failed for slide {slide_number}: {e}")
            
            # Step 3b: Generate initial HTML with image
            html = await generate_slide_html(
                slide=slide,
                slide_number=slide_number,
                total_slides=total_slides,
                strategy=strategy,
                gemini_key=gemini_key,
                image_info=image_info
            )
            
            # Step 3b: AI Self-Review (auto-improve before showing to user)
            print(f"[Design Architect] Self-reviewing slide {slide_number}...")
            html = await self_review_slide(
                html=html,
                strategy=strategy,
                gemini_key=gemini_key
            )
            
            html_contents.append(html)
            
            # Render to image
            page = await browser.new_page(viewport={"width": VIDEO_WIDTH, "height": VIDEO_HEIGHT})
            await page.set_content(html)
            await page.wait_for_timeout(1500)
            
            output_path = os.path.join(slides_dir, f"slide_{slide_number:03d}.png")
            await page.screenshot(path=output_path, type="png")
            await page.close()
            
            image_paths.append(output_path)
        
        await browser.close()
    
    # Save HTML contents for feedback editing
    save_html_contents(job_id, html_contents)
    
    print(f"[Design Architect] Generated {len(image_paths)} slides with unified design strategy")
    return image_paths


# =============================================================================
# Slide Data Storage (for feedback editing)
# =============================================================================

_slide_data_cache: Dict[str, Dict[str, Any]] = {}

def save_slide_data(job_id: str, slides: List[Dict], strategy: Dict):
    """Save slide data and strategy for later feedback editing"""
    _slide_data_cache[job_id] = {
        "slides": slides,
        "strategy": strategy
    }

def get_slide_data(job_id: str) -> Optional[Dict[str, Any]]:
    """Get saved slide data"""
    return _slide_data_cache.get(job_id)

def save_html_contents(job_id: str, html_contents: List[str]):
    """Save generated HTML contents"""
    if job_id in _slide_data_cache:
        _slide_data_cache[job_id]["html_contents"] = html_contents

def get_html_content(job_id: str, slide_number: int) -> Optional[str]:
    """Get HTML content for a specific slide"""
    data = _slide_data_cache.get(job_id)
    if data and "html_contents" in data:
        idx = slide_number - 1
        if 0 <= idx < len(data["html_contents"]):
            return data["html_contents"][idx]
    return None

def update_html_content(job_id: str, slide_number: int, html: str):
    """Update HTML content for a specific slide"""
    if job_id in _slide_data_cache and "html_contents" in _slide_data_cache[job_id]:
        idx = slide_number - 1
        if 0 <= idx < len(_slide_data_cache[job_id]["html_contents"]):
            _slide_data_cache[job_id]["html_contents"][idx] = html


# =============================================================================
# AI Self-Review (Automatic improvement before showing to user)
# =============================================================================

AI_SELF_REVIEW_PROMPT = """# Role
あなたは世界クラスのプレゼンテーションデザイナーであり、厳格なクオリティレビュアーです。
生成されたスライドを批評的に評価し、改善してください。

# 現在のスライドHTML
```html
{current_html}
```

# デザイン戦略
コンセプト: {concept_name}
感情トーン: {emotional_tone}
カラーパレット: Primary={primary}, Secondary={secondary}, Accent={accent}

# レビュー観点

## 1. コピー（テキスト）
- タイトルは簡潔でインパクトがあるか？
- ポイントは具体的で理解しやすいか？
- 冗長な表現はないか？
- キーメッセージは心に残るか？

## 2. レイアウト
- 視覚的階層は明確か？
- 余白は適切か（詰め込みすぎ/スカスカ）？
- 視線の流れは自然か？
- 要素のバランスは良いか？

## 3. ビジュアル
- 色使いはブランドに合っているか？
- コントラストは十分か（読みやすさ）？
- アイコンは内容に合っているか？
- 装飾は適度か（過剰/不足）？

## 4. プロフェッショナリズム
- プレゼンの場で使えるクオリティか？
- 洗練された印象を与えるか？
- 細部まで完成されているか？

# 指示

1. 上記の観点でスライドを厳しく評価してください
2. 改善点を特定してください
3. 改善を反映した新しいHTMLを生成してください

**必ず何かを改善してください。** 完璧なスライドは存在しません。
コピーの言い回し、フォントサイズ、余白、色のトーン、アイコンなど、
何か1つでも良くできる点を見つけて改善してください。

# 出力
改善されたHTMLを出力してください（<!DOCTYPE html>から</html>まで）。
説明は不要です。HTMLのみ。
"""


async def self_review_slide(
    html: str,
    strategy: Dict[str, Any],
    gemini_key: Optional[str] = None
) -> str:
    """
    AI self-reviews and improves a slide before showing to user
    """
    key = gemini_key or GEMINI_API_KEY
    if not key:
        return html  # Return original if no key
    
    genai.configure(api_key=key)
    
    style = strategy.get("design_style", {})
    analysis = strategy.get("content_analysis", {})
    colors = style.get("color_palette", {})
    
    prompt = AI_SELF_REVIEW_PROMPT.format(
        current_html=html,
        concept_name=style.get("concept_name", ""),
        emotional_tone=analysis.get("emotional_tone", ""),
        primary=colors.get("primary", "#F59E0B"),
        secondary=colors.get("secondary", "#8B5CF6"),
        accent=colors.get("accent", "#06B6D4")
    )
    
    try:
        model = genai.GenerativeModel("gemini-2.0-flash-exp")
        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                temperature=0.7,
                max_output_tokens=4096
            )
        )
        
        improved_html = response.text.strip()
        
        # Extract HTML from markdown code block if present
        if "```html" in improved_html:
            improved_html = improved_html.split("```html")[1].split("```")[0].strip()
        elif "```" in improved_html:
            improved_html = improved_html.split("```")[1].split("```")[0].strip()
        
        if improved_html.startswith("<!DOCTYPE") or improved_html.startswith("<html"):
            print("[Self-Review] ✓ Slide improved")
            return improved_html
        else:
            print("[Self-Review] Invalid HTML, keeping original")
            return html
            
    except Exception as e:
        print(f"[Self-Review] Error: {e}, keeping original")
        return html


# =============================================================================
# Feedback-Based Slide Regeneration
# =============================================================================

FEEDBACK_REGENERATION_PROMPT = """# Role
あなたはAIデザインアーキテクトです。ユーザーからのフィードバックに基づき、スライドを改善してください。

# 現在のスライドHTML
```html
{current_html}
```

# デザイン戦略
コンセプト: {concept_name}
カラーパレット: Primary={primary}, Secondary={secondary}, Accent={accent}

# ユーザーフィードバック
{feedback}

# フィードバックタイプ
{feedback_type}

# 指示
1. ユーザーのフィードバックを正確に理解してください
2. 現在のデザインを基盤として、フィードバックを反映した改善を行ってください
3. デザインの統一感（色、フォント、スタイル）は維持してください
4. サイズは幅{width}px × 高さ{height}pxを維持してください

# 出力
改善されたHTMLを出力してください（<!DOCTYPE html>から</html>まで）。
説明は不要です。HTMLのみ。
"""


async def regenerate_slide_with_feedback(
    job_id: str,
    slide_number: int,
    feedback: str,
    feedback_type: str = "general",  # copy, layout, visual, general
    gemini_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Regenerate a single slide based on user feedback
    """
    import os
    from playwright.async_api import async_playwright
    from config import OUTPUT_DIR
    
    key = gemini_key or GEMINI_API_KEY
    if not key:
        raise ValueError("Gemini API key is required")
    
    # Get saved data
    slide_data = get_slide_data(job_id)
    if not slide_data:
        raise ValueError(f"Slide data not found for job {job_id}")
    
    current_html = get_html_content(job_id, slide_number)
    if not current_html:
        raise ValueError(f"HTML content not found for slide {slide_number}")
    
    strategy = slide_data.get("strategy", {})
    style = strategy.get("design_style", {})
    colors = style.get("color_palette", {})
    
    # Generate improved HTML based on feedback
    genai.configure(api_key=key)
    
    prompt = FEEDBACK_REGENERATION_PROMPT.format(
        current_html=current_html,
        concept_name=style.get("concept_name", ""),
        primary=colors.get("primary", "#F59E0B"),
        secondary=colors.get("secondary", "#8B5CF6"),
        accent=colors.get("accent", "#06B6D4"),
        feedback=feedback,
        feedback_type=feedback_type,
        width=VIDEO_WIDTH,
        height=VIDEO_HEIGHT
    )
    
    try:
        model = genai.GenerativeModel("gemini-2.0-flash-exp")
        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                temperature=0.7,
                max_output_tokens=4096
            )
        )
        
        new_html = response.text.strip()
        
        # Extract HTML from markdown code block if present
        if "```html" in new_html:
            new_html = new_html.split("```html")[1].split("```")[0].strip()
        elif "```" in new_html:
            new_html = new_html.split("```")[1].split("```")[0].strip()
        
        if not new_html.startswith("<!DOCTYPE") and not new_html.startswith("<html"):
            raise ValueError("Invalid HTML generated")
        
        # Render new version
        slides_dir = os.path.join(OUTPUT_DIR, f"{job_id}_slides")
        
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page(viewport={"width": VIDEO_WIDTH, "height": VIDEO_HEIGHT})
            await page.set_content(new_html)
            await page.wait_for_timeout(1500)
            
            # Save as new version
            new_path = os.path.join(slides_dir, f"slide_{slide_number:03d}.png")
            await page.screenshot(path=new_path, type="png")
            
            await page.close()
            await browser.close()
        
        # Update stored HTML
        update_html_content(job_id, slide_number, new_html)
        
        print(f"[Feedback] Regenerated slide {slide_number} based on: {feedback[:50]}...")
        
        return {
            "success": True,
            "slide_number": slide_number,
            "preview_url": f"/outputs/{job_id}_slides/slide_{slide_number:03d}.png",
            "feedback_applied": feedback
        }
        
    except Exception as e:
        print(f"[Feedback] Error regenerating slide {slide_number}: {e}")
        return {
            "success": False,
            "slide_number": slide_number,
            "error": str(e)
        }

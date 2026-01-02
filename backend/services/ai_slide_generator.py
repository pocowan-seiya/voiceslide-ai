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

# Color Theme Presets for user selection
COLOR_THEMES = {
    "cosmic": {
        "name": "Cosmic Dark",
        "description": "宇宙的な深みと神秘感",
        "primary": "#F59E0B",
        "secondary": "#8B5CF6",
        "accent": "#06B6D4",
        "background_start": "#0f172a",
        "background_end": "#1e293b"
    },
    "warm": {
        "name": "Warm Sunset",
        "description": "温かみのあるオレンジ・ゴールド",
        "primary": "#F97316",
        "secondary": "#DC2626",
        "accent": "#FBBF24",
        "background_start": "#1c1917",
        "background_end": "#292524"
    },
    "elegant": {
        "name": "Elegant Purple",
        "description": "エレガントな紫・ピンク",
        "primary": "#A855F7",
        "secondary": "#EC4899",
        "accent": "#F472B6",
        "background_start": "#0c0a1d",
        "background_end": "#1e1b4b"
    },
    "nature": {
        "name": "Nature Green",
        "description": "自然とリラックス",
        "primary": "#10B981",
        "secondary": "#059669",
        "accent": "#34D399",
        "background_start": "#022c22",
        "background_end": "#064e3b"
    },
    "ocean": {
        "name": "Ocean Blue",
        "description": "海のような開放感",
        "primary": "#3B82F6",
        "secondary": "#0EA5E9",
        "accent": "#38BDF8",
        "background_start": "#0c1a2c",
        "background_end": "#1e3a5f"
    },
    "mono": {
        "name": "Monochrome",
        "description": "シンプルでクリーン",
        "primary": "#FFFFFF",
        "secondary": "#A1A1AA",
        "accent": "#E4E4E7",
        "background_start": "#18181b",
        "background_end": "#27272a"
    }
}

DESIGN_STRATEGY_PROMPT = """# Role
あなたは世界最高峰のデザインスタジオ（IDEO、Appleの発表会チーム、Pentagram）を率いる
**シニア・アートディレクター兼チーフ・コピーライター**です。

# Mission
入力されたプレゼンテーション内容を解析し、単なる「説明資料」ではなく、
観客の感情を揺さぶり、魂に刻まれる**芸術作品（マスターピース）**としての
統一されたデザイン戦略を設計してください。

# Artistic Design Principles（芸術的基準）

## 1. Less is More（極限の削ぎ落とし）
- テキストは極限まで削る
- 1つのスライドに1つの強烈なメッセージのみ
- 箇条書きは最大3点まで

## 2. Visual Metaphor（視覚的メタファー）
- 「宇宙」という言葉に「星空の画像」を使うのは素人
- プロは「無限に広がる波紋」「暗闇に差す一筋の光」など、
  概念を象徴する抽象表現を選ぶ

## 3. Negative Space（余白の美学）
- 余白は「空き」ではなく「意味」である
- 視線を誘導するために大胆に余白を活かす
- 要素は少なく、インパクトを最大化

## 4. Cinematic Contrast（映画的対比）
- 光と影、静と動、マクロとミクロの対比を強調
- ドラマティックなビジュアルインパクト

# Good vs Bad（品質ベンチマーク）

❌ **凡庸なアウトプット**:
- コピー: 「インプットとアウトプットで価値を作る」
- 構成: 左に箇条書き、右にビジネスマンが握手している写真

✅ **芸術的作品としてのアウトプット**:
- コピー: 「あなたの呼吸が、価値に変わる。」
- 構成: 画面中央に黄金比で配置された微細な光の粒子。背景は深い漆黒。
- 意図: 「出すこと（呼吸）」が自然に価値を生むという哲学を視覚的に表現

---

# User Input Content
プレゼンテーションタイトル: {presentation_title}

スライド内容:
{slides_content}

{color_theme_instruction}

---

# Task: デザイン戦略の設計

### Step 1: Context Interpretation（哲学的解釈）
1. **Core Jewel:** 全体を貫く「ダイヤモンドのような一言」
2. **Emotional Tone:** 哲学的な深みと感情的なトーン
3. **Key Metaphors:** 視覚的メタファーになり得る抽象的概念（3つ）
4. **Target Soul:** 心を動かしたいターゲット層

### Step 2: Art Direction（アートディレクション）
1. **Concept Name:** 芸術的なデザイン戦略名
2. **Color Palette:** 感情を揺さぶる配色（質感・光沢感も考慮）
   - primary: メインカラー (HEX)
   - secondary: サブカラー (HEX)
   - accent: アクセントカラー (HEX)
   - background_start: 背景グラデーション開始色 (HEX)
   - background_end: 背景グラデーション終了色 (HEX)
3. **Typography Direction:** 書体の方向性（繊細/力強い/エレガント等）
4. **Visual Theme:** 視覚的世界観（抽象的な光の粒子、流れる水墨、宇宙的な広がりなど）

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
あなたは世界最高峰のデザインスタジオ（IDEO、Apple、Pentagram）に所属する
**シニア・アートディレクター**です。

単なる「スライド」ではなく、観客の魂に刻まれる**1枚の芸術作品**を創造してください。

# Artistic Principles（厳守）

## 1. Less is More
- テキストは**極限まで削る**
- 1スライド = 1メッセージ
- 箇条書きがあれば最大3点まで、各点は10文字以内

## 2. Visual Metaphor
- 直接的な表現は避ける
- 概念を象徴する**抽象的なビジュアル**を構築
- 例：「成長」→ 上昇する光の軌跡、「価値」→ 黄金の粒子

## 3. Negative Space（余白の美学）
- 余白は**意味**を持つ
- 要素は少なく、インパクトを最大化
- 画面の50%以上を余白にすることを恐れない

## 4. Cinematic Contrast
- 光と影のドラマティックな対比
- 大きなタイトル vs 繊細なディテール

# Design Strategy（統一されたスタイル）
コンセプト: {concept_name}
説明: {concept_description}
感情トーン: {emotional_tone}
ビジュアルテーマ: {visual_theme}

カラーパレット:
- Primary: {primary}
- Secondary: {secondary}
- Accent: {accent}
- Background: {background_start} → {background_end}

# This Slide
スライド番号: {slide_number} / {total_slides}
スライドタイプ: {slide_type}

## Raw Content（これを芸術に昇華させる）
タイトル: {title}
サブタイトル: {subtitle}
ポイント:
{points}
キーメッセージ: {key_message}

{image_section}

# Your Task: Copywriting + Art Direction

## Step 1: Copywriting（ダイヤモンドへの昇華）
提供されたテキストを、短く、鋭く、詩的な「ダイヤモンドのような言葉」に磨き上げてください。
- タイトルは**8文字以内**を目指す
- ポイントは各点**キーワード2-3語**に凝縮
- キーメッセージは心に残る**一文**に

## Step 2: Art Direction
- **構図**: 黄金比、三分割法、対角線配置を活用
- **配置**: 画面の重心を意識（例：右下3分の1に重心）
- **余白**: 大胆に使う。詰め込まない。
- **装飾**: 抽象的な光、グラデーション、微細な粒子のみ

# Technical Specs
サイズ: 幅{width}px × 高さ{height}px
フォント: 'Noto Sans JP' (Google Fonts)

## CSS Techniques
- `linear-gradient` で深みのある背景
- `backdrop-filter: blur()` でグラスモーフィズム
- `-webkit-background-clip: text` でグラデーションテキスト
- `box-shadow` で奥行き
- 大きな`border-radius`で柔らかさ

# Output
完全なHTML（<!DOCTYPE html>から</html>まで）を出力。
CSSはすべて<style>タグ内に記述。
外部リソースはGoogle Fonts（Noto Sans JP）のみ使用。
**説明は不要。HTMLのみ。**

# 絶対禁止事項（厳守）

❌ 字幕テキスト
❌ ナレーション・文字起こし
❌ 話し手の発言の引用
❌ 長い説明文（2文以上禁止）
❌ スライド下部の小さな追加テキスト
❌ 提供されたポイント以外の追加テキスト
❌ ありきたりなビジネス画像（握手、会議室など）

# 表示するもの（これだけ）

✅ 磨き上げたタイトル
✅ サブタイトル（必要なら）
✅ 凝縮されたポイント（最大3つ）
✅ キーメッセージ（1文）
✅ スライド番号（控えめに）
✅ 抽象的なビジュアル装飾
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
    gemini_key: Optional[str] = None,
    color_theme: Optional[str] = None  # 'cosmic', 'warm', 'elegant', 'nature', 'ocean', 'mono', or None for AI
) -> Dict[str, Any]:
    """
    Step 1 & 2: Analyze content and define design strategy
    color_theme: If specified, use preset. If None, AI will choose appropriate colors.
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
    
    # Build color theme instruction
    if color_theme and color_theme in COLOR_THEMES:
        theme = COLOR_THEMES[color_theme]
        color_theme_instruction = f"""
# 指定された配色テーマ
ユーザーは「{theme['name']}」テーマを選択しました。以下の配色を使用してください：
- Primary: {theme['primary']}
- Secondary: {theme['secondary']}
- Accent: {theme['accent']}
- Background Start: {theme['background_start']}
- Background End: {theme['background_end']}
"""
    else:
        color_theme_instruction = ""
    
    prompt = DESIGN_STRATEGY_PROMPT.format(
        presentation_title=outline.get("presentation_title", "プレゼンテーション"),
        slides_content=slides_content,
        color_theme_instruction=color_theme_instruction
    )
    
    try:
        model = genai.GenerativeModel("gemini-3.0-pro-preview")
        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                temperature=0.7
            )
        )
        
        strategy = json.loads(response.text)
        print(f"[Design Architect] Strategy: {strategy['design_style']['concept_name']}")
        
        # Force apply color theme if specified (override AI's choice)
        if color_theme and color_theme in COLOR_THEMES:
            theme = COLOR_THEMES[color_theme]
            print(f"[Design Architect] Forcing color theme: {theme['name']}")
            strategy['design_style']['color_palette'] = {
                "primary": theme['primary'],
                "secondary": theme['secondary'],
                "accent": theme['accent'],
                "background_start": theme['background_start'],
                "background_end": theme['background_end']
            }
        
        return strategy
        
    except Exception as e:
        print(f"[Design Architect] Strategy generation failed: {e}")
        return get_fallback_strategy(color_theme)


def get_fallback_strategy(color_theme: Optional[str] = None) -> Dict[str, Any]:
    """Fallback design strategy"""
    # Select colors based on theme or default to cosmic
    if color_theme and color_theme in COLOR_THEMES:
        theme = COLOR_THEMES[color_theme]
        colors = {
            "primary": theme['primary'],
            "secondary": theme['secondary'],
            "accent": theme['accent'],
            "background_start": theme['background_start'],
            "background_end": theme['background_end']
        }
    else:
        colors = {
            "primary": "#F59E0B",
            "secondary": "#8B5CF6",
            "accent": "#06B6D4",
            "background_start": "#0f172a",
            "background_end": "#1e293b"
        }
    
    return {
        "content_analysis": {
            "core_message": "価値あるアウトプット",
            "emotional_tone": "知的で洗練された",
            "key_concepts": ["価値", "アウトプット", "成長"],
            "target_audience": "ビジネスパーソン"
        },
        "design_style": {
            "concept_name": "Professional Design",
            "concept_description": "プロフェッショナルで洗練されたデザイン",
            "color_palette": colors,
            "typography_direction": "力強いサンセリフ体、クリーンで現代的",
            "visual_theme": "抽象的な幾何学とモダンなグラデーション"
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
    
    # Extract slide content (explicitly exclude transcript/speakers_words data)
    slide_copy = slide.get("slide_copy", {})
    title = slide_copy.get("headline") or slide.get("title", "")
    subtitle = slide_copy.get("subheadline") or slide.get("subtitle", "")
    raw_points = slide_copy.get("bullet_points") or slide.get("points", [])
    key_message = slide_copy.get("key_message") or ""
    
    # IMPORTANT: Explicitly exclude these fields - they should NOT appear on slides
    # - speakers_words (transcript text)
    # - call_to_action (not needed for display)
    # - note_for_designer (internal note)
    # - keywords (metadata only)
    
    # Format points (only clean bullet points, no transcript)
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
        model = genai.GenerativeModel("gemini-3.0-pro-preview")
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
    outline: Optional[Dict[str, Any]] = None,
    color_theme: Optional[str] = None,  # User-selected color theme
    progress_callback: Optional[callable] = None  # Progress callback(current, total, message)
) -> List[str]:
    """
    Generate all slides using the AI Design Architect approach
    """
    import os
    from playwright.async_api import async_playwright
    from config import OUTPUT_DIR
    
    slides_dir = os.path.join(OUTPUT_DIR, f"{job_id}_slides")
    os.makedirs(slides_dir, exist_ok=True)
    
    total_slides = len(slides)
    
    # Step 1 & 2: Generate design strategy for the entire presentation
    if outline is None:
        outline = {"slides": slides}
    
    print("[Design Architect] Analyzing content and defining design strategy...")
    if progress_callback:
        progress_callback(0, total_slides + 1, "デザイン戦略を生成中...")
    
    strategy = await generate_design_strategy(outline, gemini_key, color_theme)
    
    if progress_callback:
        progress_callback(1, total_slides + 1, f"スライド生成中 (0/{total_slides})")
    
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
            slide_type = determine_slide_type(slide, slide_number, total_slides)
            
            # Step 3a: Image generation temporarily disabled (API version compatibility)
            # TODO: Re-enable when google-generativeai supports response_modalities
            image_info = None
            
            # Step 3b: Generate HTML
            html = await generate_slide_html(
                slide=slide,
                slide_number=slide_number,
                total_slides=total_slides,
                strategy=strategy,
                gemini_key=gemini_key,
                image_info=image_info
            )
            
            # Step 3c: Self-review to check for transcript text and improve quality
            # Now runs on ALL slides to ensure no transcript/subtitle text remains
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
            await page.wait_for_timeout(1000)
            
            output_path = os.path.join(slides_dir, f"slide_{slide_number:03d}.png")
            await page.screenshot(path=output_path, type="png")
            await page.close()
            
            image_paths.append(output_path)
            print(f"[Design Architect] Completed slide {slide_number}/{total_slides}")
            
            # Update progress
            if progress_callback:
                progress_callback(slide_number + 1, total_slides + 1, f"スライド生成中 ({slide_number}/{total_slides})")
        
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

## 0. 字幕・ナレーションテキストの削除（最優先）
**まず最初に**以下をチェックし、存在すれば**必ず削除**してください：

❌ スライド下部の小さなテキスト（字幕のように見えるもの）
❌ 長い説明文や話し言葉のテキスト
❌ 文字起こし・ナレーションのような文章
❌ 「〜と思います」「〜ですね」のような話し言葉
❌ 2-3文以上続く長いテキストブロック
❌ 提供されたポイント以外の追加テキスト

**許可されるテキストのみ残す：**
✅ タイトル（大きく目立つ）
✅ サブタイトル（あれば）
✅ 箇条書きポイント（短く簡潔に）
✅ キーメッセージ（1文のみ）
✅ スライド番号

もし不要なテキストがあれば、**そのHTML要素を完全に削除**してください。

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

1. **まず字幕・ナレーションテキストがないかチェック。あれば削除！**
2. 上記の観点でスライドを厳しく評価してください
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
        model = genai.GenerativeModel("gemini-3.0-pro-preview")
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
        model = genai.GenerativeModel("gemini-3.0-pro-preview")
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

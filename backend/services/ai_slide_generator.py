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

# =============================================================================
# Layout Variation System - 8 Different Layout Types
# =============================================================================

LAYOUT_TYPES = {
    "center_hero": {
        "name": "Center Hero",
        "description": "中央配置の大きなタイトル、最小限の要素",
        "css_hints": """
            - タイトルを画面中央にどーんと配置
            - 余白たっぷり、要素は最小限
            - サブテキストはタイトル下に小さく
            - 背景にsubtle装飾（光の粒子やグラデーション円）
        """,
        "best_for": ["title", "closing", "quote"]
    },
    "left_heavy": {
        "name": "Left Heavy",
        "description": "左側にメインコンテンツ、右側に余白やビジュアル",
        "css_hints": """
            - 左60%にテキストコンテンツ
            - 右40%は余白または抽象的装飾
            - 左揃えのテキスト
            - 垂直方向は中央寄せ
        """,
        "best_for": ["points", "concept", "closing"]
    },
    "right_heavy": {
        "name": "Right Heavy",
        "description": "右側にメインコンテンツ、左側に余白",
        "css_hints": """
            - 右60%にテキストコンテンツ
            - 左40%は余白または抽象的装飾
            - 右揃えまたは左揃えのテキスト
            - 背景に左から流れるグラデーション
        """,
        "best_for": ["points", "concept", "quote"]
    },
    "split_horizontal": {
        "name": "Split Horizontal",
        "description": "上下2分割、上にタイトル、下にコンテンツ",
        "css_hints": """
            - 上部30%にタイトルエリア
            - 下部70%にコンテンツエリア
            - 横長のレイアウト感
            - 水平線やグラデーション境界
        """,
        "best_for": ["points", "concept", "closing"]
    },
    "split_vertical": {
        "name": "Split Vertical",
        "description": "左右2分割、均等配置",
        "css_hints": """
            - 左右50-50に分割
            - 片側にタイトル、片側にポイント
            - 垂直の区切り線やグラデーション
            - 対比を強調
        """,
        "best_for": ["comparison", "flow"]
    },
    "diagonal": {
        "name": "Diagonal",
        "description": "対角線配置、動的なレイアウト",
        "css_hints": """
            - 左上から右下への対角線を意識
            - タイトルは左上
            - コンテンツは右下方向に流れる
            - transform: skewで傾斜装飾
        """,
        "best_for": ["flow", "concept", "points"]
    },
    "minimal": {
        "name": "Minimal",
        "description": "極限までシンプル、1-2要素のみ",
        "css_hints": """
            - 画面の80%を余白に
            - 1つの強力なメッセージのみ
            - フォントサイズを大きく
            - 装飾なし、純粋なタイポグラフィ
        """,
        "best_for": ["quote", "key_message", "transition"]
    },
    "cards": {
        "name": "Cards Layout",
        "description": "カード型のコンテンツ配置",
        "css_hints": """
            - glassmorphismカードを使用
            - 2-3枚のカードを横並び
            - 各カードにアイコンとテキスト
            - hover効果的なshadow
        """,
        "best_for": ["points", "concept", "flow", "comparison"]
    }
}

# Track used layouts to avoid repetition
_used_layouts_cache: Dict[str, List[str]] = {}

def select_layout_for_slide(
    job_id: str,
    slide_number: int,
    total_slides: int,
    content_type: str,
    num_points: int = 0
) -> Dict[str, Any]:
    """
    Select an appropriate layout for each slide, ensuring variety.
    Avoids using the same layout consecutively.
    """
    # Initialize cache for this job
    if job_id not in _used_layouts_cache:
        _used_layouts_cache[job_id] = []
    
    used = _used_layouts_cache[job_id]
    
    # Title slide - always center_hero
    if slide_number == 1:
        layout_key = "center_hero"
    # Closing slide - center_hero or minimal
    elif slide_number == total_slides:
        layout_key = "minimal" if len(used) > 0 and used[-1] == "center_hero" else "center_hero"
    else:
        # Get suitable layouts for this content type
        suitable = []
        for key, layout in LAYOUT_TYPES.items():
            if content_type in layout.get("best_for", []):
                suitable.append(key)
        
        # If no suitable layouts, use all except center_hero
        if not suitable:
            suitable = ["left_heavy", "right_heavy", "split_horizontal", 
                       "split_vertical", "diagonal", "cards"]
        
        # Add minimal for slides with few points
        if num_points <= 2:
            suitable.append("minimal")
        
        # Remove the last used layout to avoid repetition
        if used:
            last_used = used[-1]
            suitable = [l for l in suitable if l != last_used]
        
        # Also try to avoid the second-to-last to increase variety
        if len(used) >= 2:
            second_last = used[-2]
            suitable = [l for l in suitable if l != second_last] or suitable
        
        # Select based on slide position for more variety
        if suitable:
            # Use slide_number to cycle through suitable layouts
            layout_key = suitable[(slide_number - 2) % len(suitable)]
        else:
            layout_key = "left_heavy"
    
    # Track usage
    used.append(layout_key)
    _used_layouts_cache[job_id] = used[-10:]  # Keep only last 10
    
    return {
        "key": layout_key,
        **LAYOUT_TYPES[layout_key]
    }

DESIGN_STRATEGY_PROMPT = """# Role definition
あなたは、世界最高峰のクリエイティブエージェンシーに所属する「AIデザインアーキテクト」です。
あなたの使命は、提供されたプレゼンテーション全体の内容を深く理解し、統一感のある「オーダーメイドのスライドデザイン戦略」を設計することです。

# User Input Content
プレゼンテーションタイトル: {presentation_title}

スライド内容:
{slides_content}

{color_theme_instruction}

---

# Process

### Step 1: Content Analysis (内容の分析)
1. **Core Message:** 最も伝えたい核心的なメッセージ（1文）
2. **Emotional Tone:** コンテンツが持つ感情的なトーン
3. **Key Concepts:** デザインのモチーフとなり得る重要なキーワード（3〜5個）
4. **Target Audience:** 想定される読者層

### Step 2: Design Style Definition (デザインスタイルの定義)
1. **Concept Name:** デザインのテーマ名と概要
2. **Color Palette:** コンテンツに最適な配色を選択
   - **重要**: 青系だけでなく、コンテンツの感情トーンに合った多様な配色を検討してください
   - 温かみのあるテーマ → オレンジ、ゴールド、レッド系
   - エレガントなテーマ → パープル、ピンク、マゼンタ系
   - 自然・安らぎ → グリーン、ターコイズ系
   - プロフェッショナル → ブルー、グレー系
   - 情熱・エネルギー → レッド、オレンジ系
   
   以下の形式で指定:
   - primary: メインカラー (HEX)
   - secondary: サブカラー (HEX)
   - accent: アクセントカラー (HEX)
   - background_start: 背景グラデーション開始色 (HEX、暗い色)
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
あなたは世界トップクラスの**プレゼンテーションデザイナー兼アートディレクター**です。
聴衆の心に一生残る「1枚の作品」としてのスライドを作成してください。

# ⚠️ IMPORTANT: 使用するレイアウト（厳守）
{layout_instruction}

---

# Goals（デザインゴール）
1. **メッセージの昇華**: テキストをそのまま載せるのではなく、メッセージを象徴する「言葉」と「ビジュアル」へ昇華させる
2. **視覚的インパクト**: 見た瞬間に心を掴む、強烈なファーストインプレッション
3. **究極の両立**: インパクトと理解しやすさを極限まで両立

# Design Strategy（統一デザイン戦略）
コンセプト: {concept_name}
説明: {concept_description}
感情トーン: {emotional_tone}
ビジュアルテーマ: {visual_theme}

カラーパレット:
- Primary: {primary}
- Secondary: {secondary}
- Accent: {accent}
- Background: {background_start} → {background_end}

# Slide Content（素材）
スライド番号: {slide_number} / {total_slides}
スライドタイプ: {slide_type}

タイトル: {title}
サブタイトル: {subtitle}
ポイント:
{points}
キーメッセージ: {key_message}

{image_section}

---

# Your Design Process

## Step 1: The Core Message（核心メッセージ）
提供されたテキストを見た瞬間に突き刺さる**究極まで削ぎ落としたコピー**に変換：
- タイトルは**8文字以内**を目指す
- 箇条書きは**キーワード2-3語**に凝縮
- 冗長な説明は一切排除

## Step 2: Design Philosophy（デザイン哲学）
なぜその配置、その色、その余白にするのかを意識：
- **感情トーン**に合わせた色温度
- **メッセージの重み**に応じたフォントサイズ
- **視線誘導**を計算した要素配置

## Step 3: Visual Composition（視覚構成）
- **黄金比・三分割法**を活用した配置
- **大胆な余白**（画面の40-60%を余白に）
- **視覚的階層**（タイトル > ポイント > 装飾）

## Step 4: Graphic Detail（グラフィックディテール）
CSSで表現する**質感と雰囲気**：
- 背景の**深み**（グラデーションの角度・色数）
- **光の当たり方**（グロー効果、ハイライト）
- **影の使い方**（box-shadow の距離・ぼかし）
- **質感**（ガラス効果、ノイズテクスチャ）

---

# Technical Specs

1. **サイズ**: 幅{width}px × 高さ{height}px
2. **フォント**: 'Noto Sans JP' (Google Fonts)
3. **完成度**: 「1枚のポスター」として額縁に入れられるクオリティ

## CSS Techniques
- `linear-gradient`（多角度、多色）for depth
- `radial-gradient` for light spots
- `backdrop-filter: blur()` for glass morphism
- `-webkit-background-clip: text` for gradient text
- `box-shadow`（複数レイヤー）for realistic depth
- `border-radius`（大きめ）for softness
- `transform: rotate/skew` for dynamic elements

# Output
完全なHTML（<!DOCTYPE html>から</html>まで）を出力してください。
CSSはすべて<style>タグ内に記述。
外部リソースはGoogle Fonts（Noto Sans JP）のみ。
説明は不要です。HTMLのみ。

## 絶対禁止事項（厳守）
以下は**絶対に**スライドに表示しないでください：

❌ 字幕テキスト
❌ ナレーション・文字起こし
❌ 話し手の発言の引用
❌ 長い説明文（2-3文以上）
❌ スライド下部の小さな追加テキスト
❌ 提供されたポイント以外の追加テキスト
❌ **画像のプレースホルダーテキスト**（例：「Image Here」「📷」「[画像]」など）
❌ **img タグや外部画像URL**（画像は使用しない）
❌ **画像生成プロンプトのテキスト表示**

## ビジュアル表現の方法（重要）
画像の代わりに**CSSのみで**抽象的なビジュアルを作成してください：

✅ **グラデーション背景** - linear-gradient, radial-gradient
✅ **グラスモーフィズムカード** - backdrop-filter: blur() + 半透明背景
✅ **CSSで作る形状** - border-radius, transform で作る円・四角
✅ **光のエフェクト** - box-shadow, グロー効果
✅ **装飾的なボーダー** - 色付きボーダー、グラデーションボーダー
✅ **抽象的パターン** - 繰り返しグラデーション

例：右側に青いグラデーション円を配置
```css
.visual-element {{
  position: absolute;
  right: 60px;
  top: 50%;
  transform: translateY(-50%);
  width: 300px;
  height: 300px;
  border-radius: 50%;
  background: radial-gradient(circle, #3B82F6 0%, transparent 70%);
  filter: blur(40px);
}}
```

## 表示するもの（これだけ）
✅ タイトル（headline）
✅ サブタイトル（subheadline）- あれば
✅ 箇条書きポイント（bullet_points）- 短く簡潔に
✅ キーメッセージ（key_message）- 1文のみ
✅ スライド番号
✅ CSS装飾（グラデーション、シェイプ、グロー効果）

上記以外のテキストは一切表示しないでください。
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
        return "title"  # Changed to English for LAYOUT_TYPES matching
    elif slide_number == total_slides:
        return "closing"  # Changed to English
    elif not points:
        return "quote"  # Changed to English
    elif len(points) == 3:
        if any(word in title for word in ["ステップ", "プロセス", "流れ", "→", "フロー"]):
            return "flow"  # Changed to English
        return "concept"  # Changed to English
    elif len(points) >= 4:
        return "points"  # Changed to English
    elif len(points) == 2:
        return "comparison"  # New: for 2-point slides
    else:
        return "points"  # Default to points


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
    job_id: str,  # Added for layout tracking
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
    
    # Select layout for variety (NEW)
    layout = select_layout_for_slide(
        job_id=job_id,
        slide_number=slide_number,
        total_slides=total_slides,
        content_type=slide_type,
        num_points=len(raw_points)
    )
    
    # Build layout instruction
    layout_instruction = f"""
**レイアウト: {layout['name']}**
{layout['description']}

**配置のヒント:**
{layout['css_hints']}

このレイアウトに**必ず従って**デザインしてください。前のスライドとは異なる配置になります。
"""
    
    print(f"[Design Architect] Slide {slide_number}: Using layout '{layout['name']}'")
    
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
        layout_instruction=layout_instruction,  # NEW
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
                job_id=job_id,  # Added for layout tracking
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
            
            # Step 3d: Post-processing - forcibly remove any remaining caption text
            print(f"[Design Architect] Post-processing slide {slide_number} (removing captions)...")
            html = remove_caption_text(html)
            
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
# HTML Post-Processing - Forcibly Remove Caption/Transcript Text
# =============================================================================

import re

def remove_caption_text(html: str) -> str:
    """
    Post-process HTML to remove any caption-like text that shouldn't be on slides.
    This is a safety net after AI generation and self-review.
    
    Removes:
    - Small text at bottom of slides
    - Long paragraph-like text
    - Text that looks like subtitles/narration
    """
    # Pattern 1: Remove elements with very small font-size (caption-like)
    # font-size: 10px, 11px, 12px, 13px, 14px patterns
    html = re.sub(
        r'<[^>]*style="[^"]*font-size:\s*1[0-4]px[^"]*"[^>]*>.*?</[^>]+>',
        '',
        html,
        flags=re.DOTALL | re.IGNORECASE
    )
    
    # Pattern 2: Remove elements positioned at absolute bottom with small text
    html = re.sub(
        r'<[^>]*style="[^"]*position:\s*absolute[^"]*bottom:\s*[0-2]0px[^"]*"[^>]*>.*?</[^>]+>',
        '',
        html,
        flags=re.DOTALL | re.IGNORECASE
    )
    
    # Pattern 3: Remove <p> tags with very long text (50+ characters, likely narration)
    # But keep short text and bullet points
    def filter_long_paragraphs(match):
        content = match.group(1)
        # If text is longer than 100 chars and doesn't look like a bullet point, remove it
        if len(content) > 100 and not content.strip().startswith(('•', '-', '・', '●', '○')):
            return ''
        return match.group(0)
    
    html = re.sub(
        r'<p[^>]*>([^<]+)</p>',
        filter_long_paragraphs,
        html,
        flags=re.IGNORECASE
    )
    
    # Pattern 4: Remove divs/spans with class containing "caption", "subtitle", "narration"
    html = re.sub(
        r'<[^>]*class="[^"]*(?:caption|subtitle|narration|transcript)[^"]*"[^>]*>.*?</[^>]+>',
        '',
        html,
        flags=re.DOTALL | re.IGNORECASE
    )
    
    # Pattern 5: Remove text that ends with conversational markers
    conversational_patterns = [
        r'と思います',
        r'ですね',
        r'ですよね',
        r'なんですね',
        r'じゃないですか',
        r'ということで',
    ]
    for pattern in conversational_patterns:
        html = re.sub(
            rf'<[^>]+>[^<]*{pattern}[^<]*</[^>]+>',
            '',
            html,
            flags=re.IGNORECASE
        )
    
    return html


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

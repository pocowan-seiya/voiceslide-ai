"""
VoiceSlide AI - AI Design Architect
Professional-grade slide design using 3-step process:
1. Content Analysis
2. Design Style Definition
3. Slide Structure & Layout Generation
"""

import json
import base64
import random
import asyncio
from typing import Dict, Any, List, Optional
from bs4 import BeautifulSoup
import google.generativeai as genai

from config import GEMINI_API_KEY, VIDEO_WIDTH, VIDEO_HEIGHT, get_video_dimensions
from services.ai_utils import safe_gemini_generate

# Global semaphore to limit concurrent browser instances
# Railway Pro Plan (24GB RAM, 24 vCPU) - increased for better concurrency
BROWSER_SEMAPHORE = asyncio.Semaphore(15)  # Increased to 15 for seminar support

# Queue tracking for visibility
queue_waiters: Dict[str, float] = {}  # job_id -> timestamp when started waiting
queue_active: Dict[str, float] = {}   # job_id -> timestamp when started processing

def get_queue_position(job_id: str) -> Dict[str, Any]:
    """Get current queue position and estimated wait time for a job."""
    if job_id in queue_active:
        return {"position": 0, "status": "processing", "estimated_wait": 0}
    
    if job_id not in queue_waiters:
        return {"position": -1, "status": "unknown", "estimated_wait": 0}
    
    # Count how many jobs are ahead in the queue
    my_timestamp = queue_waiters[job_id]
    position = sum(1 for ts in queue_waiters.values() if ts < my_timestamp) + 1
    
    # Estimate wait time: ~3 minutes per slide set, considering concurrent processing
    concurrent_capacity = 15
    estimated_minutes = max(0, (position - concurrent_capacity) * 3)
    
    return {
        "position": position,
        "status": "waiting",
        "estimated_wait": estimated_minutes,
        "active_count": len(queue_active),
        "waiting_count": len(queue_waiters)
    }

def update_html_text_content(html: str, new_copy: Dict[str, Any]) -> str:
    """
    Update text content in existing HTML using BeautifulSoup to preserve layout perfectly.
    """
    try:
        soup = BeautifulSoup(html, 'html.parser')
        
        # Update title (h1 or class="title")
        title_el = soup.find('h1') or soup.select_one('.title') or soup.find('div', class_='title')
        if title_el and new_copy.get("title"):
            title_el.string = new_copy["title"]
            
        # Update subtitle (h2,h3 or class="subtitle")
        subtitle_el = soup.find('h2') or soup.find('h3') or soup.select_one('.subtitle') or soup.find('div', class_='subtitle')
        if subtitle_el and new_copy.get("subtitle"):
            subtitle_el.string = new_copy["subtitle"]
            
        # Update points (ul or class="points")
        ul_el = soup.find('ul') or soup.select_one('.points') or soup.find('div', class_='points')
        if ul_el and new_copy.get("points"):
            # If it's a UL/OL, recreate LIs
            if ul_el.name in ['ul', 'ol']:
                ul_el.clear()
                for point in new_copy["points"]:
                    li = soup.new_tag('li')
                    li.string = str(point)
                    ul_el.append(li)
            else:
                # If it's a div, maybe clear and add p tags or just text
                # Safe bet: try to find existing list structure or just replace text
                pass
                
        return str(soup)
    except Exception as e:
        print(f"[DOM Update Error] {e}")
        return html  # Fallback to original if parsing fails


def fix_body_dimensions(html: str, target_width: int, target_height: int) -> str:
    """
    Post-process AI-generated HTML to fix body dimensions.
    AI often generates body { width: 1920px; height: 1080px; } regardless of prompt,
    causing content to shrink when viewport is different (e.g., portrait 1080x1920).
    """
    import re
    
    # Only fix if dimensions don't match the standard landscape (no-op for landscape)
    if target_width == 1920 and target_height == 1080:
        return html
    
    # Replace ALL 1920/1080 dimension references inside <style> blocks
    def fix_style_block(match):
        style_content = match.group(1)
        style_content = re.sub(r'width\s*:\s*1920\s*px', f'width: {target_width}px', style_content)
        style_content = re.sub(r'height\s*:\s*1080\s*px', f'height: {target_height}px', style_content)
        return f'<style>{style_content}</style>'
    
    html = re.sub(r'<style>(.*?)</style>', fix_style_block, html, flags=re.DOTALL)
    
    return html


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

# Font Style Presets for user selection
FONT_STYLES = {
    "gothic": {
        "name": "ゴシック体",
        "description": "モダンでクリーン",
        "font_family": "'Noto Sans JP', 'Hiragino Sans', sans-serif",
        "google_font": "Noto+Sans+JP:wght@400;700;900",
        "css_instruction": """
/* ゴシック体: モダンでクリーン */
body { font-family: 'Noto Sans JP', 'Hiragino Sans', sans-serif; }
h1, h2, h3 { font-weight: 900; letter-spacing: -0.02em; }
"""
    },
    "mincho": {
        "name": "明朝体",
        "description": "上品でエレガント",
        "font_family": "'Noto Serif JP', 'Hiragino Mincho', serif",
        "google_font": "Noto+Serif+JP:wght@400;700;900",
        "css_instruction": """
/* 明朝体: 上品でエレガント */
body { font-family: 'Noto Serif JP', 'Hiragino Mincho', serif; }
h1, h2, h3 { font-weight: 700; letter-spacing: 0.05em; }
p, li { line-height: 1.8; }
"""
    },
    "pop": {
        "name": "ポップ体",
        "description": "カジュアルで親しみやすい",
        "font_family": "'M PLUS Rounded 1c', 'Noto Sans JP', sans-serif",
        "google_font": "M+PLUS+Rounded+1c:wght@400;700;800",
        "css_instruction": """
/* ポップ体: カジュアルで親しみやすい */
body { font-family: 'M PLUS Rounded 1c', 'Noto Sans JP', sans-serif; }
h1, h2, h3 { font-weight: 800; letter-spacing: 0.02em; }
"""
    },
    "handwritten": {
        "name": "手書き風",
        "description": "温かみと個性",
        "font_family": "'Zen Maru Gothic', 'Noto Sans JP', sans-serif",
        "google_font": "Zen+Maru+Gothic:wght@400;700;900",
        "css_instruction": """
/* 手書き風: 温かみと個性 */
body { font-family: 'Zen Maru Gothic', 'Noto Sans JP', sans-serif; }
h1, h2, h3 { font-weight: 700; }
"""
    }
}

# =============================================================================
# Illustration Mode Templates and Mix Strategy
# =============================================================================

# 4 illustration template layouts (simplified)
ILLUSTRATION_TEMPLATES = {
    "center_hero": {
        "name": "Center Hero",
        "description": "イラストを中央に大きく配置、タイトルは上部"
    },
    "left_illustration": {
        "name": "Left Illustration",
        "description": "左にイラスト、右にテキスト"
    },
    "right_illustration": {
        "name": "Right Illustration", 
        "description": "右にイラスト、左にテキスト"
    },
    "full_bleed": {
        "name": "Full Bleed",
        "description": "イラストを画面いっぱいに、最小限のテキスト"
    }
}



def should_use_illustration_by_percentage(slide_type: str, slide_number: int, total_slides: int, percentage: int) -> bool:
    """
    Determine if a slide should have an illustration based on percentage.
    Uses a deterministic distribution strategy to ensure even coverage.
    
    Strategy:
    1. Always include first (Title) and last (Conclusion) slides if percentage >= 20%
    2. Distribute remaining slots evenly across the middle slides
    """
    if percentage <= 0:
        return False
    if percentage >= 100:
        return True
        
    # Calculate target number of illustrations
    target_count = max(1, round(total_slides * (percentage / 100)))
    
    # Priority slides determined by deterministic logic (simulating AI decision)
    selected_indices = set()
    
    # Always include first slide
    if target_count >= 1:
        selected_indices.add(1)
        
    # Always include last slide if we have enough budget and more than 1 slide
    if target_count >= 2 and total_slides > 1:
        selected_indices.add(total_slides)
        
    # Fill remaining slots using even distribution across middle slides
    remaining_slots = target_count - len(selected_indices)
    
    if remaining_slots > 0:
        # Available middle slides
        middle_slides = [i for i in range(2, total_slides) if i not in selected_indices]
        
        if middle_slides:
            # Calculate step size to distribute evenly
            import math
            step = len(middle_slides) / remaining_slots
            for i in range(remaining_slots):
                # Use math.floor to distribute from the beginning
                index = math.floor(i * step)
                if index < len(middle_slides):
                    selected_indices.add(middle_slides[index])
    
    return slide_number in selected_indices

def select_illustration_template(slide_number: int, total_slides: int, slide_type: str) -> str:
    """
    Select an illustration template for variety.
    Uses new layout names integrated into LAYOUT_TYPES.
    """
    import random
    
    templates = ["center_hero_with_image", "left_image", "right_image", "full_screen_image"]
    
    # First/last slides: prefer hero/full screen layouts
    if slide_number == 1 or slide_number == total_slides:
        hero_templates = ["center_hero_with_image", "full_screen_image"]
        return random.choice(hero_templates)
    
    # Others: random selection from all 4 templates
    return random.choice(templates)

def should_include_text_in_illustration(slide_number: int, total_slides: int, layout: str = "") -> bool:
    """
    Determine if the illustration should include text labels (for diagram-style).
    Returns False for image-heavy layouts where text would decrease visual impact.
    """
    # Don't include text in left/right illustration layouts (too small/cutoff risk)
    if layout in ["left_image", "right_image", "center_hero_with_image", "full_screen_image"]:
        return False
        
    # By default in standard mode + illustration, let's keep illustrations clean (no text)
    # This avoids conflict with slide content
    return False


# =============================================================================
# Dynamic Text Styles for Illustration Mode
# =============================================================================

# 6 text style variations - refined and elegant like standard slides
TEXT_STYLES = {
    "warm_coral": {
        "name": "Warm Coral",
        "emotions": ["exciting", "energetic", "innovative", "tech", "warm"],
        "title_css": """
            background: linear-gradient(135deg, #FF6B6B, #F97316, #FBBF24);
            -webkit-background-clip: text; 
            -webkit-text-fill-color: transparent;
            filter: drop-shadow(0 2px 10px rgba(249, 115, 22, 0.3));
        """,
        "subtitle_css": "color: #FED7AA;"
    },
    "elegant_purple": {
        "name": "Elegant Purple",
        "emotions": ["professional", "serious", "corporate", "calm"],
        "title_css": """
            background: linear-gradient(135deg, #C084FC, #A855F7, #9333EA);
            -webkit-background-clip: text; 
            -webkit-text-fill-color: transparent;
            filter: drop-shadow(0 2px 10px rgba(168, 85, 247, 0.3));
        """,
        "subtitle_css": "color: #E9D5FF;"
    },
    "ocean_blue": {
        "name": "Ocean Blue",
        "emotions": ["inspiring", "dreamy", "visionary", "creative"],
        "title_css": """
            background: linear-gradient(135deg, #38BDF8, #0EA5E9, #0284C7);
            -webkit-background-clip: text; 
            -webkit-text-fill-color: transparent;
            filter: drop-shadow(0 2px 10px rgba(14, 165, 233, 0.3));
        """,
        "subtitle_css": "color: #BAE6FD;"
    },
    "sunset_rose": {
        "name": "Sunset Rose",
        "emotions": ["friendly", "passionate", "emotional", "personal"],
        "title_css": """
            background: linear-gradient(135deg, #FB7185, #F43F5E, #E11D48);
            -webkit-background-clip: text; 
            -webkit-text-fill-color: transparent;
            filter: drop-shadow(0 2px 10px rgba(244, 63, 94, 0.3));
        """,
        "subtitle_css": "color: #FECDD3;"
    },
    "clean_white": {
        "name": "Clean White",
        "emotions": ["clean", "simple", "modern", "minimal"],
        "title_css": """
            color: #F8FAFC;
            text-shadow: 0 2px 20px rgba(248, 250, 252, 0.15);
        """,
        "subtitle_css": "color: #CBD5E1;"
    },
    "emerald_fresh": {
        "name": "Emerald Fresh",
        "emotions": ["powerful", "action", "urgent", "growth"],
        "title_css": """
            background: linear-gradient(135deg, #34D399, #10B981, #059669);
            -webkit-background-clip: text; 
            -webkit-text-fill-color: transparent;
            filter: drop-shadow(0 2px 10px rgba(16, 185, 129, 0.3));
        """,
        "subtitle_css": "color: #A7F3D0;"
    }
}


def select_text_style(strategy: Dict[str, Any], slide: Dict[str, Any] = None) -> Dict[str, str]:
    """
    Select appropriate text style based on content analysis.
    Returns the selected style dict with CSS.
    """
    import random
    
    # Get emotional tone from strategy
    content_analysis = strategy.get("content_analysis", {})
    emotional_tone = content_analysis.get("emotional_tone", "").lower()
    energy_level = slide.get("energy_level", "medium") if slide else "medium"
    
    # Mapping of emotions/tones to styles
    style_mapping = {
        # Energetic/exciting content
        "exciting": "warm_coral",
        "energetic": "warm_coral",
        "innovative": "warm_coral",
        "tech": "warm_coral",
        "future": "warm_coral",
        
        # Professional/calm content
        "professional": "elegant_purple",
        "serious": "elegant_purple",
        "corporate": "elegant_purple",
        "business": "elegant_purple",
        
        # Inspiring/creative content
        "inspiring": "ocean_blue",
        "dreamy": "ocean_blue",
        "visionary": "ocean_blue",
        "creative": "ocean_blue",
        
        # Warm/emotional content
        "warm": "sunset_rose",
        "friendly": "sunset_rose",
        "passionate": "sunset_rose",
        "emotional": "sunset_rose",
        "personal": "sunset_rose",
        
        # Clean/minimal content
        "clean": "clean_white",
        "simple": "clean_white",
        "modern": "clean_white",
        
        # Powerful/action content
        "powerful": "emerald_fresh",
        "action": "emerald_fresh",
        "urgent": "emerald_fresh",
    }
    
    # Find matching style based on emotional tone
    selected_style = None
    for keyword, style_name in style_mapping.items():
        if keyword in emotional_tone:
            selected_style = style_name
            break
    
    # Energy level override
    if energy_level == "high" and not selected_style:
        selected_style = random.choice(["warm_coral", "emerald_fresh"])
    elif energy_level == "low" and not selected_style:
        selected_style = random.choice(["clean_white", "elegant_purple"])
    
    # Default: random selection
    if not selected_style:
        selected_style = random.choice(list(TEXT_STYLES.keys()))
    
    return TEXT_STYLES[selected_style]

async def polish_copy_for_illustration(
    slide: Dict[str, Any],
    slide_number: int,
    total_slides: int,
    strategy: Dict[str, Any],
    gemini_key: str
) -> Dict[str, str]:
    """
    Polish slide copy for illustration mode using AI.
    Returns optimized title, subtitle, and points for impactful display.
    """
    import google.generativeai as genai
    
    key = gemini_key or GEMINI_API_KEY
    if not key:
        # Fallback to raw copy if no API key
        slide_copy = slide.get("slide_copy", {})
        return {
            "title": slide_copy.get("headline") or slide.get("title", f"スライド {slide_number}"),
            "subtitle": slide_copy.get("subheadline") or "",
            "points": slide_copy.get("bullet_points") or []
        }
    
    genai.configure(api_key=key)
    
    # Get raw copy
    slide_copy = slide.get("slide_copy", {})
    raw_title = slide_copy.get("headline") or slide.get("title", "")
    raw_subtitle = slide_copy.get("subheadline") or ""
    raw_points = slide_copy.get("bullet_points") or []
    key_message = slide_copy.get("key_message") or ""
    
    # Get personality for consistent tone
    personality = strategy.get("personality_analysis", {})
    tone = personality.get("tone", "プロフェッショナル")
    expressions = personality.get("characteristic_expressions", [])
    
    prompt = f"""# タスク
話し言葉の文字起こしテキストを、**プレゼンスライド用の端的なキャッチコピー**に変換してください。

## 入力（話し言葉のまま）
- タイトル: {raw_title}
- サブタイトル: {raw_subtitle}
- ポイント: {raw_points}
- キーメッセージ: {key_message}

## 🚨 絶対禁止（話し言葉を完全除去）

以下の表現は**絶対に使わないでください**：

### 語尾の話し言葉
❌「〜だと思う」「〜と思っていて」「〜かなと」
❌「〜していく」「〜していくっていう」
❌「〜なんですよね」「〜じゃないですか」
❌「〜できるようになってきた」
❌「〜っていうのも」「〜というか」
❌「〜なんですと」「〜なんです」
❌「〜わけですよ」「〜っていうわけで」

### 曖昧・不明瞭表現
❌「〜とか」「〜など」「〜みたいな」
❌「できなくはない」「しかない」
❌「何やら」「どうやら」「なんか」
❌「いろいろ」「さまざま」「様々な」
❌「ある意味」「結局」「そもそも」

### 冗長な接続
❌「それを〜することによって」
❌「〜をやることで」
❌「〜していくことが」
❌「〜というところで」「ところが」

## 🚨 長文禁止（要約すること）
- ポイントは必ず**1行（20文字以内）の体言止め**にすること。
- 文章（「〜です」「〜ます」）ではなく、キーワード（「〜の重要性」「〜による効果」）にする。
- 元のテキストが長い場合は、思い切って削り、核心のみを残してください。

## ✅ 正しい変換例

| 話し言葉（NG） | スライドコピー（OK） |
|--------------|-------------------|
| AIを使っていくビジョン | AIビジョン |
| 自分のエッジとして使っていこう | 自分だけのエッジに |
| できなくはないと思う | できる |
| YouTubeの発信を前からしたいなと思っていた | YouTube発信への想い |
| 実際にやってみた | 実践した結果 |
| そうなってくると工程が大変 | 工程の複雑さ |
| AIが出てきたことによっていろいろなことをAIができるようになってきた | AIで可能性が広がる |

## 🔄 完全言い換えルール（最重要）

**文字起こしの言葉をそのまま使わないでください。**

必ず以下のプロセスで変換：
1. 入力の**意味・メッセージ**を理解する
2. そのメッセージを**全く新しい言葉**で表現する
3. **スライドに最適化された短いフレーズ**にする

### 絶対NG
- 入力テキストの単語をそのままコピペ
- 長い文をただ短くしただけ
- 「〜がある」「〜ができる」で終わる文

### 絶対OK
- 2〜4語の名詞句（「AI×創造」「未来への扉」）
- インパクトのある体言止め
- キャッチコピーのような表現

## 最適化ルール

### タイトル
- **20文字以内**に凝縮
- 長い場合は**改行して2行**でもOK（例: "自分の才能が\n開花する"）
- 話し言葉の語尾は絶対禁止
- 体言止め or 動詞の終止形
- 例: 「AI×発信」「創造の扉」「可能性の拡張」

### サブタイトル
- **20文字以内**
- 話し言葉は絶対禁止（〜していく, 〜と思う など）
- タイトルを一言で補足
- なければ空文字

### ポイント（ある場合）
- 各**15文字以内**
- 話し言葉は絶対禁止
- 体言止めのみ
- 最大2個（多いと読めない）

## 出力形式（JSON）
```json
{{
  "title": "端的なタイトル",
  "subtitle": "補足（あれば）",
  "points": ["ポイント1", "ポイント2"]
}}
```
"""
    
    try:
        response_text = await safe_gemini_generate(
            "gemini-3-flash-preview",
            prompt,
            key,
            config=genai.GenerationConfig(
                response_mime_type="application/json",
                temperature=0.3,
                max_output_tokens=500
            )
        )
        
        result = json.loads(response_text)
        
        print(f"[Copy Polish] Slide {slide_number}: '{raw_title[:20]}...' → '{result.get('title', '')}'")
        
        return {
            "title": result.get("title") or raw_title,
            "subtitle": result.get("subtitle") or "",
            "points": result.get("points") or []
        }
        
    except Exception as e:
        print(f"[Copy Polish] Error for slide {slide_number}: {e}")
        # Fallback to raw copy
        return {
            "title": raw_title or f"スライド {slide_number}",
            "subtitle": raw_subtitle,
            "points": raw_points[:3] if raw_points else []
        }

def generate_illustration_template_html(
    template: str,
    title: str,
    subtitle: str,
    points: list,
    img_src: str,
    slide_number: int,
    total_slides: int,
    bg_start: str,
    bg_end: str,
    primary: str,
    secondary: str,
    title_font: str,
    text_style: Dict[str, str] = None  # Dynamic text style
) -> str:
    """
    Generate HTML for illustration slides based on the selected template.
    Supports 6 different layout variations.
    """
    
    # Common CSS base
    base_css = f'''
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            width: 1920px;
            height: 1080px;
            background: linear-gradient(135deg, {bg_start} 0%, {bg_end} 100%);
            font-family: {title_font};
            color: white;
            position: relative;
            overflow: hidden;
        }}
        .slide-number {{
            position: absolute;
            bottom: 30px;
            right: 40px;
            font-size: 16px;
            color: #64748B;
        }}
    '''
    
    # Get dynamic text styles
    title_style_css = ""
    subtitle_style_css = ""
    if text_style:
        title_style_css = text_style.get("title_css", "").format(primary=primary)
        subtitle_style_css = text_style.get("subtitle_css", "")
    
    # Build points HTML if available
    points_html = ""
    if points:
        icons = ["💡", "⭐", "🎯", "✨", "🚀", "💎"]
        for i, point in enumerate(points[:4]):  # Max 4 points for illustration slides
            point_text = point if isinstance(point, str) else str(point)
            icon = icons[i % len(icons)]
            points_html += f'<div class="point"><span class="icon">{icon}</span><span>{point_text}</span></div>'
    
    if template == "center_hero":
        # Center Hero: イラスト中央、タイトル上部（インパクト重視の大きな文字）
        return f'''<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;700;900&display=swap" rel="stylesheet">
    <style>
        {base_css}
        body {{
            display: flex;
            flex-direction: column;
            align-items: center;
            padding: 50px 80px;
        }}
        .title {{ font-size: 96px; font-weight: 900; text-align: center; margin-bottom: 30px; line-height: 1.1;
            {title_style_css if title_style_css else f"background: linear-gradient(135deg, {primary}, #fff); -webkit-background-clip: text; -webkit-text-fill-color: transparent; text-shadow: 0 4px 20px rgba(0,0,0,0.3);"}
        }}
        .subtitle {{ font-size: 42px; text-align: center; margin-bottom: 40px; font-weight: 500;
            {subtitle_style_css if subtitle_style_css else "color: #E2E8F0;"}
        }}
        .illustration-container {{ flex: 1; display: flex; align-items: center; justify-content: center; }}
        .illustration {{ max-width: 85%; max-height: 100%; object-fit: contain; border-radius: 20px; box-shadow: 0 20px 60px rgba(0,0,0,0.4); }}
    </style>
</head>
<body>
    <h1 class="title">{title}</h1>
    {f'<p class="subtitle">{subtitle}</p>' if subtitle else ''}
    <div class="illustration-container"><img src="{img_src}" class="illustration" alt=""></div>
    <div class="slide-number">{slide_number} / {total_slides}</div>
</body>
</html>'''
    
    elif template == "left_illustration":
        # Left Illustration: 左にイラスト、右にテキスト
        return f'''<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;700;900&display=swap" rel="stylesheet">
    <style>
        {base_css}
        body {{ display: flex; }}
        .left {{ width: 55%; height: 100%; display: flex; align-items: center; justify-content: center; padding: 40px; }}
        .illustration {{ max-width: 100%; max-height: 90%; object-fit: contain; border-radius: 16px; box-shadow: 0 15px 40px rgba(0,0,0,0.3); }}
        .right {{ width: 45%; padding: 60px 50px; display: flex; flex-direction: column; justify-content: center; }}
        .title {{ font-size: 72px; font-weight: 900; line-height: 1.1; margin-bottom: 30px;
            {title_style_css if title_style_css else f"background: linear-gradient(135deg, {primary}, #fff); -webkit-background-clip: text; -webkit-text-fill-color: transparent; text-shadow: 0 4px 20px rgba(0,0,0,0.3);"}
        }}
        .subtitle {{ font-size: 36px; margin-bottom: 40px; line-height: 1.4; font-weight: 500;
            {subtitle_style_css if subtitle_style_css else "color: #E2E8F0;"}
        }}
        .points {{ display: flex; flex-direction: column; gap: 28px; }}
        .point {{ display: flex; align-items: center; gap: 20px; padding: 28px 32px; background: rgba(255,255,255,0.12); border-radius: 18px; border-left: 6px solid {primary}; font-size: 40px; font-weight: 600; line-height: 1.3; }}
        .icon {{ font-size: 44px; }}
    </style>
</head>
<body>
    <div class="left"><img src="{img_src}" class="illustration" alt=""></div>
    <div class="right">
        <h1 class="title">{title}</h1>
        {f'<p class="subtitle">{subtitle}</p>' if subtitle else ''}
        {f'<div class="points">{points_html}</div>' if points_html else ''}
    </div>
    <div class="slide-number">{slide_number} / {total_slides}</div>
</body>
</html>'''
    
    elif template == "right_illustration":
        # Right Illustration: 右にイラスト、左にテキスト
        return f'''<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;700;900&display=swap" rel="stylesheet">
    <style>
        {base_css}
        body {{ display: flex; }}
        .left {{ width: 45%; padding: 60px 50px; display: flex; flex-direction: column; justify-content: center; }}
        .right {{ width: 55%; height: 100%; display: flex; align-items: center; justify-content: center; padding: 40px; }}
        .illustration {{ max-width: 100%; max-height: 90%; object-fit: contain; border-radius: 16px; box-shadow: 0 15px 40px rgba(0,0,0,0.3); }}
        .title {{ font-size: 72px; font-weight: 900; line-height: 1.1; margin-bottom: 30px;
            {title_style_css if title_style_css else f"background: linear-gradient(135deg, {primary}, #fff); -webkit-background-clip: text; -webkit-text-fill-color: transparent; text-shadow: 0 4px 20px rgba(0,0,0,0.3);"}
        }}
        .subtitle {{ font-size: 36px; margin-bottom: 40px; line-height: 1.4; font-weight: 500;
            {subtitle_style_css if subtitle_style_css else "color: #E2E8F0;"}
        }}
        .points {{ display: flex; flex-direction: column; gap: 28px; }}
        .point {{ display: flex; align-items: center; gap: 20px; padding: 28px 32px; background: rgba(255,255,255,0.12); border-radius: 18px; border-left: 6px solid {primary}; font-size: 40px; font-weight: 600; line-height: 1.3; }}
        .icon {{ font-size: 44px; }}
    </style>
</head>
<body>
    <div class="left">
        <h1 class="title">{title}</h1>
        {f'<p class="subtitle">{subtitle}</p>' if subtitle else ''}
        {f'<div class="points">{points_html}</div>' if points_html else ''}
    </div>
    <div class="right"><img src="{img_src}" class="illustration" alt=""></div>
    <div class="slide-number">{slide_number} / {total_slides}</div>
</body>
</html>'''
    
    elif template == "full_bleed":
        # Full Bleed: 画像オンリー（テキストなし）
        return f'''<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <style>
        {base_css}
        .full-image {{ position: absolute; top: 0; left: 0; width: 100%; height: 100%; object-fit: cover; }}
    </style>
</head>
<body>
    <img src="{img_src}" class="full-image" alt="">
    <div class="slide-number">{slide_number} / {total_slides}</div>
</body>
</html>'''
    
    else:
        # Fallback to center_hero
        return generate_illustration_template_html(
            "center_hero", title, subtitle, points, img_src,
            slide_number, total_slides, bg_start, bg_end, primary, secondary, title_font, text_style
        )

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
    },
    
    # Illustration Layouts (integrated)
    "center_hero_with_image": {
        "name": "Center Hero (with Illustration)",
        "description": "イラストを中央大きく、タイトルは上部に",
        "css_hints": """
            - AI生成イラスト（class="illustration"）を中央に大きく配置（画面の60-70%）
            - タイトルは上部に大きく（72-96px）
            - サブタイトルは控えめに
            - 余白は最小限でイラストを目立たせる
            - ポイントは不要（あっても1-2個のみ）
        """,
        "best_for": ["title", "closing", "concept"],
        "has_image": True,
        "image_size": (1080, 720),
        "image_aspect": "landscape"
    },
    "left_image": {
        "name": "Left Illustration",
        "description": "左にイラスト（高さフル）、右にテキスト",
        "css_hints": """
            - 左55%にAI生成イラスト（class="illustration"）を配置
            - 右45%にテキストエリア
            - タイトルは右側上部に大きく（72px）
            - ポイントは右側中央〜下部に配置
            - 境界線はぼかすかグラデーションで繋ぐ
            - 画像のアスペクト比は縦長（3:4）
        """,
        "best_for": ["introduction", "points", "comparison"],
        "has_image": True,
        "image_size": (540, 720),
        "image_aspect": "portrait"
    },
    "right_image": {
        "name": "Right Illustration",
        "description": "右にイラスト（高さフル）、左にテキスト",
        "css_hints": """
            - 右55%にAI生成イラスト（class="illustration"）を配置
            - 左45%にテキストエリア
            - タイトルは左側上部に大きく（72px）
            - ポイントは左側中央〜下部に配置
            - 境界線はぼかすかグラデーションで繋ぐ
            - 画像のアスペクト比は縦長（3:4）
        """,
        "best_for": ["introduction", "points", "comparison"],
        "has_image": True,
        "image_size": (540, 720),
        "image_aspect": "portrait"
    },
    "full_screen_image": {
        "name": "Full Screen Image",
        "description": "全面イラスト、テキストはオーバーレイ",
        "css_hints": """
            - 画面全体にイラストを配置（100%幅・高さ）
            - テキストには必ず半透明の黒背景（backdrop-filter: blur）を追加し可読性確保
            - タイトルは中央または下部に配置
            - 映画ポスターのようなレイアウト
            - コンテンツは最小限に
        """,
        "best_for": ["title", "closing", "powerful_message"],
        "has_image": True,
        "image_size": (1080, 720),
        "image_aspect": "landscape"
    }
}

# =============================================================================
# Portrait (9:16) Layout Types - Vertical-first designs
# =============================================================================

PORTRAIT_LAYOUT_TYPES = {
    "top_hero": {
        "name": "Top Hero (Portrait)",
        "description": "上部にタイトル大きく、下部にポイントを縦積み",
        "css_hints": """
            - 画面上部30%にタイトルを大きく配置（font-size: clamp(2rem, 5vh, 3.5rem)）
            - 下部70%にポイントを**縦に積む**（flex-direction: column）
            - カードやポイントは**横並び禁止**（1列のみ）
            - パディング: 40px 40px
            - 各カードは width: 100% で画面幅いっぱい
            - 余白を大きく取る
        """,
        "best_for": ["title", "concept", "points"]
    },
    "stacked_cards": {
        "name": "Stacked Cards (Portrait)",
        "description": "カードを縦に積み上げるShort動画向けレイアウト",
        "css_hints": """
            - カードを**縦に積む**（flex-direction: column, gap: 16px）
            - 横並び・2列配置禁止
            - 各カードはglassmorphism（backdrop-filter: blur）
            - カード幅は画面の90%
            - タイトルは上部に20-30pxで配置
            - ポイントは各カード内に1行ずつ
        """,
        "best_for": ["points", "concept", "comparison", "flow"]
    },
    "full_center": {
        "name": "Full Center (Portrait)",
        "description": "縦画面中央に1つのメッセージ、余白重視",
        "css_hints": """
            - 画面中央にタイトルを**1つだけ**大きく配置
            - font-size: clamp(2.5rem, 6vh, 4rem)
            - 余白を画面の60%以上取る
            - サブテキストは1行のみ（15文字以内）
            - 背景にsubtle装飾（radial-gradient光の粒子）
            - 純粋なタイポグラフィで勝負
        """,
        "best_for": ["quote", "key_message", "closing", "transition"]
    },
    "top_bottom_split": {
        "name": "Top-Bottom Split (Portrait)",
        "description": "上下2分割、上にビジュアル/タイトル、下にコンテンツ",
        "css_hints": """
            - 上部40%にタイトル（大きめ、中央揃え）
            - 下部60%にコンテンツ（ポイントを縦積み）
            - 区切り: グラデーションの境界線
            - 下部には背景をわずかに変えて対比
            - ポイントは左寄せ、border-leftでアクセント
        """,
        "best_for": ["points", "concept", "introduction"]
    }
}


# Track used layouts to avoid repetition
_used_layouts_cache: Dict[str, List[str]] = {}

def select_layout_for_slide(
    job_id: str,
    slide_number: int,
    total_slides: int,
    content_type: str,
    num_points: int = 0,
    is_illustration_mode: bool = False,  # illustration mode flag
    is_portrait: bool = False  # Portrait (9:16) mode flag
) -> Dict[str, Any]:
    """
    Select an appropriate layout for each slide, ensuring variety.
    Avoids using the same layout consecutively.
    Standard layouts focus on typography and readability.
    For illustration-enhanced slides, uses integrated image-focused layouts.
    
    If no cached layout is found (new design or regeneration), generates one using AI 
    or fallback logic based on content type.
    """
    # Initialize cache for this job
    if job_id not in _used_layouts_cache:
        _used_layouts_cache[job_id] = []
    
    used = _used_layouts_cache[job_id]
    
    # Determine available layouts based on illustration mode
    available_layouts = []
    if is_illustration_mode:
        # Filter for layouts that have "has_image": True
        available_layouts = [key for key, layout in LAYOUT_TYPES.items() if layout.get("has_image")]
        # Prioritize specific layouts for title/closing in illustration mode
        if slide_number == 1:
            layout_key = "center_hero_with_image"
        elif slide_number == total_slides:
            # Alternate full_screen_image and center_hero_with_image for closing
            layout_key = "full_screen_image" if len(used) > 0 and "center_hero_with_image" in used[-1] else "center_hero_with_image"
        else:
            # Alternate between left_image, right_image, center_hero_with_image for middle slides
            illustration_specific_layouts = ["left_image", "right_image", "center_hero_with_image"]
            
            # Remove last used to avoid repetition
            if used:
                last_used = used[-1]
                available_for_cycle = [l for l in illustration_specific_layouts if l != last_used]
            else:
                available_for_cycle = illustration_specific_layouts
            
            # Cycle through layouts
            layout_key = available_for_cycle[(slide_number - 2) % len(available_for_cycle)] if available_for_cycle else "left_image"
    else:
        # === Portrait Mode ===
        if is_portrait:
            available_layouts = list(PORTRAIT_LAYOUT_TYPES.keys())
            
            # Title/closing slides
            if slide_number == 1 or slide_number == total_slides:
                layout_key = "full_center"
            else:
                # Cycle through portrait layouts
                portrait_cycle = ["top_hero", "stacked_cards", "top_bottom_split"]
                if used:
                    portrait_cycle = [l for l in portrait_cycle if l != used[-1]] or portrait_cycle
                layout_key = portrait_cycle[(slide_number - 2) % len(portrait_cycle)]
            
            # Track and return from portrait types
            used.append(layout_key)
            _used_layouts_cache[job_id] = used[-10:]
            return {"key": layout_key, **PORTRAIT_LAYOUT_TYPES[layout_key]}
        
        # === Standard (Landscape) Mode ===
        # Standard mode: filter for layouts that do NOT have "has_image"
        available_layouts = [key for key, layout in LAYOUT_TYPES.items() if not layout.get("has_image")]
        
        # Title slide - always center_hero
        if slide_number == 1:
            layout_key = "center_hero"
        # Closing slide - center_hero or minimal
        elif slide_number == total_slides:
            layout_key = "minimal" if len(used) > 0 and used[-1] == "center_hero" else "center_hero"
        else:
            # Get suitable layouts for this content type from non-image layouts
            suitable = []
            for key in available_layouts:
                layout = LAYOUT_TYPES[key]
                if content_type in layout.get("best_for", []):
                    suitable.append(key)
            
            # If no suitable layouts, use a default set of non-image layouts
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

# ⚠️ コピー表現の絶対ルール（最最最重要 - 違反禁止）

スライドに表示するテキストは**提供されたコピーをそのまま使う**こと。
AIが言葉を変更・追加・言い換えすることは**一切禁止**。

## 許可されていること
✅ 提供されたテキストをそのまま表示する
✅ レイアウトや装飾でデザインを工夫する
✅ フォントサイズや配置を調整する

## 絶対禁止（違反は認められない）
❌ 言葉を言い換える
❌ よりキャッチーな表現に変更する
❌ ビジネス用語・専門用語に置き換える
❌ 要約して別の言葉で表現する
❌ 提供されたテキストにない言葉を追加する

## 確認
「このスライドの言葉は、提供されたコピーと完全に一致しているか？」
→ YES → 続行 | NO → 修正

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

# 🎭 話者のパーソナリティ（最重要）
{personality_section}

**パーソナリティを反映させる方法:**
- **コピー**: 話者の口調・表現を維持、その人らしい言葉遣いで
- **デザイン**: パーソナリティに合った雰囲気（カジュアルならポップに、真面目なら洗練に）
- **バランス**: その人らしさを保ちながら、インパクトのあるデザインを実現

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

## Step 1: The Core Message（核心メッセージの整理）
**元の表現を活かしながら**読みやすく整理：
- タイトルは**元のキーワードをそのまま使用**
- 箇条書きは**話者の言葉**で表現（勝手な言い換えNG）
- 長文のみ短縮（意味を変えずに）

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

## ⚠️ タイトル・テキストの色（絶対禁止ルール）

**⛔ タイトルやサブタイトルに暗い色を絶対に使用しないでください！**

### ❌ 絶対禁止の色（単色もグラデーションも禁止）:
- 黒（#000, #111, #222, #333, #444, black など）
- 茶色（brown, #8B4513, #A0522D, #6B4423, sienna, chocolate など）
- 暗いグレー（#555, #666, #777, dimgray, darkgray など）
- 暗い緑（#2D3A2D, darkgreen, #1A3A1A など）
- 暗い青（#1A1A3A, midnightblue, #2A2A4A など）
- **グラデーションに上記の暗い色を含めることも禁止**

### ✅ 必ず使う明るい色:
- 白（#FFFFFF, #F8FAFC, #FFF）← 最も安全
- 明るいオレンジ系（#FF6B6B, #F97316, #FFAA00）
- 明るいピンク系（#FF69B4, #FF85A2, #FFA0C0）
- 明るいパープル系（#A855F7, #C084FC, #D8B4FE）
- 明るいシアン系（#06B6D4, #22D3EE, #67E8F9）
- 明るいゴールド系（#FFD700, #FFC107, #FBBF24）

### 正しい例（これを参考に）:
```css
.title {{ color: white; }}  /* ベスト */
.title {{ background: linear-gradient(135deg, #FF6B6B, #F97316); -webkit-background-clip: text; color: transparent; }}  /* 明るいグラデ */
.title {{ background: linear-gradient(135deg, #FF85A2, #A855F7); -webkit-background-clip: text; color: transparent; }}  /* ピンク→パープル */
```

### 間違った例（使用禁止！）:
```css
.title {{ color: #333; }}  /* ❌ 暗い単色 */
.title {{ color: #5D2E0C; }}  /* ❌ 茶色 */
.title {{ background: linear-gradient(to bottom, #8B4513, #5D2E0C); }}  /* ❌ 暗いグラデーション */
.title {{ background: linear-gradient(135deg, #2D2D2D, #444444); }}  /* ❌ 暗いグレーのグラデーション */
```

# Output
完全なHTML（<!DOCTYPE html>から</html>まで）を出力してください。
CSSはすべて<style>タグ内に記述。
外部リソースはGoogle Fontsのみ使用可能（{font_import}）。
説明は不要です。HTMLのみ。
{font_instruction}

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

## タイポグラフィの絶対ルール（必須CSS）

**⚠️ テキストが途中で切れないように、以下のCSSを必ず適用してください：**

```css
/* 必須: タイトルは必ず全文表示（切れ禁止、2行表記も許可） */
h1, h2, .title, .headline {{
  word-break: keep-all;      /* 日本語の単語を分割しない */
  white-space: normal;       /* 自然に折り返す（2行もOK） */
  overflow: visible;         /* はみ出しを見せる（hidden禁止） */
  text-overflow: clip;       /* ellipsis禁止（...で切れない） */
  font-size: clamp(2rem, 4vw, 4rem);  /* 自動調整されるサイズ */
  line-height: 1.2;          /* 2行の場合も読みやすく */
  max-width: 90%;            /* 左右に余白を確保 */
  padding: 0 20px;           /* 左右の余白 */
  text-align: center;        /* 中央揃えで見栄え向上 */
  margin: 0 auto;            /* 中央に配置 */
}}

/* サブタイトル・本文も同様 */
h3, p, .subtitle, .subheadline {{
  word-break: keep-all;
  white-space: normal;
  overflow: visible;
  line-height: 1.4;
  max-width: 100%;
}}

/* 必須: コンテンツが画面内に収まるように（切れ禁止） */
body {{
  padding: 40px 50px !important;  /* 十分な内側余白 */
  box-sizing: border-box;
  overflow: visible !important;  /* 切れ禁止（hiddenは使わない） */
}}

/* ポイントカードも切れないように */
.point, .card {{
  white-space: normal;
  overflow: visible;
  word-break: keep-all;
}}
```

**⚠️ 絶対禁止（テキスト切れの原因）:**
❌ `text-overflow: ellipsis` （...で切れる）
❌ `overflow: hidden` + `white-space: nowrap` の組み合わせ
❌ `max-height` で高さを制限してテキストを隠す

**✅ 代わりにすること:**
- テキストが長い場合は**フォントサイズを小さくする**
- 必要なら**複数行に折り返す**
- タイトルは**必ず全文表示**（省略禁止）


## レイアウトのバランス（重要）
**不均衡な2カラムレイアウトは禁止**です：

❌ **禁止**: 左側が空白で右側にテキストが集中
❌ **禁止**: 片側にコンテンツがなく不均衡
❌ **禁止**: カラムの一方が極端に小さい

✅ **推奨**: コンテンツが少ない場合は**センター配置**
✅ **推奨**: 2カラムを使う場合は**両側にバランス良くコンテンツを配置**
✅ **推奨**: 左右どちらかが空く場合は**1カラムで中央揃え**

**レイアウト判断基準**:
- ポイントが3つ以下 → センター配置を優先
- ポイントが4つ以上 → 2カラムまたはグリッドを検討
- 片側が空く場合 → 装飾的な要素（グラデーション円など）で埋める

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
    color_theme: Optional[str] = None,
    design_preference: Optional[str] = None,
    copy_style_request: Optional[str] = None,
    facecam_position: Optional[str] = None,
    facecam_size: Optional[int] = None
) -> Dict[str, Any]:
    """
    Step 1 & 2: Analyze content and define design strategy
    color_theme: If specified, use preset. If None, AI will choose appropriate colors.
    design_preference: Free-form user requirements to incorporate into design.
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
    
    # Build design preference instruction
    design_preference_instruction = ""
    if design_preference:
        design_preference_instruction = f"""
# ユーザーからのデザイン要望
以下のユーザーからの要望を**必ず**反映してください：
「{design_preference}」

この要望を最優先で取り入れたデザインを生成してください。
"""

    # Build copy style instruction
    copy_style_instruction = ""
    if copy_style_request:
        copy_style_instruction = f"""
# ユーザーからのコピー（文章表現）要望
以下のライティングスタイルの要望を**全スライドに適用**してください：
「{copy_style_request}」

スライドのタイトル、サブタイトル、ポイント、キーメッセージなど、すべてのテキスト要素にこのスタイルを反映してください。
"""
    
    # Build PiP avoidance instruction
    pip_avoidance_instruction = ""
    if facecam_position:
        pos_labels = {
            "top-left": "左上",
            "top-right": "右上",
            "bottom-left": "左下",
            "bottom-right": "右下"
        }
        pos_label = pos_labels.get(facecam_position, facecam_position)
        pip_avoidance_instruction = f"""
# 顔出しワイプ（PiP）回避エリア
動画の{pos_label}に顔出しワイプ（円形オーバーレイ）が配置されます。
**全スライドで{pos_label}のエリア（約スライド幅25%×高さ25%）には重要なテキストや要素を配置しないでください。**
タイトル、ポイント、キーメッセージなどのテキストはワイプと被らない位置にレイアウトしてください。
"""

    prompt = DESIGN_STRATEGY_PROMPT.format(
        presentation_title=outline.get("presentation_title", "プレゼンテーション"),
        slides_content=slides_content,
        color_theme_instruction=color_theme_instruction + design_preference_instruction + copy_style_instruction + pip_avoidance_instruction
    )
    
    try:
        response_text = await safe_gemini_generate(
            "gemini-3-flash-preview",
            prompt,
            key,
            config=genai.GenerationConfig(
                response_mime_type="application/json",
                temperature=0.7
            )
        )
        
        strategy = json.loads(response_text)
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
        
        # Include personality analysis from outline
        personality = outline.get("personality_analysis", {})
        if personality:
            strategy["personality_analysis"] = personality
            print(f"[Design Architect] Personality: {personality.get('tone', 'N/A')}")
        
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
    job_id: str,
    gemini_key: Optional[str] = None,
    image_info: Optional[Dict[str, str]] = None,
    text_density: str = "standard",
    is_illustration_mode: bool = False,
    video_width: int = VIDEO_WIDTH,
    video_height: int = VIDEO_HEIGHT
) -> str:
    """
    Step 3: Generate individual slide HTML based on strategy.
    For illustration mode, uses ILLUSTRATION_LAYOUT_TYPES for image-focused designs.
    """
    key = gemini_key or GEMINI_API_KEY
    if not key:
        raise ValueError("Gemini API key is required")
    
    genai.configure(api_key=key)
    
    # Extract slide content (explicitly exclude transcript/speakers_words data)
    slide_copy = slide.get("slide_copy", {})
    title = slide_copy.get("headline") or slide.get("title", "")
    subtitle = slide_copy.get("subheadline") or slide.get("subtitle", "")
    
    # For "simple" mode, omit bullet points
    if text_density == "simple":
        raw_points = []  # No bullet points in simple mode
        key_message = ""  # No key message either
        print(f"[Design Architect] Slide {slide_number}: Simple mode (title + headline only)")
    else:
        # Standard mode
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
    
    # Copy style instruction from user request (injected at per-slide level for strong influence)
    copy_style_from_strategy = strategy.get('_copy_style_request', '')
    copy_style_per_slide = ""
    if copy_style_from_strategy:
        copy_style_per_slide = f"""
# ❗❗ コピーライティングの最優先ルール ❗❗

ユーザーからのライティング要望: 「{copy_style_from_strategy}」

この要望に従って、以下のテキストを**必ず書き換え**てください：
- タイトル: 「{title}」 → 要望に沿った表現に書き換え
- サブタイトル: 「{subtitle}」 → 要望に沿った表現に書き換え
- ポイント: 全ての箇条書きを要望に沿った表現に書き換え
- キーメッセージ: 要望に沿った表現に書き換え

※ 元のテキストをそのまま使わず、必ず要望のスタイルに変換してください。
※ 意味は保持しつつ、表現だけを変更してください。
"""
    text_style_instruction = copy_style_per_slide
    
    slide_type = determine_slide_type(slide, slide_number, total_slides)
    
    # Detect portrait mode
    is_portrait = video_height > video_width
    
    # Select layout for variety
    layout = select_layout_for_slide(
        job_id=job_id,
        slide_number=slide_number,
        total_slides=total_slides,
        content_type=slide_type,
        num_points=len(raw_points),
        is_illustration_mode=is_illustration_mode,
        is_portrait=is_portrait
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
    is_ai_illustration = False
    if image_info:
        photographer = image_info.get("photographer", "Unknown")
        is_ai_illustration = "Gemini 3" in photographer
        
        image_section = IMAGE_SECTION_TEMPLATE.format(
            image_url=image_info.get("url", ""),
            photographer=photographer
        )
    else:
        image_section = ""
    
    # Extract personality for personalized copy/design
    personality = strategy.get("personality_analysis", {})
    personality_section = ""
    if personality:
        tone = personality.get("tone", "")
        expressions = personality.get("characteristic_expressions", [])
        style_desc = personality.get("speaking_style", "")
        values = personality.get("values", "")
        design_hint = personality.get("design_hint", "")

        
        personality_section = f"""
話者の口調: {tone}
特徴的な表現: {', '.join(expressions) if expressions else '(分析中)'}
話し方の特徴: {style_desc}
大切にしていること: {values}
デザインの方向性: {design_hint}
"""
    else:
        personality_section = "(パーソナリティ分析は次回の生成から適用されます)"
    
    # Simple mode instruction for minimal design
    simple_mode_instruction = ""
    if text_density == "simple":
        simple_mode_instruction = """
# ⚠️ シンプルモード（最重要 - 必ず従う）

このスライドは**シンプルモード**です。文字量を極限まで減らしてください。

## 絶対ルール
1. **タイトルのみ大きく表示**（画面の50%以上を占める大きさ）
2. **サブテキストは1行のみ**（15文字以内）
3. **箇条書き禁止**
4. **長い文章禁止**
5. **アイコンやカードで視覚表現**（テキストの代わりに図形・アイコンを使う）

## デザイン例
参考: 
- 大きなタイトル
- 小さな1行の説明
- 2-3個のカードやアイコンで視覚的に表現
- 余白を大きく取る（画面の60%以上が余白）

## 文字量の目安
- タイトル: 10文字以内
- サブテキスト: 15文字以内
- 合計: 30文字以内（これ以上は多すぎ）

文字が多いと失格です。ビジュアルで伝えてください。
"""
    
    # Illustration mode instruction (when generating illustration-focused slides)
    illustration_mode_instruction = ""
    if is_illustration_mode or is_ai_illustration:
        illustration_mode_instruction = """
# 🎨 イラスト重視モード（※最優先ルール）

AI生成されたイラストがこのスライドの主役です。以下の絶対ルールに従ってください：

## ⚠️ テキスト表示の絶対禁止事項（厳守）
1. **長文の段落（Paragraph）は禁止**：3行以上の長い文章は絶対に表示しないでください。
2. **スクリプト・文字起こしの表示禁止**：話し言葉や説明文、ナレーションテキストは一切表示しないでください。
3. **要素は最小限に**：表示してよいのは「タイトル」「短いサブタイトル（1行）」「短い箇条書き（最大3点）」のみです。

## 必須: イラスト画像の配置
レイアウトに従って、必ず以下のような `<img class="illustration">` タグを含めてください：

```html
<img class="illustration" src="ILLUSTRATION_PLACEHOLDER" alt="AI Illustration" style="..." />
```

**重要**: `src="ILLUSTRATION_PLACEHOLDER"` はそのまま記述してください。後で実際の画像が注入されます。

## レイアウト別配置例

### Left / Right Illustration:
- 左または右55%にイラスト画像
- 反対側にテキスト（タイトル大きく、ポイントは最大2個）

### Center Hero:
- 中央にイラスト大きく
- タイトルは上部に大きく（96px以上）

### Full Bleed:
- イラストを全画面背景（width: 100%; height: 100vh; object-fit: cover;）
- テキストはオーバーレイで最小限

## テキストルール
1. **タイトルは大きく**（72-96px）、体言止めかキャッチコピー調
2. **サブタイトルは簡潔**（15文字以内）
3. **ポイントは最大2個**（各8文字以内）
4. **話し言葉禁止**（「〜なんです」「〜だと思う」等）

## 可読性確保
- テキスト背景: `backdrop-filter: blur(10px)` または `rgba(0,0,0,0.6)`
- text-shadow: `0 4px 12px rgba(0,0,0,0.8)`
"""
    
    # User images instruction - available to ALL slides when user uploads images
    user_images_instruction = ""
    user_images_list = strategy.get("_user_images_data", [])  # Use internal key (not serialized to AI)
    user_images_count = strategy.get("user_images_count", 0)
    
    if user_images_list:
        # Smart distribution: N images → assigned to N different slides
        # For 1 image: skip title slide (slide 1), place on slide 2
        # For N images: slides 1..N each get one image
        
        if len(user_images_list) == 1:
            # Single image: place on slide 2 (skip title)
            target_slide = 2
        else:
            # Multiple images: each slide gets one (slide N gets image N)
            target_slide = slide_number
        
        # Only add image instruction if this slide should have an image
        if slide_number == target_slide or (len(user_images_list) > 1 and slide_number <= len(user_images_list)):
            user_images_instruction = f"""
# 🖼️ ユーザー画像の配置（このスライド用）

このスライドにユーザーがアップロードした画像を**必ず**配置してください。

以下のHTMLを**そのまま**（srcを変更せず）挿入：

```html
<div style="position: absolute; right: 5%; top: 50%; transform: translateY(-50%); width: 40%; max-height: 80%; z-index: 50; border-radius: 12px; overflow: hidden; box-shadow: 0 10px 30px rgba(0,0,0,0.3);">
    <img src="USER_IMAGE_PLACEHOLDER" alt="User Image" style="width: 100%; height: auto; object-fit: contain; display: block;">
</div>
```

**重要**: 
- src="USER_IMAGE_PLACEHOLDER" を変更しない
- 左側テキストを max-width: 55% 等で調整
"""
        else:
            # This slide doesn't get a user image
            user_images_instruction = ""
    
    # Portrait mode instruction
    portrait_instruction = ""
    if is_portrait:
        portrait_instruction = """
# 📱 縦長モード（9:16）— 最重要ルール

このスライドは**縦長画面（9:16、Shorts/Reels向け）**です。以下のルールを必ず守ってください。

## ❗ 絶対禁止（横長レイアウトを使わない）
❌ `display: flex` + `flex-direction: row` — 横並び禁止
❌ カードやポイントを2列以上に並べる
❌ 左右分割レイアウト（left_heavy, right_heavy, split_vertical等）
❌ width: 60% / width: 40% の横分割

## ✅ 必須ルール
✅ すべての要素は `flex-direction: column` で**縦に積む**
✅ bodyはpadding: 40px 40px（左右80pxは広すぎる）
✅ タイトル: font-size: clamp(2rem, 5vh, 3.5rem)
✅ カード/ポイント: width: 100% または width: 90%（画面幅いっぱい）
✅ コンテンツは縦方向に流れるように配置
✅ フォントは横長より小さめ（画面が狭いため）
"""
    
    # Generate prompt
    base_font_instruction = style.get("font_instruction", "")
    
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
        layout_instruction=layout_instruction + simple_mode_instruction + illustration_mode_instruction + user_images_instruction + portrait_instruction,
        image_section=image_section,
        personality_section=personality_section,
        width=video_width,
        height=video_height,
        font_import=style.get("font_import", "Noto Sans JP:wght@400;700;900"),
        font_instruction=base_font_instruction + text_style_instruction
    )
    
    try:
        # Gemini 3 Flash for high-quality slide generation
        html = await safe_gemini_generate(
            "gemini-3-flash-preview",
            prompt,
            key,
            config=genai.GenerationConfig(
                temperature=0.8,
                max_output_tokens=4096
            )
        )
        
        # Extract HTML from markdown code block if present
        if "```html" in html:
            html = html.split("```html")[1].split("```")[0].strip()
        elif "```" in html:
            html = html.split("```")[1].split("```")[0].strip()
        
        if not html.startswith("<!DOCTYPE") and not html.startswith("<html"):
            print(f"[Design Architect] Invalid HTML for slide {slide_number}, using fallback")
            return generate_fallback_html(slide, slide_number, total_slides, strategy)
        
        # Replace user image placeholder with actual base64 if present (for ANY slide that has placeholder)
        user_images_list = strategy.get("_user_images_data", [])
        if user_images_list and "USER_IMAGE_PLACEHOLDER" in html:
            # Smart index: for single image targeting slide 2, always use image 0
            # For multiple images, each slide gets corresponding image
            if len(user_images_list) == 1:
                img_index = 0  # Single image always uses index 0
            else:
                img_index = (slide_number - 1) % len(user_images_list)
            img = user_images_list[img_index]
            html = html.replace("USER_IMAGE_PLACEHOLDER", img["base64"])
            print(f"[Design Architect] Injected user image {img_index + 1}/{len(user_images_list)} into slide {slide_number}")
        elif user_images_list and "user_image_placeholder" in html:
            # Try lowercase fallback
            if len(user_images_list) == 1:
                img_index = 0
            else:
                img_index = (slide_number - 1) % len(user_images_list)
            img = user_images_list[img_index]
            html = html.replace("user_image_placeholder", img["base64"])
            print(f"[Design Architect] Injected user image {img_index + 1}/{len(user_images_list)} into slide {slide_number} (lowercase)")
        
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
    font_style: Optional[str] = None,   # User-selected font style: gothic, mincho, pop, handwritten
    user_images: Optional[List[str]] = None,  # User-uploaded image paths
    design_preference: Optional[str] = None,  # User design requirements (e.g., "white background")
    copy_style_request: Optional[str] = None,  # User copy/writing style request
    text_density: str = "standard",  # "simple" (title+headline) or "standard" (full)
    progress_callback: Optional[callable] = None,  # Progress callback(current, total, message)
    start_slide: int = 1,  # Batch: start from this slide (1-indexed)
    end_slide: Optional[int] = None,  # Batch: end at this slide (inclusive), None = all
    reference_image_path: Optional[str] = None,  # Reference image for illustration style
    illustration_request: Optional[str] = None,  # User's text request for illustrations
    add_illustrations: bool = False,  # Whether to add AI-generated illustrations to slides
    illustration_percentage: int = 50,  # Percentage of slides to add illustrations (10-100)
    video_width: int = VIDEO_WIDTH,  # Dynamic video width (for portrait support)
    video_height: int = VIDEO_HEIGHT,  # Dynamic video height (for portrait support)
    facecam_position: Optional[str] = None,  # PiP position for text avoidance
    facecam_size: Optional[int] = None  # PiP size
) -> List[str]:
    """
    Generate all slides using the AI Design Architect approach
    """
    print(f"[DEBUG] generate_all_custom_slides called for job {job_id}, dimensions={video_width}x{video_height}")
    import os
    from playwright.async_api import async_playwright
    from config import OUTPUT_DIR

    # Local shorthand for viewport dimensions
    vw = video_width
    vh = video_height
    
    slides_dir = os.path.join(OUTPUT_DIR, f"{job_id}_slides")
    os.makedirs(slides_dir, exist_ok=True)
    
    total_slides = len(slides)
    
    # Batch processing: determine actual end slide
    if end_slide is None:
        end_slide = total_slides
    end_slide = min(end_slide, total_slides)
    
    # Step 1 & 2: Generate or retrieve design strategy
    if outline is None:
        outline = {"slides": slides}
    
    # Check if we have cached strategy (for batch continuation)
    cached_data = get_slide_data(job_id)
    
    if start_slide == 1 or cached_data is None:
        # First batch: generate new strategy
        print("[Design Architect] Analyzing content and defining design strategy...")
        if design_preference:
            print(f"[Design Architect] User preference: {design_preference}")
        if progress_callback:
            progress_callback(0, end_slide - start_slide + 2, "デザイン戦略を生成中...")
        
        strategy = await generate_design_strategy(outline, gemini_key, color_theme, design_preference, copy_style_request, facecam_position, facecam_size)
        
        # Store copy_style_request in strategy for per-slide prompt injection
        if copy_style_request:
            strategy['_copy_style_request'] = copy_style_request
        
        # Apply user-selected font style to strategy
        if font_style and font_style in FONT_STYLES:
            font_config = FONT_STYLES[font_style]
            strategy.setdefault("design_style", {})
            strategy["design_style"]["font_import"] = font_config["google_font"]
            strategy["design_style"]["font_instruction"] = font_config["css_instruction"]
            print(f"[Design Architect] Applying font style: {font_config['name']}")
        
        # Save strategy and slide data for later batches
        save_slide_data(job_id, slides, strategy)
    else:
        # Subsequent batches: use cached strategy
        print(f"[Design Architect] Using cached strategy for batch {start_slide}-{end_slide}")
        strategy = cached_data.get("strategy", {})
    
    # Convert user images to base64 for embedding in slides
    # Store separately from strategy to avoid token overflow in prompts
    user_images_base64 = []
    user_images_file = os.path.join(slides_dir, "user_images.pkl")
    
    if user_images and start_slide == 1:
        import base64
        import pickle
        for img_path in user_images:
            try:
                with open(img_path, "rb") as f:
                    img_data = f.read()
                ext = os.path.splitext(img_path)[1].lower().replace(".", "")
                if ext == "jpg":
                    ext = "jpeg"
                b64 = base64.b64encode(img_data).decode("utf-8")
                user_images_base64.append({
                    "base64": f"data:image/{ext};base64,{b64}",
                    "filename": os.path.basename(img_path)
                })
            except Exception as e:
                print(f"[User Images] Failed to load {img_path}: {e}")
        
        if user_images_base64:
            # Save to separate file (not in strategy to avoid token overflow)
            with open(user_images_file, "wb") as f:
                pickle.dump(user_images_base64, f)
            # Only store count in strategy (not the data)
            strategy["user_images_count"] = len(user_images_base64)
            print(f"[Design Architect] Saved {len(user_images_base64)} user images to {user_images_file}")
    elif os.path.exists(user_images_file):
        # Load cached user images for subsequent batches/regeneration
        import pickle
        try:
            with open(user_images_file, "rb") as f:
                user_images_base64 = pickle.load(f)
            print(f"[Design Architect] Loaded {len(user_images_base64)} cached user images")
        except Exception as e:
            print(f"[User Images] Failed to load cached images: {e}")
    
    # Make user_images available for generate_slide_html via strategy reference
    if user_images_base64:
        strategy["_user_images_data"] = user_images_base64  # Underscore prefix = internal, not sent to AI
    
    if progress_callback:
        progress_callback(1, end_slide - start_slide + 2, f"スライド生成中 ({start_slide-1}/{total_slides})")
    
    # Step 3: Generate slides in the specified range
    image_paths = []
    html_contents = []
    
    # For batch mode, include existing paths AND HTML contents for slides before start_slide
    if start_slide > 1 and cached_data and "html_contents" in cached_data:
        html_contents = cached_data["html_contents"][:start_slide - 1]
    
    for i in range(1, start_slide):
        existing_path = os.path.join(slides_dir, f"slide_{i:03d}.png")
        if os.path.exists(existing_path):
            image_paths.append(existing_path)
    
    import time as time_module
    
    # Register in queue for visibility
    queue_waiters[job_id] = time_module.time()
    print(f"[Queue] Job {job_id} entered queue (waiters: {len(queue_waiters)}, active: {len(queue_active)})")
    
    print(f"[DEBUG] Waiting for BROWSER_SEMAPHORE (current value: {BROWSER_SEMAPHORE._value})")
    async with BROWSER_SEMAPHORE, async_playwright() as p:
        # Move from waiting to active
        if job_id in queue_waiters:
            del queue_waiters[job_id]
        queue_active[job_id] = time_module.time()
        print(f"[Queue] Job {job_id} now processing (waiters: {len(queue_waiters)}, active: {len(queue_active)})")
        
        print(f"[DEBUG] BROWSER_SEMAPHORE acquired, launching browser...")
        browser = await p.chromium.launch(args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu'])
        print(f"[DEBUG] Browser launched successfully")
        
        for i, slide in enumerate(slides):
            slide_number = i + 1
            
            # Batch mode: skip slides outside the specified range
            if slide_number < start_slide or slide_number > end_slide:
                continue
            
            slide_type = determine_slide_type(slide, slide_number, total_slides)
            
            # Step 3a: Image generation
            image_info = None
            
            # Check for illustration settings from new parameters
            is_illustration_mode_enabled = add_illustrations
            
            # Apply percentage-based strategy: not all slides need illustrations
            use_illustration_for_this_slide = False
            selected_template = None
            if is_illustration_mode_enabled:
                # Use percentage-based selection
                use_illustration_for_this_slide = should_use_illustration_by_percentage(
                    slide_type, slide_number, total_slides, illustration_percentage
                )
                if use_illustration_for_this_slide:
                    selected_template = select_illustration_template(slide_number, total_slides, slide_type)
                    print(f"[Generator] Slide {slide_number}: Using illustration (template: {selected_template})")
                else:
                    print(f"[Generator] Slide {slide_number}: Standard text-based slide (MIX strategy)")
            
            # Generate image only if this slide should have illustration
            if use_illustration_for_this_slide:
                print(f"[Generator] Illustration mode detected for slide {slide_number}")
                visual_suggestion = slide.get("visual_suggestion", {})
                # Use image_prompt if available, otherwise description, otherwise title
                base_prompt = visual_suggestion.get("image_prompt") or visual_suggestion.get("description", "")
                
                # Fallback: use slide title if no visual_suggestion
                if not base_prompt:
                    slide_copy = slide.get("slide_copy", {})
                    title = slide_copy.get("headline") or slide.get("title", "")
                    if title:
                        base_prompt = f"illustration for: {title}"
                        print(f"[Generator] Using title as prompt fallback: {title}")
                
                if base_prompt:
                    # Build illustration prompt focused on concept visualization (diagram-style)
                    # The core purpose is to help understanding and visualization of concepts
                    
                    # Base instruction: focus on conceptual visualization, not artistic beauty
                    # Determine if this illustration should include text labels (based on layout)
                    include_text_labels = should_include_text_in_illustration(slide_number, total_slides, selected_template)
                    
                    text_instruction = "- NO text or labels in the image (text will be added separately on the slide)"
                    if include_text_labels:
                        text_instruction = "- Include simple Japanese labels or short text annotations in the diagram to explain key parts"
                        print(f"[Generator] Including text labels in illustration for slide {slide_number}")
                    
                    diagram_instruction = f"""Create an explanatory diagram illustration that helps visualize and understand the concept.
Focus on:
- Visualizing relationships, processes, or concepts clearly
- Using arrows, icons, and simple visual elements to explain ideas
- Making the illustration educational and easy to understand
{text_instruction}

Concept to illustrate: """
                    
                    # Include user's illustration request if provided (this controls style)
                    user_style_part = ""
                    if illustration_request:
                        user_style_part = f"\n\nStyle instruction from user: {illustration_request}"
                        print(f"[Generator] Including user style request: {illustration_request[:50]}...")
                    
                    # Add visual theme from design strategy if available
                    theme_part = ""
                    if strategy.get("design_style"):
                        visual_theme = strategy["design_style"].get("visual_theme", "")
                        if visual_theme:
                            theme_part = f"\n\nVisual theme: {visual_theme}"
                    
                    full_prompt = f"{diagram_instruction}{base_prompt}{user_style_part}{theme_part}"
                    
                    # Determine image aspect based on layout
                    layout_config = LAYOUT_TYPES.get(selected_template, {})
                    image_aspect = layout_config.get("image_aspect", "landscape")
                    print(f"[Generator] Generating illustration for slide {slide_number} (aspect: {image_aspect})...")
                    print(f"[Generator] Prompt: {full_prompt[:100]}...")
                    if progress_callback:
                        progress_callback(i, end_slide - start_slide + 2, f"イラスト生成中 ({slide_number}/{total_slides})...")
                    
                    img_data = await generate_slide_image(full_prompt, gemini_key, reference_image_path, image_aspect)
                    
                    if img_data:
                        img_filename = f"slide_illustration_{slide_number:03d}.png"
                        img_path = os.path.join(slides_dir, img_filename)
                        try:
                            with open(img_path, "wb") as f:
                                f.write(img_data)
                            
                            # Create base64 data URL for Playwright rendering
                            import base64
                            img_base64 = base64.b64encode(img_data).decode('utf-8')
                            data_url = f"data:image/png;base64,{img_base64}"
                            
                            # Set image info for HTML generation
                            image_info = {
                                "url": f"/outputs/{job_id}_slides/{img_filename}",
                                "absolute_path": img_path,
                                "data_url": data_url,  # Base64 for Playwright
                                "photographer": "AI Generated (Gemini 3)"
                            }
                            print(f"[Generator] Saved illustration to {img_path}")
                        except Exception as e:
                            print(f"[Generator] Failed to save image: {e}")
                    else:
                        print(f"[Generator] Image generation returned no data for slide {slide_number}")
                else:
                    print(f"[Generator] No prompt available for slide {slide_number}, skipping image generation")
            
            # Step 3b: Generate HTML
            # NEW: イラストモードでも標準と同じgenerate_slide_htmlを使用
            # AI画像は生成後に注入する
            
            if use_illustration_for_this_slide:
                print(f"[Generator] Using AI HTML generation with illustration layout for slide {slide_number}")
                
                # NEW: イラストモード専用 - 話し言葉を修正してスライド用コピーに変換
                polished_copy = await polish_copy_for_illustration(
                    slide=slide,
                    slide_number=slide_number,
                    total_slides=total_slides,
                    strategy=strategy,
                    gemini_key=gemini_key
                )
                
                # 整形されたコピーをslideに反映（元のslideを上書きしないようにコピー）
                polished_slide = slide.copy()
                if "slide_copy" not in polished_slide:
                    polished_slide["slide_copy"] = {}
                polished_slide["slide_copy"] = polished_slide["slide_copy"].copy()
                polished_slide["slide_copy"]["headline"] = polished_copy["title"]
                polished_slide["slide_copy"]["subheadline"] = polished_copy["subtitle"]
                polished_slide["slide_copy"]["bullet_points"] = polished_copy["points"]
                
                print(f"[Generator] Polished copy for illustration: '{polished_copy['title']}'")
                
                # Generate HTML using standard process with polished copy
                # But with illustration-specific layout (image_info passed for injection later)
                html = await generate_slide_html(
                    slide=polished_slide,  # Use polished copy
                    slide_number=slide_number,
                    total_slides=total_slides,
                    strategy=strategy,
                    job_id=job_id,
                    gemini_key=gemini_key,
                    image_info=image_info,
                    text_density=text_density,
                    is_illustration_mode=True,
                    video_width=vw,
                    video_height=vh
                )
                
                # Inject AI illustration into the generated HTML if image exists
                if image_info and image_info.get("data_url"):
                    img_data_url = image_info.get("data_url")
                    
                    # Check if illustration placeholder exists and replace it
                    if 'class="illustration"' in html:
                        import re
                        # Replace src in illustration img tag with actual data URL
                        html = re.sub(
                            r'(<img[^>]*class="illustration"[^>]*src=")[^"]*(")',
                            rf'\g<1>{img_data_url}\g<2>',
                            html
                        )
                        print(f"[Generator] Injected illustration data URL into slide {slide_number}")
                    else:
                        # Fallback: inject illustration as background
                        print(f"[Generator] No illustration placeholder found, injecting as background for slide {slide_number}")
                        illustration_html = f'''
<div style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; z-index: 1; overflow: hidden;">
    <img src="{img_data_url}" class="illustration" alt="AI Illustration" style="width: 100%; height: 100%; object-fit: cover; opacity: 0.85;">
    <div style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; background: linear-gradient(135deg, rgba(0,0,0,0.6) 0%, rgba(0,0,0,0.3) 50%, rgba(0,0,0,0.5) 100%);"></div>
</div>'''
                        if '<body>' in html:
                            html = html.replace('<body>', '<body>\n' + illustration_html, 1)
                        elif '<body ' in html:
                            # Find the end of <body tag and insert after
                            import re
                            html = re.sub(r'(<body[^>]*>)', r'\1\n' + illustration_html, html, count=1)
            else:
                # Standard mode: use AI-generated HTML
                html = await generate_slide_html(
                    slide=slide,
                    slide_number=slide_number,
                    total_slides=total_slides,
                    strategy=strategy,
                    job_id=job_id,
                    gemini_key=gemini_key,
                    image_info=image_info,
                    text_density=text_density,
                    video_width=vw,
                    video_height=vh
                )
                
                # Step 3b-2: Inject AI illustration if not present in HTML (fallback)
                if is_illustration_mode_enabled and image_info:
                    img_url = image_info.get("url", "")
                    if img_url and img_url not in html:
                        print(f"[Generator] Injecting illustration into slide {slide_number}...")
                        illustration_html = f'''
<div style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; z-index: 1; overflow: hidden;">
    <img src="{img_url}" alt="AI Illustration" style="width: 100%; height: 100%; object-fit: cover; opacity: 0.85;">
    <div style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; background: linear-gradient(135deg, rgba(0,0,0,0.7) 0%, rgba(0,0,0,0.3) 50%, rgba(0,0,0,0.5) 100%);"></div>
</div>'''
                        if '<body' in html:
                            html = html.replace('<body>', '<body>' + illustration_html, 1)
                        elif '<body ' in html:
                            import re
                            html = re.sub(r'(<body[^>]*>)', r'\1' + illustration_html.replace('\\', '\\\\'), html, count=1)
                        else:
                            html = illustration_html + html
            
            # Step 3c: Self-review (skip for illustration mode as we use fixed template with base64 image)
            # Only run for standard slides to ensure no transcript/subtitle text remains
            if not (use_illustration_for_this_slide and image_info):
                print(f"[Design Architect] Self-reviewing slide {slide_number}...")
                html = await self_review_slide(
                    html=html,
                    strategy=strategy,
                    gemini_key=gemini_key
                )
                
                # Step 3d: Post-processing - forcibly remove any remaining caption text
                print(f"[Design Architect] Post-processing slide {slide_number} (removing captions)...")
                html = remove_caption_text(html)
            else:
                print(f"[Design Architect] Skipping self-review for illustration slide {slide_number}")
            
            html_contents.append(html)
            
            # Render to image with browser restart on crash
            output_path = os.path.join(slides_dir, f"slide_{slide_number:03d}.png")
            
            render_success = False
            for render_attempt in range(3):
                try:
                    # Try to create new page (may fail if browser crashed)
                    try:
                        page = await browser.new_page(viewport={"width": vw, "height": vh})
                    except Exception as page_error:
                        print(f"[Browser] new_page failed, restarting browser... ({str(page_error)[:50]})")
                        try:
                            await browser.close()
                        except:
                            pass
                        await asyncio.sleep(1)
                        browser = await p.chromium.launch(args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu'])
                        page = await browser.new_page(viewport={"width": vw, "height": vh})
                    
                    html = fix_body_dimensions(html, vw, vh)
                    await page.set_content(html)
                    await page.wait_for_timeout(800)
                    
                    # Screenshot
                    await page.screenshot(path=output_path, type="png")
                    await page.close()
                    render_success = True
                    break
                    
                except Exception as render_error:
                    print(f"[Render] Attempt {render_attempt + 1} failed: {str(render_error)[:80]}")
                    try:
                        await page.close()
                    except:
                        pass
                    if render_attempt < 2:
                        # Restart browser
                        try:
                            await browser.close()
                        except:
                            pass
                        await asyncio.sleep(1)
                        browser = await p.chromium.launch(args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu'])
                        print(f"[Browser] Restarted for retry {render_attempt + 2}")
            
            if not render_success:
                print(f"[Design Architect] ⚠️ Slide {slide_number} rendering failed, skipping...")
                continue
            
            # Validation is now integrated into self-review for speed
            image_paths.append(output_path)
            print(f"[Design Architect] Completed slide {slide_number}/{total_slides}")
            
            # Update progress (for batch mode)
            slides_in_batch = slide_number - start_slide + 1
            if progress_callback:
                progress_callback(slides_in_batch + 1, end_slide - start_slide + 2, f"スライド生成中 ({slide_number}/{total_slides})")
            
            # Pacing: Add small delay between slides to prevent aggregate rate limits (especially for Free Tier)
            if slide_number < total_slides:
                await asyncio.sleep(2.5) 
        
        await browser.close()
    
    # Clean up queue tracking
    if job_id in queue_active:
        del queue_active[job_id]
    if job_id in queue_waiters:
        del queue_waiters[job_id]
    print(f"[Queue] Job {job_id} completed (waiters: {len(queue_waiters)}, active: {len(queue_active)})")
    
    # Save HTML contents for feedback editing
    save_html_contents(job_id, html_contents)
    
    print(f"[Design Architect] Generated {len(image_paths)} slides with unified design strategy")
    return image_paths


# =============================================================================
# Slide Validation - Auto-detect and fix layout issues
# =============================================================================

VALIDATION_PROMPT = """あなたはスライドの**厳格な**品質検証担当者です。
このスライド画像を**非常に厳しい目で**分析し、以下の問題がないかチェックしてください。

⚠️ **重要**: 少しでも問題があれば is_valid: false としてください。品質に妥協は許されません。

## チェック項目（厳格に判定）

### 1. 空白・コンテンツ不足 ❌
- スライドの**40%以上が空白**の場合 → 問題あり
- タイトルだけで本文がほとんどない → 問題あり
- アイコンや装飾だけで情報が薄い → 問題あり

### 2. レイアウト崩れ ❌
- テキストがスライドの外にはみ出している
- テキストや要素が重なって読めない
- 要素の配置がおかしい、中途半端な位置にある

### 3. 不均衡な2カラムレイアウト（最重要）❌
**以下のパターンは必ず問題としてマーク**:
- **左側が空白**で右側にテキストが集中 → 問題あり
- **右側が空白**で左側にテキストが集中 → 問題あり
- カラムの**片側だけにアイコン**があり反対側が空 → 問題あり
- **小さなボックスに1単語ずつ**並んでいて、隣が空白 → 問題あり
- **カラムのサイズが極端に違う**（50:50に近くない） → 問題あり

**具体例**:
- 左に「◯」「△」「□」のアイコン、右に空白 → ❌ 問題あり
- 左に短いタイトルだけ、右に大きな空白エリア → ❌ 問題あり

### 4. 読みにくさ ❌
- テキストが小さすぎて読めない
- 背景とテキストのコントラストが低すぎる
- フォントサイズがバラバラで統一感がない

## 判定基準

**is_valid: true** = 上記のどの問題もない、プロフェッショナルな仕上がり
**is_valid: false** = 上記の問題が1つでもある

## 回答形式（JSON）

問題がある場合（厳しく判定）:
```json
{
  "is_valid": false,
  "issues": ["左側が空白で右側にコンテンツが集中している", "カラムのバランスが悪い"],
  "fix_suggestion": "センター配置に変更するか、左側にも装飾的な要素を追加してバランスを取る"
}
```

問題がない場合:
```json
{"is_valid": true, "issues": [], "fix_suggestion": ""}
```
"""


async def validate_slide_screenshot(
    image_path: str,
    gemini_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Validate a slide screenshot using Gemini Vision
    Returns: {"is_valid": bool, "issues": list, "fix_suggestion": str}
    """
    import os
    
    key = gemini_key or GEMINI_API_KEY
    if not key:
        return {"is_valid": True, "issues": [], "fix_suggestion": ""}
    
    try:
        genai.configure(api_key=key)
        
        # Load image
        with open(image_path, "rb") as f:
            image_data = f.read()
        
        image_part = {
            "mime_type": "image/png",
            "data": base64.b64encode(image_data).decode("utf-8")
        }
        
        response_text = await safe_gemini_generate(
            "gemini-3-flash-preview",
            [VALIDATION_PROMPT, image_part],
            key,
            config=genai.GenerationConfig(
                response_mime_type="application/json",
                temperature=0.1
            )
        )
        
        result = json.loads(response_text)
        return result
        
    except Exception as e:
        print(f"[Validation] Error validating slide: {e}")
        return {"is_valid": True, "issues": [], "fix_suggestion": ""}


async def validate_and_regenerate_slide(
    slide_number: int,
    current_html: str,
    image_path: str,
    slide: Dict[str, Any],
    strategy: Dict[str, Any],
    job_id: str,
    browser,
    slides_dir: str,
    gemini_key: Optional[str] = None,
    max_retries: int = 2
) -> tuple:
    """
    Validate a slide and regenerate if needed.
    Returns: (final_html, final_image_path, was_regenerated)
    """
    from playwright.async_api import async_playwright
    
    html = current_html
    path = image_path
    
    for attempt in range(max_retries):
        # Validate the current screenshot
        validation = await validate_slide_screenshot(path, gemini_key)
        
        if validation.get("is_valid", True):
            if attempt > 0:
                print(f"  [Validation] ✅ Slide {slide_number} fixed after {attempt} retries")
            return html, path, attempt > 0
        
        issues = validation.get("issues", [])
        fix_suggestion = validation.get("fix_suggestion", "")
        print(f"  [Validation] ⚠️ Slide {slide_number} has issues: {issues}")
        
        # Regenerate with fix suggestion
        feedback = f"以下の問題を修正してください:\n"
        for issue in issues:
            feedback += f"- {issue}\n"
        if fix_suggestion:
            feedback += f"\n修正の方向性: {fix_suggestion}"
        
        try:
            # Use self_review with specific fix instructions
            html = await self_review_slide(
                html=html,
                strategy=strategy,
                gemini_key=gemini_key,
                additional_feedback=feedback
            )
            
            # Re-render
            page = await browser.new_page(viewport={"width": vw, "height": vh})
            html = fix_body_dimensions(html, vw, vh)
            await page.set_content(html)
            await page.wait_for_timeout(1000)
            await page.screenshot(path=path, type="png")
            await page.close()
            
            print(f"  [Validation] Regenerated slide {slide_number} (attempt {attempt + 1}/{max_retries})")
            
        except Exception as e:
            print(f"  [Validation] Failed to regenerate slide {slide_number}: {e}")
            break
    
    return html, path, True


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

def load_html_contents(job_id: str) -> List[str]:
    """Load saved HTML contents for a job"""
    data = _slide_data_cache.get(job_id)
    if data and "html_contents" in data:
        return data["html_contents"]
    return []

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

## 2. レイアウト（重要！）
**レイアウトを厳しくチェックし、問題があれば必ず修正してください。**

### 絶対NG（検出したら必ず修正）:
❌ 左側または右側が空白で反対側にコンテンツ集中
❌ カラム間のバランスが極端に悪い（片方30%、片方70%など）
❌ 不必要な余白が多い（コンテンツがスカスカ）
❌ 小さすぎるボックスやカード（画面の20%以下）
❌ テキストが読みにくい配置（文字が小さい、コントラスト不足）

### 修正すべきこと:
✅ 余白を減らしてコンテンツを大きく表示
✅ 2カラムを使う場合は均等に（50:50 または 60:40）
✅ フォントサイズを大きめに（タイトル: 40px以上、本文: 20px以上）
✅ パディングを適度に（過剰なpadding/marginを削減）
✅ 情報を画面いっぱいに効率的に配置

### 具体的なチェックポイント:
- max-width: 80%以上のコンテナを使用しているか？
- flexboxで均等配置されているか？
- 無駄なpadding（100px以上）がないか？
- 視聴者が遠くからでも読める文字サイズか？

## 3. ビジュアル

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
    gemini_key: Optional[str] = None,
    additional_feedback: Optional[str] = None  # Additional fix instructions from validation
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
    
    # Add validation feedback if provided
    if additional_feedback:
        prompt += f"""

## 🔧 追加の修正指示（検証からのフィードバック）

{additional_feedback}

上記の問題を優先的に修正してください。
"""
    
    try:
        # Gemini 3 Flash for self-review
        improved_html = await safe_gemini_generate(
            "gemini-3-flash-preview",
            prompt,
            key,
            config=genai.GenerationConfig(
                temperature=0.7,
                max_output_tokens=4096
            )
        )
        
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

# ⛔ 最重要: コンテンツの保持（絶対ルール - 違反禁止）

**以下のコンテンツは絶対に削除・変更しないでください。これに違反すると失敗になります。**

## 必ず保持する要素:
1. **タイトルテキスト**: h1, .title, .headline のテキストをそのまま保持
2. **サブタイトルテキスト**: h3, .subtitle のテキストをそのまま保持
3. **ポイント・箇条書き**: .point, li のテキストをすべて保持
4. **画像**: img タグの src 属性を変更禁止（特に data:image/... は絶対保持）
5. **イラスト**: class="illustration" の img タグを削除禁止、srcも保持

## 変更してよいもの（デザイン調整のみ）:
✅ 色・フォントサイズ・スタイリング
✅ 背景・装飾要素
✅ ユーザーが具体的に依頼した変更のみ

## 絶対禁止（レイアウト保持）:
❌ テキストコンテンツの削除・省略・変更
❌ 画像srcを空にする、削除する、変更する
❌ 「シンプルに」を理由にコンテンツを減らす
❌ 元にないテキストを追加する
❌ **レイアウトの変更**（ユーザーが明示的に依頼しない限り）
❌ **画像の位置変更**（左→右、中央→背景など）
❌ **画像を背景に移動する**（元の配置を保持）

# タイトル色のルール（絶対順守）

⛔ **タイトルに暗い色を使用禁止！**
- ❌ 黒系（#000, #111, #222, #333）
- ❌ 茶色系（brown, #8B4513, chocolate）
- ❌ 暗いグレー系（#444, #555, dimgray）
- ✅ 白（#FFF, #FFFFFF）が最も安全
- ✅ 明るいグラデーション（オレンジ、ピンク、紫）

# 実行手順

1. **テキスト抽出**: 元HTMLからタイトル、サブタイトル、ポイント、画像srcをすべて抽出
2. **フィードバック理解**: ユーザーの要望を理解（デザイン変更のみ）
3. **HTML再構築**: 抽出したテキストと画像を**必ず含めて**新HTMLを生成
4. **検証**: タイトル・サブタイトル・ポイント・画像がすべて存在することを確認

# 出力仕様
- サイズ: {width}px × {height}px
- 形式: 完全なHTML（<!DOCTYPE html>から</html>まで）
- 説明不要、HTMLのみ出力
"""


async def regenerate_slide_with_feedback(
    job_id: str,
    slide_number: int,
    feedback: str,
    feedback_type: str = "general",
    gemini_key: Optional[str] = None,
    image_base64: Optional[str] = None,
    image_filename: Optional[str] = None,
    video_width: int = VIDEO_WIDTH,
    video_height: int = VIDEO_HEIGHT
) -> Dict[str, Any]:
    """
    Regenerate a single slide based on user feedback (supports image uploads)
    """
    import os
    import base64
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
    
    # Handle image upload - save to disk and prepare for embedding
    image_instruction = ""
    image_data_url = None  # Store for post-processing
    IMAGE_PLACEHOLDER = "USER_IMAGE_PLACEHOLDER_URL"
    
    # Extract existing illustration image from current HTML for preservation
    existing_illustration_dataurl = None
    ILLUSTRATION_PLACEHOLDER = "EXISTING_ILLUSTRATION_URL"
    import re
    
    # Match data URL in img src with class="illustration" - handle both attribute orders
    # Pattern 1: src comes before class
    dataurl_match = re.search(r'<img[^>]+src="(data:image/[^"]+)"[^>]*class="illustration"', current_html)
    # Pattern 2: class comes before src  
    if not dataurl_match:
        dataurl_match = re.search(r'<img[^>]+class="illustration"[^>]*src="(data:image/[^"]+)"', current_html)
    # Pattern 3: Look for any img with illustration class and data URL anywhere in the tag
    if not dataurl_match:
        # Find all img tags with illustration class, then extract data URL
        illustration_match = re.search(r'<img[^>]*class="illustration"[^>]*>', current_html)
        if illustration_match:
            img_tag = illustration_match.group(0)
            src_match = re.search(r'src="(data:image/[^"]+)"', img_tag)
            if src_match:
                existing_illustration_dataurl = src_match.group(1)
    
    if dataurl_match and not existing_illustration_dataurl:
        existing_illustration_dataurl = dataurl_match.group(1)
    
    if existing_illustration_dataurl:
        print(f"[Feedback] ✅ Preserving existing illustration image ({len(existing_illustration_dataurl)} chars)")
    
    if image_base64 and image_filename:
        try:
            # Decode and save image
            slides_dir = os.path.join(OUTPUT_DIR, f"{job_id}_slides")
            os.makedirs(slides_dir, exist_ok=True)
            
            # Generate unique filename
            import time
            ext = os.path.splitext(image_filename)[1] or ".png"
            saved_filename = f"user_image_{slide_number}_{int(time.time())}{ext}"
            saved_path = os.path.join(slides_dir, saved_filename)
            
            # Save image
            image_bytes = base64.b64decode(image_base64)
            with open(saved_path, "wb") as f:
                f.write(image_bytes)
            
            # Create data URL for later embedding (NOT in prompt)
            import mimetypes
            mime_type = mimetypes.guess_type(saved_path)[0] or "image/png"
            image_data_url = f"data:{mime_type};base64,{image_base64}"
            
            # Add image instruction with PLACEHOLDER (not actual data URL)
            image_instruction = f"""

## 🖼️ ユーザーがアップロードした画像
ユーザーが画像をアップロードしました。以下のようにスライドに追加してください：

1. スライドの適切な位置に画像を配置してください（中央やメインコンテンツの横など）
2. 画像サイズは適切に調整（max-width: 300px～500px程度）
3. 以下のプレースホルダーをimg要素のsrcに使用してください：
   <img src="{IMAGE_PLACEHOLDER}" style="..." />

例：
<img src="{IMAGE_PLACEHOLDER}" style="max-width: 400px; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.3);" />

"""
            print(f"[Feedback] User image saved: {saved_path}")
        except Exception as e:
            print(f"[Feedback] Failed to process image: {e}")
    
    # Process based on feedback type - Different prompts for different goals
    
    # 1. Image Only Mode
    if feedback_type == "image" or feedback_type == "regenerate_image":
        print(f"[Feedback] Mode: Image Only - Regenerating illustration for slide {slide_number}")
        # Call specific image regeneration function
        from services.ai_slide_generator import regenerate_slide_illustration
        return await regenerate_slide_illustration(
            job_id=job_id,
            slide_number=slide_number,
            feedback=feedback,
            gemini_key=gemini_key,
            video_width=video_width,
            video_height=video_height
        )
        
    # Configure Gemini for other modes
    genai.configure(api_key=key)
    prompt = ""
    
    genai.configure(api_key=key)

    # 2. Copy Only Mode - Use DOM Manipulation for 100% Safety
    if feedback_type == "copy" or feedback_type == "regenerate_copy":
        print(f"[Feedback] Mode: Copy Only - Changing text via DOM manipulation for slide {slide_number}")
        
        copy_prompt = f"""# Role
あなたはプロのコピーライターです。スライドのテキストを修正してください。

# ユーザーの要望
{feedback}

# 現在のHTML
```html
{current_html}
```

# 指示
ユーザーの要望に基づいて、タイトル、サブタイトル、箇条書きポイントを修正してください。
出力は以下のJSON形式のみでお願いします。Markdownブロックは不要です。

{{
  "title": "新しいタイトル（短く簡潔に）",
  "subtitle": "新しいサブタイトル（なければ空文字列）",
  "points": ["ポイント1", "ポイント2", "ポイント3"]
}}
"""
        try:
            # Generate JSON
            response_text = await safe_gemini_generate(
                "gemini-3-flash-preview",
                copy_prompt,
                key,
                config=genai.GenerationConfig(
                    response_mime_type="application/json"
                )
            )
            new_copy = json.loads(response_text)
            print(f"[Feedback] New copy generated: {new_copy}")
            
            # Apply to HTML using BeautifulSoup helper
            new_html = update_html_text_content(current_html, new_copy)
            
            # Common post-processing (screenshot, etc) handled below? 
            # No, structural limitation of this function. Will handle screenshot here and return.
            
            update_html_content(job_id, slide_number, new_html)
            
            # Capture screenshot
            async with async_playwright() as p:
                browser = await p.chromium.launch()
                page = await browser.new_page(viewport={"width": video_width, "height": video_height})
                new_html = fix_body_dimensions(new_html, video_width, video_height)
                await page.set_content(new_html)
                # Wait for potential images
                await page.wait_for_timeout(1000)
                
                slides_dir = os.path.join(OUTPUT_DIR, f"{job_id}_slides")
                new_image_path = os.path.join(slides_dir, f"slide_{slide_number:03d}.png")
                await page.screenshot(path=new_image_path)
                await browser.close()
                
            return {
                "success": True,
                "preview_url": f"/outputs/{job_id}_slides/slide_{slide_number:03d}.png"
            }
            
        except Exception as e:
            print(f"[Feedback] Copy update failed: {e}")
            return {"success": False, "error": str(e)}

    # Configure prompt for other modes (Layout & General)
    prompt = ""
    
    # === CRITICAL: Strip base64 data URLs from HTML to prevent token limit errors ===
    # Base64 images can be 100k+ characters, causing prompt to exceed Gemini's 1M token limit
    stored_data_urls = {}
    html_for_prompt = current_html
    
    # Find and replace all base64 data URLs with placeholders
    data_url_pattern = r'(src=["\'])(data:image/[^"\']+)(["\'])'
    data_url_matches = list(re.finditer(data_url_pattern, current_html))
    
    for i, match in enumerate(data_url_matches):
        placeholder = f"__BASE64_IMAGE_{i}__"
        data_url = match.group(2)
        stored_data_urls[placeholder] = data_url
        html_for_prompt = html_for_prompt.replace(data_url, placeholder, 1)
    
    if stored_data_urls:
        print(f"[Feedback] Stripped {len(stored_data_urls)} base64 images from prompt (saved for restoration)")
        # Log size reduction
        original_size = len(current_html)
        reduced_size = len(html_for_prompt)
        print(f"[Feedback] HTML size: {original_size:,} → {reduced_size:,} chars (reduced by {original_size - reduced_size:,})")

        
    # 3. Layout Only Mode
    if feedback_type == "layout" or feedback_type == "fix_layout":
        print(f"[Feedback] Mode: Layout Only - Changing layout for slide {slide_number}")
        prompt = f"""# Role
あなたはWebデザイナーです。スライドのコンテンツ（テキストと画像）は**内容を維持したまま**、レイアウトのみを変更してください。

# ユーザーの要望（レイアウト変更）
{feedback}

# 現在のHTML
```html
{html_for_prompt}
```

# ⚠️ コンテンツ保持の絶対ルール（違反すると失敗）
このスライドのテキスト（タイトル、サブタイトル、ポイント）と画像は**絶対に削除・変更しないでください**。

1. **テキスト保持**:
   - タイトルを必ず含めること
   - サブタイトルを必ず含めること
   - 全ての箇条書きポイントを必ず含めること
   - **文字を空白にしたり、ダミーテキストに置き換えることは厳禁です。** current_htmlの中身をそのまま使ってください。

2. **画像保持**:
   - `src="{ILLUSTRATION_PLACEHOLDER}"` などのimgタグは必ず維持すること。
   - `class="illustration"` も維持すること。

3. **レイアウト変更**:
   - CSSグリッド、Flexbox、配置、配色を変更して要望に応えてください。
   - テキストの可読性を確保すること（画像の上に文字を置くなら背景色やシャドウをつける）。

# 出力
修正後の完全なHTMLのみを出力してください。
"""

    # 4. General Mode (Layout & Copy)
    else:
        print(f"[Feedback] Mode: General (Layout & Copy) - Regenerating slide {slide_number}")
        
        # Detect explicit copy change requests like "AをBに変更して" or "「X」を「Y」にして"
        copy_change_detected = False
        copy_change_instruction = ""
        
        import re
        # Pattern 1: 「A」を「B」に変更/して
        pattern1 = re.search(r'「([^」]+)」を「([^」]+)」に(変更|して)', feedback)
        # Pattern 2: "A"を"B"に
        pattern2 = re.search(r'"([^"]+)"を"([^"]+)"に', feedback)
        # Pattern 3: AをBに変更して (without quotes)
        pattern3 = re.search(r'(.+?)を(.+?)に(変更|して|直して|修正)', feedback)
        
        if pattern1 or pattern2 or pattern3:
            copy_change_detected = True
            match = pattern1 or pattern2 or pattern3
            old_text = match.group(1)
            new_text = match.group(2)
            copy_change_instruction = f"""

# ⚠️ 最優先: テキスト変更の指示

ユーザーが以下の具体的なテキスト変更を要求しています。**必ずこの変更を適用してください**:

変更前: 「{old_text}」
変更後: 「{new_text}」

この変更は「コンテンツ保持ルール」より優先されます。ユーザーが明示的に変更を指示した場合は、その通りに変更してください。
"""
            print(f"[Feedback] ✅ Copy change detected: 「{old_text}」→「{new_text}」")
        
        prompt = FEEDBACK_REGENERATION_PROMPT.format(
            current_html=html_for_prompt,
            concept_name=style.get("concept_name", ""),
            primary=colors.get("primary", "#F59E0B"),
            secondary=colors.get("secondary", "#8B5CF6"),
            accent=colors.get("accent", "#06B6D4"),
            feedback=feedback + image_instruction + copy_change_instruction,
            feedback_type="レイアウトとコピーの修正（画像は保持）",
            width=video_width,
            height=video_height
        )

    
    try:
        # Gemini 2.0 Flash for creative prompts
        # Generate response
        response_text = await safe_gemini_generate(
            "gemini-3-flash-preview", # Assuming model_name should be this
            prompt, # Assuming full_prompt should be prompt
            key,
            config=genai.GenerationConfig(temperature=0.7)
        )
        
        new_html = response_text.strip()
        
        # Extract HTML from markdown code block if present
        if "```html" in new_html:
            new_html = new_html.split("```html")[1].split("```")[0].strip()
        elif "```" in new_html:
            new_html = new_html.split("```")[1].split("```")[0].strip()
        
        # === CRITICAL: Restore base64 data URLs that were stripped before sending to AI ===
        if stored_data_urls:
            for placeholder, data_url in stored_data_urls.items():
                if placeholder in new_html:
                    new_html = new_html.replace(placeholder, data_url)
            print(f"[Feedback] Restored {len(stored_data_urls)} base64 images in AI response")
        
        # Replace image placeholder with actual data URL
        if image_data_url and IMAGE_PLACEHOLDER in new_html:
            new_html = new_html.replace(IMAGE_PLACEHOLDER, image_data_url)
            print(f"[Feedback] Replaced image placeholder with data URL ({len(image_data_url)} chars)")
        
        # Re-inject existing illustration image if it was removed during regeneration
        if existing_illustration_dataurl:
            # Check if user explicitly requested to remove the image
            remove_keywords = ["画像を消", "画像を削除", "イラストを消", "イラストを削除", "画像なし", "イラストなし"]
            should_preserve = not any(kw in feedback.lower() for kw in remove_keywords)
            
            if should_preserve:
                # Try to find an existing img tag with illustration class
                illustration_match = re.search(r'<img[^>]*class="illustration"[^>]*>', new_html)
                
                if illustration_match:
                    old_img = illustration_match.group(0)
                    # Check if src is already correct
                    if existing_illustration_dataurl not in old_img:
                        # Replace the src value
                        new_img = re.sub(r'src="[^"]*"', f'src="{existing_illustration_dataurl}"', old_img)
                        new_html = new_html.replace(old_img, new_img)
                        print(f"[Feedback] ✅ Re-injected existing illustration image into existing container")
                    else:
                        print(f"[Feedback] ✅ Illustration image already correct, no change needed")
                else:
                    # No img tag with illustration class found - ALWAYS force inject
                    # This handles cases where AI removed the img or used a different element
                    print(f"[Feedback] ⚠️ No img.illustration found, force-injecting as background...")
                    illustration_html = f'''
<div style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; z-index: 1; overflow: hidden;">
    <img src="{existing_illustration_dataurl}" class="illustration" alt="AI Illustration" style="width: 100%; height: 100%; object-fit: cover; opacity: 0.85;">
    <div style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; background: linear-gradient(135deg, rgba(0,0,0,0.6) 0%, rgba(0,0,0,0.3) 50%, rgba(0,0,0,0.5) 100%);"></div>
</div>'''
                    if '<body>' in new_html:
                        new_html = new_html.replace('<body>', '<body>\n' + illustration_html, 1)
                    elif '<body ' in new_html:
                        new_html = re.sub(r'(<body[^>]*>)', r'\1\n' + illustration_html, new_html, count=1)
                    print(f"[Feedback] ✅ Force-injected illustration as background")
            else:
                print(f"[Feedback] User requested image removal, not preserving illustration")
        
        if not new_html.startswith("<!DOCTYPE") and not new_html.startswith("<html"):
            raise ValueError("Invalid HTML generated")
        
        # Render new version
        slides_dir = os.path.join(OUTPUT_DIR, f"{job_id}_slides")
        
        async with BROWSER_SEMAPHORE, async_playwright() as p:
            browser = await p.chromium.launch(args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu'])
            page = await browser.new_page(viewport={"width": video_width, "height": video_height})
            new_html = fix_body_dimensions(new_html, video_width, video_height)
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

async def generate_slide_image(prompt: str, api_key: str, reference_image_path: Optional[str] = None, image_aspect: str = "landscape") -> Optional[bytes]:
    """Generates an image using Gemini 3 Pro Image Preview model.
    
    Args:
        prompt: The text prompt for image generation
        api_key: Gemini API key
        reference_image_path: Optional path to reference image for style guidance
        image_aspect: "portrait" for tall images (left/right layout), "landscape" for wide images
    """
    if not api_key:
        return None
        
    try:
        import os
        import base64
        
        genai.configure(api_key=api_key)
        model_name = "gemini-3-pro-image-preview"
        model = genai.GenerativeModel(model_name)
        
        # Build content with optional reference image
        content_parts = []
        
        if reference_image_path and os.path.exists(reference_image_path):
            print(f"[Imagen] Using reference image: {reference_image_path}")
            # Read and encode reference image
            with open(reference_image_path, "rb") as f:
                ref_image_data = f.read()
            
            # Determine mime type
            ext = os.path.splitext(reference_image_path)[1].lower()
            mime_type = {
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".png": "image/png",
                ".gif": "image/gif",
                ".webp": "image/webp"
            }.get(ext, "image/png")
            
            # Add reference image to content
            content_parts.append({
                "inline_data": {
                    "mime_type": mime_type,
                    "data": base64.b64encode(ref_image_data).decode("utf-8")
                }
            })
            
            # Modify prompt to reference the style
            aspect_instruction = "Generate a PORTRAIT (tall) image suitable for a side panel layout." if image_aspect == "portrait" else "Generate a LANDSCAPE (wide) image."
            enhanced_prompt = f"{aspect_instruction} Generate an illustration in the same artistic style as the reference image. {prompt}"
            content_parts.append(enhanced_prompt)
        else:
            aspect_instruction = "Generate a PORTRAIT (tall) image suitable for a side panel layout." if image_aspect == "portrait" else "Generate a LANDSCAPE (wide) image."
            content_parts.append(f"{aspect_instruction} {prompt}")
        
        print(f"[Imagen] Generating image with prompt: {prompt[:50]}...")
        
        # Robust retry logic for Imagen
        max_retries = 5
        retry_delays = [10, 30, 60, 120]
        last_error = None
        
        for attempt in range(max_retries):
            try:
                response = model.generate_content(content_parts)
                
                if hasattr(response, 'candidates') and response.candidates:
                    for part in response.candidates[0].content.parts:
                        if hasattr(part, 'inline_data'):
                            print(f"[Imagen] Success!")
                            return part.inline_data.data
                
                print(f"[Imagen] No image data in response.")
                return None
                
            except Exception as e:
                last_error = e
                err_str = str(e)
                is_rate_limit = any(x in err_str for x in ["429", "Resource exhausted", "Quota exceeded", "ResourceExhausted"])
                is_busy = any(x in err_str for x in ["503", "Service Unavailable", "500", "Internal error"])
                is_timeout = any(x in err_str for x in ["504", "Deadline expired", "DeadlineExceeded", "timeout", "Timeout"])
                
                if (is_rate_limit or is_busy or is_timeout) and attempt < max_retries - 1:
                    wait_time = retry_delays[min(attempt, len(retry_delays)-1)] + random.uniform(0, 5)
                    print(f"[Imagen] Rate limit/Busy/Timeout (attempt {attempt+1}/{max_retries}), waiting {wait_time:.1f}s...")
                    import time
                    time.sleep(wait_time)
                    continue
                else:
                    print(f"[Imagen] Error: {e}")
                    return None
    except Exception as e:
        print(f"[Imagen] Unexpected error: {e}")
        return None


async def regenerate_slide_illustration(
    job_id: str,
    slide_number: int,
    feedback: str,
    gemini_key: Optional[str] = None,
    video_width: int = VIDEO_WIDTH,
    video_height: int = VIDEO_HEIGHT
) -> Dict[str, Any]:
    """
    Regenerate ONLY the illustration image for a specific slide based on feedback.
    The slide layout and copy remain unchanged - only the image is regenerated.
    """
    import os
    import base64
    from playwright.async_api import async_playwright
    from config import OUTPUT_DIR
    
    key = gemini_key or GEMINI_API_KEY
    if not key:
        return {"success": False, "error": "Gemini API key is required"}
    
    slide_data = get_slide_data(job_id)
    if not slide_data:
        return {"success": False, "error": f"Slide data not found for job {job_id}"}
    
    slides = slide_data.get("slides", [])
    if slide_number < 1 or slide_number > len(slides):
        return {"success": False, "error": f"Invalid slide number: {slide_number}"}
    
    slide = slides[slide_number - 1]
    
    # Get reference image path if exists
    reference_image_path = None
    ref_dir = os.path.join(OUTPUT_DIR, f"{job_id}_reference")
    if os.path.exists(ref_dir):
        for ext in ['.png', '.jpg', '.jpeg', '.webp']:
            ref_path = os.path.join(ref_dir, f"reference{ext}")
            if os.path.exists(ref_path):
                reference_image_path = ref_path
                break
    
    # Build improved prompt with user feedback
    slide_copy = slide.get("slide_copy", {})
    visual_suggestion = slide.get("visual_suggestion", {})
    base_prompt = visual_suggestion.get("image_prompt") or visual_suggestion.get("description", "")
    
    if not base_prompt:
        title = slide_copy.get("headline") or slide.get("title", "")
        base_prompt = f"illustration for: {title}"
    
    feedback_prompt = f"""Create an explanatory diagram illustration.
Original concept: {base_prompt}
User feedback: {feedback}
Please incorporate the feedback to improve the illustration."""
    
    print(f"[Image Regen] Regenerating image for slide {slide_number}...")
    
    img_data = await generate_slide_image(feedback_prompt, key, reference_image_path)
    
    if not img_data:
        return {"success": False, "error": "Failed to generate new image"}
    
    slides_dir = os.path.join(OUTPUT_DIR, f"{job_id}_slides")
    os.makedirs(slides_dir, exist_ok=True)
    
    illustration_path = os.path.join(slides_dir, f"slide_illustration_{slide_number:03d}.png")
    with open(illustration_path, "wb") as f:
        f.write(img_data)
    
    current_html = get_html_content(job_id, slide_number)
    if not current_html:
        return {"success": False, "error": "Current HTML not found"}
    
    img_base64 = base64.b64encode(img_data).decode("utf-8")
    new_data_url = f"data:image/png;base64,{img_base64}"
    
    import re
    data_url_pattern = r'src="data:image/[^"]+base64,[^"]+"'
    
    if re.search(data_url_pattern, current_html):
        new_html = re.sub(data_url_pattern, f'src="{new_data_url}"', current_html)
    else:
        file_url_pattern = r'src="[^"]*slide_illustration_\d+\.png[^"]*"'
        if re.search(file_url_pattern, current_html):
            new_html = re.sub(file_url_pattern, f'src="{new_data_url}"', current_html)
        else:
            return {"success": False, "error": "Could not find image to replace"}
    
    update_html_content(job_id, slide_number, new_html)
    
    output_path = os.path.join(slides_dir, f"slide_{slide_number:03d}.png")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": video_width, "height": video_height})
        new_html = fix_body_dimensions(new_html, video_width, video_height)
        await page.set_content(new_html)
        await page.wait_for_timeout(500)
        await page.screenshot(path=output_path)
        await browser.close()
    
    return {
        "success": True,
        "slide_number": slide_number,
        "preview_url": f"/outputs/{job_id}_slides/slide_{slide_number:03d}.png"
    }

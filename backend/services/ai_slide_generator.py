"""
VoiceSlide AI - AI-Generated Custom Slide Design
Uses Gemini to generate unique HTML/CSS for each slide based on content
"""

import json
import base64
from typing import Dict, Any, List, Optional
import google.generativeai as genai

from config import GEMINI_API_KEY, VIDEO_WIDTH, VIDEO_HEIGHT


# Reference design examples for AI to learn from
DESIGN_EXAMPLES = """
# 参考デザイン例

## 例1: フロー図スライド
```html
<div class="slide cosmic-theme">
  <div class="section-label">PROCESS OF VALUE</div>
  <h1 class="title gradient-gold">インプットとアウトプット</h1>
  
  <div class="flow-diagram">
    <div class="flow-item">
      <div class="icon-circle purple">📥</div>
      <h3>インプット</h3>
      <p class="subtitle">INFORMATION</p>
      <div class="glass-card">
        <p>世界中にある有料・無料の情報。まずは自分の中に取り入れる「情報の収集」フェーズ。</p>
      </div>
    </div>
    
    <div class="flow-arrow">›</div>
    
    <div class="flow-item">
      <div class="icon-circle cyan">🔄</div>
      <h3>自分のフィルター</h3>
      <p class="subtitle">PROCESSING</p>
      <div class="glass-card">
        <p>取り入れた情報を自分の感性や経験を通して解釈し、咀嚼するプロセス。</p>
      </div>
    </div>
    
    <div class="flow-arrow">›</div>
    
    <div class="flow-item">
      <div class="icon-circle gold">📤</div>
      <h3>アウトプット</h3>
      <p class="subtitle">CREATION</p>
      <div class="glass-card">
        <p>フィルターを通したものを表現して外に出す。ここで初めて<span class="highlight">「価値」</span>が生まれる。</p>
      </div>
    </div>
  </div>
  
  <div class="bottom-quote">「自分が吸収して、自分のフィルターや感性の中で落とし込んで、アウトプットしていく」</div>
</div>
```

## 例2: 波及効果スライド（円形図）
```html
<div class="slide dark-theme">
  <div class="section-label">RIPPLE EFFECT OF OUTPUT</div>
  <h1 class="title gradient-pink">価値の波及</h1>
  
  <div class="two-column">
    <div class="left-panel">
      <div class="point-card accent-left">
        <span class="icon">💎</span>
        <h3>1. 価値になる</h3>
        <p>アウトプットしたその瞬間に、それはあなた独自の「価値」として存在し始めます。</p>
      </div>
      
      <div class="point-card accent-left">
        <span class="icon">📡</span>
        <h3>2. 多くの人に届く</h3>
        <p>発信された価値は電波のように波及し、あなたの知らない場所まで届いていきます。</p>
      </div>
      
      <div class="point-card accent-left">
        <span class="icon">💼</span>
        <h3>3. ビジネスの可能性</h3>
        <p>価値が届くことで共鳴が生まれ、それがビジネスや新しい機会へと繋がります。</p>
      </div>
    </div>
    
    <div class="right-panel">
      <div class="ripple-diagram">
        <div class="center-circle gold">
          <span class="icon">📤</span>
          OUTPUT
        </div>
        <div class="orbit orbit-1"></div>
        <div class="orbit orbit-2"></div>
        <div class="orbit orbit-3"></div>
        <div class="satellite" style="--angle: 45deg; --distance: 120px">
          <span>⭐</span> Value
        </div>
        <div class="satellite" style="--angle: 135deg; --distance: 180px">
          <span>📡</span> Reach
        </div>
        <div class="satellite" style="--angle: 270deg; --distance: 220px">
          <span>💼</span> Business
        </div>
      </div>
    </div>
  </div>
</div>
```

## 例3: 3カラムカード
```html
<div class="slide gradient-bg">
  <div class="section-label">VALUE OF ADDITION</div>
  <h2 class="subtitle">足し算の価値</h2>
  <p class="tagline">アウトプットとは、単なる出力ではない</p>
  <h1 class="hero-title">表現することで、<br><span class="highlight">価値は確かになる。</span></h1>
  
  <div class="three-cards">
    <div class="feature-card gradient-top-cyan">
      <div class="card-icon">🔍</div>
      <h3>理解が深まる</h3>
      <p>インプットした情報を自分の言葉に変換する過程で本質的な理解へと変わる</p>
    </div>
    
    <div class="feature-card gradient-top-purple">
      <div class="card-icon">👁️</div>
      <h3>先が見える</h3>
      <p>アウトプットを重ねることで視座が高まり次のステップが見えてくる</p>
    </div>
    
    <div class="feature-card gradient-top-gold">
      <div class="card-icon">✓</div>
      <h3>価値の確定</h3>
      <p>頭の中にあるだけではまだ「イリュージョン」。出すことで「現実の価値」になる</p>
    </div>
  </div>
  
  <div class="bottom-quote">"アウトプットも足し算。表現することで確かになっていく"</div>
</div>
```

## 例4: タイトルスライド（背景画像）
```html
<div class="slide full-bg-image">
  <div class="overlay gradient-dark"></div>
  <div class="centered-content">
    <div class="intro-label">HELLO, I'M ETO</div>
    <h1 class="mega-title gradient-gold">宇宙と価値の足し算</h1>
    <h2 class="sub-title">宇宙の足し算と<br>引き算のイリュージョン</h2>
    
    <div class="quote-box glass">
      「宇宙は増える足し算しかない。<br>引き算はイリュージョンなんだ。」
    </div>
    
    <div class="corner-label">🪐 Thinking about the Universe</div>
  </div>
</div>
```
"""


HTML_GENERATION_PROMPT = """あなたは世界クラスのプレゼンテーションデザイナーです。
与えられたスライド内容から、美しくユニークなHTML/CSSを生成してください。

# スライド情報
タイトル: {title}
サブタイトル: {subtitle}
ポイント:
{points}
キーメッセージ: {key_message}
スライド番号: {slide_number} / {total_slides}

# デザイン要件

1. **サイズ**: 幅{width}px × 高さ{height}px
2. **フォント**: 'Noto Sans JP'を使用
3. **テーマ**: ダークテーマ（背景は暗いグラデーション）
4. **アクセント**: 適切な色のグラデーションやハイライト
5. **スタイル**: 
   - グラスモーフィズム（半透明カード）
   - グラデーションテキスト
   - アイコン（絵文字を使用）
   - 装飾的な要素（オービット、波紋、フローアローなど）

# 参考デザイン
{design_examples}

# 重要な指示

1. **内容に合わせたレイアウト**を選択：
   - 3つのポイント → 3カラムカードまたはフロー図
   - 引用・メッセージ → センター配置の大きなテキスト
   - タイトル → フルスクリーンの印象的なデザイン
   - プロセス → 矢印で繋がるフロー

2. **視覚的階層**を意識：
   - 最も重要な情報は大きく、目立つ色で
   - 補足情報は小さく、サブカラーで

3. **装飾要素**を追加：
   - 適切なアイコン（絵文字）
   - 微妙なグラデーション
   - グラスモーフィズムカード
   - 引用バー（bottom-quote）

4. **スライド番号**を右下に表示

# 出力形式

完全なHTML（<!DOCTYPE html>から</html>まで）を出力してください。
CSSはすべて<style>タグ内にインラインで記述してください。
外部リソースはGoogle Fonts（Noto Sans JP）のみ使用可能です。

```html
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;700;900&display=swap" rel="stylesheet">
    <style>
        /* あなたのCSS */
    </style>
</head>
<body>
    <!-- あなたのHTML -->
</body>
</html>
```

HTMLのみを出力してください。説明は不要です。
"""


async def generate_custom_slide_html(
    slide: Dict[str, Any],
    slide_number: int,
    total_slides: int,
    gemini_key: Optional[str] = None
) -> str:
    """
    Generate completely custom HTML/CSS for a slide using Gemini
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
    points_str = "\n".join([f"- {p}" if isinstance(p, str) else f"- {p}" for p in raw_points])
    
    prompt = HTML_GENERATION_PROMPT.format(
        title=title,
        subtitle=subtitle,
        points=points_str if raw_points else "(ポイントなし)",
        key_message=key_message,
        slide_number=slide_number,
        total_slides=total_slides,
        width=VIDEO_WIDTH,
        height=VIDEO_HEIGHT,
        design_examples=DESIGN_EXAMPLES
    )
    
    try:
        # Use Gemini 2.0 Flash for fast HTML generation
        model = genai.GenerativeModel("gemini-2.0-flash-exp")
        
        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                temperature=0.8,  # More creative
                max_output_tokens=4096
            )
        )
        
        html = response.text.strip()
        
        # Extract HTML if wrapped in markdown code block
        if "```html" in html:
            html = html.split("```html")[1].split("```")[0].strip()
        elif "```" in html:
            html = html.split("```")[1].split("```")[0].strip()
        
        # Validate HTML
        if not html.startswith("<!DOCTYPE") and not html.startswith("<html"):
            print(f"[Custom Slide] Warning: Invalid HTML for slide {slide_number}, using fallback")
            return generate_fallback_html(slide, slide_number, total_slides)
        
        print(f"[Custom Slide] Generated unique design for slide {slide_number}")
        return html
        
    except Exception as e:
        print(f"[Custom Slide] Error for slide {slide_number}: {e}")
        return generate_fallback_html(slide, slide_number, total_slides)


def generate_fallback_html(
    slide: Dict[str, Any],
    slide_number: int,
    total_slides: int
) -> str:
    """Generate a basic fallback HTML if AI fails"""
    slide_copy = slide.get("slide_copy", {})
    
    title = slide_copy.get("headline") or slide.get("title", "")
    subtitle = slide_copy.get("subheadline") or slide.get("subtitle", "")
    raw_points = slide_copy.get("bullet_points") or slide.get("points", [])
    key_message = slide_copy.get("key_message") or ""
    
    points_html = ""
    for i, point in enumerate(raw_points):
        point_text = point if isinstance(point, str) else str(point)
        icons = ["💡", "⭐", "🎯", "✨", "🚀"]
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
            background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
            color: #fff;
            padding: 60px 80px;
            display: flex;
            flex-direction: column;
        }}
        .title {{
            font-size: 48px;
            font-weight: 900;
            margin-bottom: 16px;
            background: linear-gradient(135deg, #F59E0B, #FBBF24);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
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
            padding: 20px;
            background: rgba(255,255,255,0.05);
            border-radius: 12px;
            border-left: 4px solid #F59E0B;
        }}
        .icon {{ font-size: 24px; }}
        .text {{ font-size: 18px; line-height: 1.6; }}
        .key-message {{
            margin-top: auto;
            padding: 20px;
            text-align: center;
            font-size: 16px;
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
    gemini_key: Optional[str] = None
) -> List[str]:
    """
    Generate all slides with custom AI-generated HTML
    """
    import os
    from playwright.async_api import async_playwright
    from config import OUTPUT_DIR
    
    slides_dir = os.path.join(OUTPUT_DIR, f"{job_id}_slides")
    os.makedirs(slides_dir, exist_ok=True)
    
    image_paths = []
    total_slides = len(slides)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        
        for i, slide in enumerate(slides):
            slide_number = i + 1
            
            # Generate custom HTML for this slide
            html = await generate_custom_slide_html(
                slide=slide,
                slide_number=slide_number,
                total_slides=total_slides,
                gemini_key=gemini_key
            )
            
            # Render to image
            page = await browser.new_page(viewport={"width": VIDEO_WIDTH, "height": VIDEO_HEIGHT})
            await page.set_content(html)
            await page.wait_for_timeout(1500)  # Wait for fonts
            
            output_path = os.path.join(slides_dir, f"slide_{slide_number:03d}.png")
            await page.screenshot(path=output_path, type="png")
            await page.close()
            
            image_paths.append(output_path)
            print(f"[Custom Slides] Generated slide {slide_number}/{total_slides}")
        
        await browser.close()
    
    return image_paths

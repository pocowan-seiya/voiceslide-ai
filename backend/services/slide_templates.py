"""
VoiceSlide AI - Professional Slide Templates
High-quality HTML/CSS templates inspired by Genspark design
"""

from typing import Dict, Any, List


def get_base_styles() -> str:
    """
    Base CSS styles for all slides
    """
    return """
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;700;900&display=swap');
    
    * {
        margin: 0;
        padding: 0;
        box-sizing: border-box;
    }
    
    body {
        font-family: 'Noto Sans JP', sans-serif;
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
        color: #ffffff;
        width: 1280px;
        height: 720px;
        overflow: hidden;
    }
    
    .slide {
        width: 1280px;
        height: 720px;
        padding: 60px;
        position: relative;
    }
    
    .section-label {
        font-size: 14px;
        font-weight: 500;
        color: #94a3b8;
        text-transform: uppercase;
        letter-spacing: 2px;
        margin-bottom: 16px;
    }
    
    .title {
        font-size: 48px;
        font-weight: 900;
        line-height: 1.2;
        margin-bottom: 24px;
    }
    
    .subtitle {
        font-size: 20px;
        color: #94a3b8;
        line-height: 1.6;
    }
    
    .card {
        background: rgba(30, 41, 59, 0.8);
        border: 1px solid rgba(148, 163, 184, 0.2);
        border-radius: 16px;
        padding: 24px;
    }
    
    .card-dark {
        background: rgba(15, 23, 42, 0.9);
        border: 1px solid rgba(148, 163, 184, 0.15);
    }
    
    .icon-badge {
        width: 48px;
        height: 48px;
        border-radius: 12px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 24px;
    }
    
    .icon-badge.cyan { background: #22d3ee; color: #0f172a; }
    .icon-badge.orange { background: #fb923c; color: #0f172a; }
    .icon-badge.purple { background: #a78bfa; color: #0f172a; }
    .icon-badge.green { background: #4ade80; color: #0f172a; }
    
    .number-badge {
        width: 32px;
        height: 32px;
        border-radius: 50%;
        background: #22d3ee;
        color: #0f172a;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: 700;
        font-size: 14px;
    }
    
    .step-number {
        font-size: 48px;
        font-weight: 900;
        color: rgba(148, 163, 184, 0.3);
        position: absolute;
        top: 20px;
        right: 24px;
    }
    
    .slide-number {
        display: none;  /* Hidden per user request */
        position: absolute;
        bottom: 30px;
        right: 60px;
        font-size: 14px;
        color: #64748b;
    }
    
    .accent-line {
        width: 4px;
        height: 80px;
        background: linear-gradient(180deg, #22d3ee 0%, #6366f1 100%);
        border-radius: 2px;
    }
    
    .connection-line {
        position: absolute;
        stroke: rgba(148, 163, 184, 0.3);
        stroke-width: 2;
        fill: none;
    }
    
    .footer-message {
        position: absolute;
        bottom: 60px;
        left: 60px;
        right: 60px;
        background: rgba(34, 211, 238, 0.1);
        border: 1px solid rgba(34, 211, 238, 0.3);
        border-radius: 12px;
        padding: 16px 24px;
        display: flex;
        align-items: center;
        gap: 12px;
    }
    
    .footer-message .icon {
        color: #22d3ee;
    }
    """


def template_title_slide(data: Dict[str, Any]) -> str:
    """
    Template 1: Title Slide
    Large title with subtitle and gradient background
    """
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            {get_base_styles()}
            
            .slide {{
                display: flex;
                flex-direction: column;
                justify-content: center;
                align-items: center;
                text-align: center;
                background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 50%, #312e81 100%);
            }}
            
            .title {{
                font-size: 64px;
                background: linear-gradient(135deg, #ffffff 0%, #c7d2fe 100%);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                margin-bottom: 32px;
            }}
            
            .subtitle {{
                font-size: 24px;
                max-width: 800px;
            }}
            
            .decorative-circle {{
                position: absolute;
                border-radius: 50%;
                border: 1px solid rgba(99, 102, 241, 0.3);
            }}
            
            .circle-1 {{ width: 400px; height: 400px; top: -100px; right: -100px; }}
            .circle-2 {{ width: 300px; height: 300px; bottom: -80px; left: -80px; }}
        </style>
    </head>
    <body>
        <div class="slide">
            <div class="decorative-circle circle-1"></div>
            <div class="decorative-circle circle-2"></div>
            <h1 class="title">{data.get('title', '')}</h1>
            <p class="subtitle">{data.get('subtitle', '')}</p>
        </div>
    </body>
    </html>
    """


def template_flow_diagram(data: Dict[str, Any]) -> str:
    """
    Template 2: Flow Diagram with connected cards
    Shows progression from Stage 1 → Stage 2 → Stage 3
    """
    stages = data.get('stages', [])
    stages_html = ""
    
    positions = [
        {"left": "60px", "top": "280px"},
        {"left": "440px", "top": "200px"},
        {"left": "820px", "top": "120px"},
    ]
    
    colors = ["cyan", "orange", "purple"]
    icons = ["👤", "🎯", "👑"]
    
    for i, stage in enumerate(stages[:3]):
        pos = positions[i] if i < len(positions) else positions[-1]
        color = colors[i] if i < len(colors) else colors[-1]
        icon = icons[i] if i < len(icons) else icons[-1]
        
        points_html = ""
        for point in stage.get('points', [])[:3]:
            points_html += f'<div class="stage-point">→ {point}</div>'
        
        stages_html += f"""
        <div class="stage-card" style="left: {pos['left']}; top: {pos['top']};">
            <div class="icon-badge {color}">{icon}</div>
            <div class="stage-label">STAGE {i+1}</div>
            <div class="stage-title">{stage.get('title', '')}</div>
            <div class="stage-points">{points_html}</div>
        </div>
        """
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            {get_base_styles()}
            
            .stage-card {{
                position: absolute;
                width: 320px;
                background: rgba(30, 41, 59, 0.9);
                border: 1px solid rgba(148, 163, 184, 0.2);
                border-radius: 16px;
                padding: 24px;
            }}
            
            .stage-label {{
                font-size: 12px;
                color: #94a3b8;
                text-transform: uppercase;
                letter-spacing: 1px;
                margin-top: 16px;
            }}
            
            .stage-title {{
                font-size: 24px;
                font-weight: 700;
                margin: 8px 0 16px 0;
            }}
            
            .stage-point {{
                font-size: 14px;
                color: #cbd5e1;
                margin: 8px 0;
            }}
            
            svg.connection {{
                position: absolute;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                pointer-events: none;
            }}
        </style>
    </head>
    <body>
        <div class="slide">
            <h1 class="title">{data.get('title', '')}</h1>
            <p class="subtitle">{data.get('subtitle', '')}</p>
            
            <svg class="connection">
                <path d="M 380 400 Q 420 300 440 280" class="connection-line"/>
                <path d="M 760 280 Q 800 200 820 200" class="connection-line"/>
            </svg>
            
            {stages_html}
        </div>
    </body>
    </html>
    """


def template_three_columns(data: Dict[str, Any]) -> str:
    """
    Template 3: Three Column Grid
    Numbered cards with icons
    """
    columns = data.get('columns', [])
    columns_html = ""
    
    colors = ["cyan", "green", "purple"]
    
    for i, col in enumerate(columns[:3]):
        color = colors[i] if i < len(colors) else colors[-1]
        
        points_html = ""
        for point in col.get('points', [])[:4]:
            points_html += f"""
            <div class="point-item">
                <span class="number-badge">{len(points_html.split('point-item')) }</span>
                <span>{point}</span>
            </div>
            """
        
        columns_html += f"""
        <div class="column-card card-dark">
            <div class="step-number">0{i+1}</div>
            <div class="icon-badge {color}">{col.get('icon', '📌')}</div>
            <h3 class="column-title">{col.get('title', '')}</h3>
            <div class="column-content">{col.get('description', '')}</div>
            {points_html}
        </div>
        """
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            {get_base_styles()}
            
            .columns-container {{
                display: grid;
                grid-template-columns: repeat(3, 1fr);
                gap: 24px;
                margin-top: 40px;
            }}
            
            .column-card {{
                position: relative;
                padding: 32px 24px;
            }}
            
            .column-title {{
                font-size: 20px;
                font-weight: 700;
                margin: 20px 0 12px 0;
            }}
            
            .column-content {{
                font-size: 14px;
                color: #94a3b8;
                line-height: 1.6;
            }}
            
            .point-item {{
                display: flex;
                align-items: center;
                gap: 12px;
                margin-top: 16px;
                font-size: 14px;
            }}
        </style>
    </head>
    <body>
        <div class="slide">
            <div class="section-label">{data.get('section', '')}</div>
            <h1 class="title">{data.get('title', '')}</h1>
            <p class="subtitle">{data.get('subtitle', '')}</p>
            
            <div class="columns-container">
                {columns_html}
            </div>
            
            <div class="slide-number">{data.get('slide_number', '')}</div>
        </div>
    </body>
    </html>
    """


def template_four_steps(data: Dict[str, Any]) -> str:
    """
    Template 4: Four Step Process
    Circular badges with centered text
    """
    steps = data.get('steps', [])
    steps_html = ""
    
    colors = ["cyan", "green", "orange", "purple"]
    
    for i, step in enumerate(steps[:4]):
        color = colors[i] if i < len(colors) else colors[-1]
        steps_html += f"""
        <div class="step-card">
            <div class="step-badge {color}">{i+1}</div>
            <div class="icon-circle {color}">{step.get('icon', '⚡')}</div>
            <h4 class="step-title">{step.get('title', '')}</h4>
            <p class="step-description">{step.get('description', '')}</p>
        </div>
        """
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            {get_base_styles()}
            
            .header-row {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 40px;
            }}
            
            .steps-container {{
                display: grid;
                grid-template-columns: repeat(4, 1fr);
                gap: 24px;
                margin-top: 60px;
            }}
            
            .step-card {{
                text-align: center;
                position: relative;
            }}
            
            .step-badge {{
                position: absolute;
                top: -15px;
                left: 50%;
                transform: translateX(-50%);
                width: 30px;
                height: 30px;
                border-radius: 50%;
                display: flex;
                align-items: center;
                justify-content: center;
                font-weight: 700;
                font-size: 14px;
                border: 2px solid;
            }}
            
            .step-badge.cyan {{ background: transparent; border-color: #22d3ee; color: #22d3ee; }}
            .step-badge.green {{ background: transparent; border-color: #4ade80; color: #4ade80; }}
            .step-badge.orange {{ background: transparent; border-color: #fb923c; color: #fb923c; }}
            .step-badge.purple {{ background: transparent; border-color: #a78bfa; color: #a78bfa; }}
            
            .icon-circle {{
                width: 80px;
                height: 80px;
                border-radius: 50%;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 32px;
                margin: 20px auto 16px auto;
                border: 2px solid;
            }}
            
            .icon-circle.cyan {{ border-color: #22d3ee; background: rgba(34, 211, 238, 0.1); }}
            .icon-circle.green {{ border-color: #4ade80; background: rgba(74, 222, 128, 0.1); }}
            .icon-circle.orange {{ border-color: #fb923c; background: rgba(251, 146, 60, 0.1); }}
            .icon-circle.purple {{ border-color: #a78bfa; background: rgba(167, 139, 250, 0.1); }}
            
            .step-title {{
                font-size: 18px;
                font-weight: 700;
                margin-bottom: 8px;
            }}
            
            .step-description {{
                font-size: 13px;
                color: #94a3b8;
                line-height: 1.5;
            }}
            
            .note-text {{
                font-size: 14px;
                color: #94a3b8;
            }}
        </style>
    </head>
    <body>
        <div class="slide">
            <div class="header-row">
                <div>
                    <h1 class="title" style="font-size: 36px;">{data.get('title', '')}</h1>
                </div>
                <div class="note-text">{data.get('note', '')}</div>
            </div>
            
            <div class="steps-container">
                {steps_html}
            </div>
            
            <div class="footer-message">
                <span class="icon">✓</span>
                <span>{data.get('footer_message', '')}</span>
            </div>
            
            <div class="slide-number">{data.get('slide_number', '')}</div>
        </div>
    </body>
    </html>
    """


def template_comparison(data: Dict[str, Any]) -> str:
    """
    Template 5: Before/After Comparison
    """
    before = data.get('before', {})
    after = data.get('after', {})
    
    before_points = ""
    for point in before.get('points', []):
        before_points += f'<div class="point">❌ {point}</div>'
    
    after_points = ""
    for point in after.get('points', []):
        after_points += f'<div class="point">✅ {point}</div>'
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            {get_base_styles()}
            
            .comparison-container {{
                display: grid;
                grid-template-columns: 1fr auto 1fr;
                gap: 40px;
                align-items: center;
                margin-top: 60px;
            }}
            
            .comparison-card {{
                padding: 32px;
            }}
            
            .comparison-label {{
                font-size: 12px;
                text-transform: uppercase;
                letter-spacing: 1px;
                margin-bottom: 16px;
            }}
            
            .comparison-title {{
                font-size: 24px;
                font-weight: 700;
                margin-bottom: 24px;
            }}
            
            .point {{
                font-size: 15px;
                margin: 12px 0;
                color: #cbd5e1;
            }}
            
            .arrow {{
                font-size: 48px;
                color: #64748b;
            }}
            
            .before {{ border-left: 4px solid #64748b; }}
            .after {{ border-left: 4px solid #22d3ee; }}
        </style>
    </head>
    <body>
        <div class="slide">
            <div class="section-label">{data.get('section', '')}</div>
            <h1 class="title">{data.get('title', '')}</h1>
            
            <div class="comparison-container">
                <div class="comparison-card card before">
                    <div class="comparison-label" style="color: #64748b;">{before.get('label', 'BEFORE')}</div>
                    <div class="comparison-title">{before.get('title', '')}</div>
                    {before_points}
                </div>
                
                <div class="arrow">→</div>
                
                <div class="comparison-card card after">
                    <div class="comparison-label" style="color: #22d3ee;">{after.get('label', 'AFTER')}</div>
                    <div class="comparison-title">{after.get('title', '')}</div>
                    {after_points}
                </div>
            </div>
            
            <div class="slide-number">{data.get('slide_number', '')}</div>
        </div>
    </body>
    </html>
    """


def template_content_with_image(data: Dict[str, Any]) -> str:
    """
    Template 6: Content with Image/Illustration
    Text on left, image on right
    """
    points = data.get('points', [])
    points_html = ""
    
    for i, point in enumerate(points[:4]):
        points_html += f"""
        <div class="point-row">
            <div class="point-bullet">{point.get('icon', '•')}</div>
            <div class="point-content">
                <div class="point-title">{point.get('title', '')}</div>
                <div class="point-desc">{point.get('description', '')}</div>
            </div>
        </div>
        """
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            {get_base_styles()}
            
            .content-layout {{
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 60px;
                margin-top: 40px;
            }}
            
            .content-side {{
                display: flex;
                flex-direction: column;
            }}
            
            .image-side {{
                display: flex;
                align-items: center;
                justify-content: center;
            }}
            
            .image-placeholder {{
                width: 100%;
                height: 400px;
                background: linear-gradient(135deg, rgba(99, 102, 241, 0.2) 0%, rgba(34, 211, 238, 0.2) 100%);
                border-radius: 16px;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 64px;
            }}
            
            .point-row {{
                display: flex;
                gap: 16px;
                margin: 16px 0;
            }}
            
            .point-bullet {{
                width: 40px;
                height: 40px;
                background: rgba(34, 211, 238, 0.2);
                border-radius: 10px;
                display: flex;
                align-items: center;
                justify-content: center;
                flex-shrink: 0;
            }}
            
            .point-title {{
                font-weight: 600;
                margin-bottom: 4px;
            }}
            
            .point-desc {{
                font-size: 14px;
                color: #94a3b8;
            }}
        </style>
    </head>
    <body>
        <div class="slide">
            <div class="section-label">{data.get('section', '')}</div>
            <h1 class="title" style="font-size: 36px;">{data.get('title', '')}</h1>
            
            <div class="content-layout">
                <div class="content-side">
                    {points_html}
                </div>
                <div class="image-side">
                    <div class="image-placeholder">{data.get('image_emoji', '🖼️')}</div>
                </div>
            </div>
            
            <div class="slide-number">{data.get('slide_number', '')}</div>
        </div>
    </body>
    </html>
    """


def template_key_points(data: Dict[str, Any]) -> str:
    """
    Template 7: Key Points with accent line
    """
    points = data.get('points', [])
    points_html = ""
    
    for point in points[:5]:
        points_html += f"""
        <div class="key-point">
            <span class="bullet">•</span>
            <span>{point}</span>
        </div>
        """
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            {get_base_styles()}
            
            .content-with-accent {{
                display: flex;
                gap: 40px;
                margin-top: 60px;
            }}
            
            .key-point {{
                font-size: 20px;
                margin: 24px 0;
                display: flex;
                gap: 16px;
                align-items: flex-start;
            }}
            
            .bullet {{
                color: #22d3ee;
                font-size: 24px;
            }}
        </style>
    </head>
    <body>
        <div class="slide">
            <div class="section-label">{data.get('section', '')}</div>
            <h1 class="title">{data.get('title', '')}</h1>
            <p class="subtitle">{data.get('subtitle', '')}</p>
            
            <div class="content-with-accent">
                <div class="accent-line"></div>
                <div class="points-container">
                    {points_html}
                </div>
            </div>
            
            <div class="slide-number">{data.get('slide_number', '')}</div>
        </div>
    </body>
    </html>
    """


# Template registry
TEMPLATES = {
    "title": template_title_slide,
    "flow": template_flow_diagram,
    "three_columns": template_three_columns,
    "four_steps": template_four_steps,
    "comparison": template_comparison,
    "content_image": template_content_with_image,
    "key_points": template_key_points,
}


def get_template(template_type: str) -> callable:
    """
    Get template function by type
    """
    return TEMPLATES.get(template_type, template_key_points)


def render_template(template_type: str, data: Dict[str, Any]) -> str:
    """
    Render a template with given data
    """
    template_func = get_template(template_type)
    return template_func(data)

"""
VoiceSlide AI - Enhanced Slide Structure Generator
Two-phase generation: Outline → Full Slides with template mapping
"""

import json
from typing import List, Dict, Any, Optional
from openai import OpenAI
import google.generativeai as genai

from config import OPENAI_API_KEY, GEMINI_API_KEY


# Initialize clients
openai_client = OpenAI(api_key=OPENAI_API_KEY)
genai.configure(api_key=GEMINI_API_KEY)


OUTLINE_GENERATION_PROMPT = """
あなたはプロフェッショナルなプレゼンテーション構成アドバイザーです。
音声トランスクリプトを分析し、効果的なスライドアウトラインを作成してください。

【構成の原則】
1. 最初はタイトルスライド（プレゼン全体のテーマを示す）
2. 導入→本論→結論の流れを意識
3. 1スライド1メッセージを徹底
4. 聞き手の興味を維持する構成
5. 最後はまとめ・結論・CTAで締める

【スライドタイプの選択】
以下のテンプレートから最適なものを選んでください：

- "title": タイトルスライド（冒頭、セクション区切り）
- "flow": フロー図（3段階の進化や変遷を示す）
- "three_columns": 3カラム（3つの並列な概念を比較）
- "four_steps": 4ステップ（プロセスや手順を示す）
- "comparison": 比較（Before/After、従来/新規）
- "content_image": コンテンツ＋画像（説明＋視覚資料）
- "key_points": 要点リスト（重要ポイントを列挙）

【出力形式】
JSON形式で以下の構造を返してください：
{
  "presentation_title": "プレゼン全体のタイトル",
  "outline": [
    {
      "slide_number": 1,
      "template_type": "title",
      "title": "スライドタイトル",
      "key_message": "このスライドで伝えたい核心メッセージ",
      "suggested_content": "含めるべき内容の概要",
      "timing_start": 0.0,
      "timing_end": 15.0
    }
  ],
  "total_duration": 180.0,
  "structure_notes": "全体構成についてのメモ"
}

【トランスクリプト】
"""


SLIDE_DESIGN_PROMPT = """
あなたはプロフェッショナルなプレゼンテーションデザイナーです。
承認されたアウトラインに基づいて、各スライドの詳細なコンテンツを作成してください。

【デザイン原則】
- Gensparkスタイルの洗練されたビジネスプレゼン
- 余白を活かしたクリーンなレイアウト
- 情報は厳選して凝縮
- 視覚的階層を明確に

【テンプレート別の出力形式】

"title"の場合:
{
  "template_type": "title",
  "title": "メインタイトル",
  "subtitle": "サブタイトル"
}

"flow"の場合:
{
  "template_type": "flow",
  "title": "スライドタイトル",
  "subtitle": "説明文",
  "stages": [
    {"title": "ステージ名", "points": ["ポイント1", "ポイント2"]}
  ]
}

"three_columns"の場合:
{
  "template_type": "three_columns",
  "section": "セクションラベル",
  "title": "スライドタイトル",
  "subtitle": "説明",
  "columns": [
    {"icon": "🔍", "title": "カラムタイトル", "description": "説明", "points": ["項目1"]}
  ]
}

"four_steps"の場合:
{
  "template_type": "four_steps",
  "title": "スライドタイトル",
  "note": "補足メモ",
  "steps": [
    {"icon": "🎯", "title": "ステップ名", "description": "説明"}
  ],
  "footer_message": "まとめメッセージ"
}

"comparison"の場合:
{
  "template_type": "comparison",
  "section": "セクションラベル",
  "title": "スライドタイトル",
  "before": {"label": "従来", "title": "タイトル", "points": ["ポイント"]},
  "after": {"label": "新規", "title": "タイトル", "points": ["ポイント"]}
}

"content_image"の場合:
{
  "template_type": "content_image",
  "section": "セクションラベル",
  "title": "スライドタイトル",
  "points": [
    {"icon": "💡", "title": "ポイント", "description": "説明"}
  ],
  "image_emoji": "🖼️"
}

"key_points"の場合:
{
  "template_type": "key_points",
  "section": "セクションラベル",
  "title": "スライドタイトル",
  "subtitle": "説明",
  "points": ["ポイント1", "ポイント2", "ポイント3"]
}

【アウトライン】
"""


async def generate_outline(transcript: str, segments: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Phase 1: Generate slide outline from transcript
    """
    formatted_transcript = format_transcript_with_segments(transcript, segments)
    
    try:
        outline = await generate_outline_with_gemini(formatted_transcript)
        if outline:
            return outline
    except Exception as e:
        print(f"Gemini outline failed: {e}")
    
    return await generate_outline_with_gpt4(formatted_transcript)


async def generate_slides(outline: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Phase 2: Generate detailed slide content from outline
    """
    outline_json = json.dumps(outline, ensure_ascii=False, indent=2)
    
    try:
        slides = await generate_slides_with_gemini(outline_json)
        if slides:
            return slides
    except Exception as e:
        print(f"Gemini slides failed: {e}")
    
    return await generate_slides_with_gpt4(outline_json)


def format_transcript_with_segments(transcript: str, segments: List[Dict[str, Any]]) -> str:
    """
    Format transcript with timing information
    """
    if not segments:
        return transcript
    
    lines = []
    for seg in segments:
        start = f"{seg['start']:.1f}s"
        end = f"{seg['end']:.1f}s"
        lines.append(f"[{start} - {end}] {seg['text']}")
    
    return "\n".join(lines)


async def generate_outline_with_gemini(transcript: str) -> Dict[str, Any]:
    """
    Generate outline using Gemini
    """
    model = genai.GenerativeModel("gemini-3-flash-preview")
    
    prompt = OUTLINE_GENERATION_PROMPT + transcript
    
    response = model.generate_content(
        prompt,
        generation_config=genai.GenerationConfig(
            response_mime_type="application/json"
        )
    )
    
    return json.loads(response.text)


async def generate_outline_with_gpt4(transcript: str) -> Dict[str, Any]:
    """
    Generate outline using GPT-4
    """
    response = openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": "You are a professional presentation structure advisor. Always respond with valid JSON."
            },
            {
                "role": "user",
                "content": OUTLINE_GENERATION_PROMPT + transcript
            }
        ],
        response_format={"type": "json_object"}
    )
    
    return json.loads(response.choices[0].message.content)


async def generate_slides_with_gemini(outline_json: str) -> List[Dict[str, Any]]:
    """
    Generate detailed slides using Gemini
    """
    model = genai.GenerativeModel("gemini-3-flash-preview")
    
    prompt = SLIDE_DESIGN_PROMPT + outline_json + """

【出力形式】
以下のJSON形式で返してください：
{
  "slides": [
    // 各スライドのデータ（テンプレートタイプに応じた形式）
  ]
}
"""
    
    response = model.generate_content(
        prompt,
        generation_config=genai.GenerationConfig(
            response_mime_type="application/json"
        )
    )
    
    result = json.loads(response.text)
    return result.get("slides", [])


async def generate_slides_with_gpt4(outline_json: str) -> List[Dict[str, Any]]:
    """
    Generate detailed slides using GPT-4
    """
    response = openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": "You are a professional presentation designer. Create detailed slide content. Always respond with valid JSON."
            },
            {
                "role": "user",
                "content": SLIDE_DESIGN_PROMPT + outline_json + '\n\nReturn JSON with "slides" array.'
            }
        ],
        response_format={"type": "json_object"}
    )
    
    result = json.loads(response.choices[0].message.content)
    return result.get("slides", [])

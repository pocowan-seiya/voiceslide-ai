"""
VoiceSlide AI v3 - 高精度スライドアナライザー
Gemini Visionでスライドの詳細な内容を抽出
"""

import os
import base64
import json
from typing import List, Dict, Any
from PIL import Image
import google.generativeai as genai

from config import GEMINI_API_KEY, OUTPUT_DIR


# Configure Gemini
genai.configure(api_key=GEMINI_API_KEY)


async def analyze_slides(file_path: str, file_type: str, job_id: str) -> Dict[str, Any]:
    """
    スライドを分析し、内容を詳細に抽出
    
    Args:
        file_path: PDFまたは画像ファイルのパス
        file_type: 'pdf' or 'images'
        job_id: ジョブID
    
    Returns:
        画像パスと分析結果のDict
    """
    slides_dir = os.path.join(OUTPUT_DIR, f"{job_id}_slides")
    os.makedirs(slides_dir, exist_ok=True)
    
    # 画像に変換
    if file_type == "pdf":
        images = await pdf_to_images(file_path, slides_dir)
    else:
        images = await copy_images(file_path, slides_dir)
    
    print(f"📊 {len(images)}枚のスライドを分析中...")
    
    # 各スライドをGemini Visionで分析
    contents = []
    for i, image_path in enumerate(images):
        print(f"🔍 スライド {i+1}/{len(images)} を分析中...")
        content = await analyze_slide_image(image_path, i + 1)
        contents.append(content)
        print(f"   → タイトル: {content.get('title', '不明')}")
    
    return {
        "images": images,
        "contents": contents
    }


async def pdf_to_images(pdf_path: str, output_dir: str) -> List[str]:
    """PDFを画像に変換"""
    try:
        from pdf2image import convert_from_path
        
        pages = convert_from_path(pdf_path, dpi=150)
        
        image_paths = []
        for i, page in enumerate(pages):
            image_path = os.path.join(output_dir, f"slide_{i+1:03d}.png")
            page.save(image_path, "PNG")
            image_paths.append(image_path)
        
        return image_paths
    
    except Exception as e:
        print(f"PDF変換エラー: {e}")
        raise Exception(f"PDF変換に失敗しました: {e}")


async def copy_images(source_path: str, output_dir: str) -> List[str]:
    """画像ファイルをコピー"""
    import shutil
    import glob
    
    if os.path.isdir(source_path):
        patterns = ["*.png", "*.jpg", "*.jpeg", "*.PNG", "*.JPG", "*.JPEG"]
        image_files = []
        for pattern in patterns:
            image_files.extend(glob.glob(os.path.join(source_path, pattern)))
        image_files.sort()
    else:
        image_files = [source_path]
    
    image_paths = []
    for i, src in enumerate(image_files):
        dst = os.path.join(output_dir, f"slide_{i+1:03d}.png")
        
        if src.lower().endswith(('.jpg', '.jpeg')):
            img = Image.open(src)
            img.save(dst, "PNG")
        else:
            shutil.copy2(src, dst)
        
        image_paths.append(dst)
    
    return image_paths


async def analyze_slide_image(image_path: str, slide_number: int, model_name: str = "gemini-3-flash-preview") -> Dict[str, Any]:
    """
    Gemini Visionでスライド画像を詳細分析
    マッピング精度向上のため、より多くの情報を抽出
    """
    try:
        with open(image_path, "rb") as f:
            image_data = f.read()
        
        model = genai.GenerativeModel(model_name)
        
        # より詳細な分析プロンプト
        prompt = """このスライド画像を詳細に分析してください。
音声との同期マッピングに使用するため、できるだけ多くの情報を抽出してください。

【出力形式】
以下のJSON形式で返してください:

{
  "title": "スライドのタイトル（大きな文字で表示されているもの）",
  "subtitle": "サブタイトルがあれば",
  "main_content": "スライドの主な内容を2-3文で詳細に説明",
  "key_points": [
    "箇条書きや要点があれば抽出（最大5個）"
  ],
  "keywords": [
    "スライドに含まれる重要なキーワード（最大10個）",
    "専門用語、固有名詞、数字なども含む"
  ],
  "visible_text": "スライドに表示されている主要なテキスト全体",
  "slide_type": "title（タイトルスライド）/ content（内容スライド）/ section（セクション区切り）/ summary（まとめ）/ chart（グラフ/図表）/ image（画像中心）",
  "numbers_and_data": "数字、統計、日付などがあれば",
  "visual_elements": "グラフ、図、画像などの視覚要素の説明"
}

スライドに日本語と英語が混在している場合は両方を抽出してください。
見出しや重要なキーワードは特に正確に抽出してください。"""
        
        image_part = {
            "mime_type": "image/png",
            "data": base64.b64encode(image_data).decode("utf-8")
        }
        
        response = model.generate_content(
            [prompt, image_part],
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json"
            )
        )
        
        content = json.loads(response.text)
        content["slide_number"] = slide_number
        content["image_path"] = image_path
        
        # キーワードが少ない場合、タイトルと内容から追加
        if len(content.get("keywords", [])) < 3:
            extra_keywords = extract_keywords_from_text(
                f"{content.get('title', '')} {content.get('main_content', '')}"
            )
            existing = set(content.get("keywords", []))
            for kw in extra_keywords:
                if kw not in existing:
                    content.setdefault("keywords", []).append(kw)
        
        return content
    
    except Exception as e:
        print(f"スライド{slide_number}の分析エラー: {e}")
        return {
            "slide_number": slide_number,
            "image_path": image_path,
            "title": f"スライド {slide_number}",
            "subtitle": "",
            "main_content": "",
            "key_points": [],
            "keywords": [],
            "visible_text": "",
            "slide_type": "content",
            "numbers_and_data": "",
            "visual_elements": "",
            "error": str(e)
        }


def extract_keywords_from_text(text: str) -> List[str]:
    """テキストから重要なキーワードを抽出"""
    import re
    
    # 日本語のカタカナ語、英単語、数字を含む表現を抽出
    patterns = [
        r'[ァ-ヴー]{3,}',  # カタカナ3文字以上
        r'[a-zA-Z]{4,}',   # 英単語4文字以上
        r'\d+[%％]',       # パーセント
        r'\d+[万億]?円',   # 金額
        r'\d+[年月日時分秒]', # 日時
    ]
    
    keywords = []
    for pattern in patterns:
        matches = re.findall(pattern, text)
        keywords.extend(matches)
    
    return list(set(keywords))[:10]

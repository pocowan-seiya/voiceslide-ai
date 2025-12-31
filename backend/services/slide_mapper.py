"""
VoiceSlide AI v3 - 高精度スライドマッパー
音声とスライドの完璧な同期を実現
"""

import json
import re
from typing import List, Dict, Any, Tuple
import google.generativeai as genai
from openai import OpenAI

from config import GEMINI_API_KEY, OPENAI_API_KEY


# Initialize clients
genai.configure(api_key=GEMINI_API_KEY)
openai_client = OpenAI(api_key=OPENAI_API_KEY)


async def map_slides_to_audio(
    slides: List[Dict[str, Any]],
    segments: List[Dict[str, Any]],
    total_duration: float
) -> List[Dict[str, Any]]:
    """
    高精度AIマッピング - スライドと音声セグメントを内容ベースで同期
    
    核心原則:
    1. 音声の全時間を使用（0秒から最後まで）
    2. スライド内容と音声内容を意味的にマッチング
    3. スライドの順序を維持
    4. 自然な切り替えポイントを検出
    """
    
    if not slides or not segments:
        return fallback_even_distribution(len(slides) if slides else 1, total_duration)
    
    # Step 1: スライドと音声の詳細な分析データを準備
    slide_analysis = prepare_detailed_slide_info(slides)
    segment_analysis = prepare_detailed_segment_info(segments)
    
    # Step 2: AIによる高精度マッピング
    mapping_prompt = create_precision_mapping_prompt(
        slide_analysis, 
        segment_analysis, 
        total_duration,
        len(slides)
    )
    
    try:
        # Gemini Pro を使用（より高精度）
        model = genai.GenerativeModel("gemini-1.5-pro")
        response = model.generate_content(
            mapping_prompt,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                temperature=0.1  # 低温度で一貫性を高める
            )
        )
        
        result = json.loads(response.text)
        timing_map = result.get("timing_map", [])
        
    except Exception as e:
        print(f"Gemini Pro mapping failed: {e}, trying GPT-4o")
        
        try:
            response = openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system", 
                        "content": """あなたはプレゼンテーション同期の専門家です。
スライドと音声の内容を分析し、最適なタイミングを決定します。
必ず有効なJSONを返してください。"""
                    },
                    {"role": "user", "content": mapping_prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.1
            )
            
            result = json.loads(response.choices[0].message.content)
            timing_map = result.get("timing_map", [])
            
        except Exception as e2:
            print(f"GPT-4o mapping also failed: {e2}")
            return fallback_even_distribution(len(slides), total_duration)
    
    # Step 3: タイミングの検証と修正
    timing_map = validate_and_fix_timing(timing_map, len(slides), total_duration, segments)
    
    return timing_map


def prepare_detailed_slide_info(slides: List[Dict[str, Any]]) -> str:
    """スライドの詳細情報をフォーマット"""
    lines = []
    
    for slide in slides:
        num = slide.get("slide_number", "?")
        title = slide.get("title", "無題")
        content = slide.get("main_content", "")
        keywords = slide.get("keywords", [])
        key_points = slide.get("key_points", [])
        slide_type = slide.get("slide_type", "content")
        
        lines.append(f"━━━ スライド {num} ━━━")
        lines.append(f"タイプ: {slide_type}")
        lines.append(f"タイトル: {title}")
        
        if content:
            lines.append(f"内容要約: {content}")
        
        if key_points:
            lines.append(f"要点: {', '.join(key_points)}")
        
        if keywords:
            lines.append(f"キーワード: {', '.join(keywords)}")
        
        lines.append("")
    
    return "\n".join(lines)


def prepare_detailed_segment_info(segments: List[Dict[str, Any]]) -> str:
    """音声セグメントの詳細情報をフォーマット"""
    lines = []
    
    for seg in segments:
        idx = seg.get("id", "?")
        start = seg.get("start", 0)
        end = seg.get("end", 0)
        text = seg.get("text", "").strip()
        
        # 時間をMM:SS形式に変換
        start_str = f"{int(start//60):02d}:{int(start%60):02d}"
        end_str = f"{int(end//60):02d}:{int(end%60):02d}"
        
        lines.append(f"[{idx}] {start_str}-{end_str} ({start:.1f}s-{end:.1f}s): {text}")
    
    return "\n".join(lines)


def create_precision_mapping_prompt(
    slide_info: str, 
    segment_info: str, 
    total_duration: float,
    slide_count: int
) -> str:
    """高精度マッピング用のプロンプトを生成"""
    
    return f"""# タスク: 音声とスライドの完璧な同期マッピング

あなたは音声プレゼンテーションの同期専門家です。
以下の音声文字起こしとスライド内容を分析し、各スライドの最適な表示タイミングを決定してください。

## 重要な原則

### 1. 音声の全時間を使用
- 開始: 0.0秒
- 終了: {total_duration:.1f}秒
- すべての音声時間がスライドでカバーされる必要があります

### 2. 内容ベースのマッチング
- スライドのタイトル・キーワードが音声で言及された時点で表示開始
- 話題が変わるタイミングでスライドを切り替え
- 単語の完全一致ではなく、意味的な関連性で判断

### 3. 自然な切り替え
- 文の終わり、間、「次に」「そして」などの接続詞の後
- 各スライドは最低5秒間表示（内容を読む時間）

### 4. スライドの順序維持
- スライドは1から{slide_count}まで順番に表示
- スライド1は必ず0秒から開始
- スライド{slide_count}は必ず{total_duration:.1f}秒まで表示

---

## スライド一覧（{slide_count}枚）

{slide_info}

---

## 音声文字起こし（タイムスタンプ付き）

{segment_info}

---

## 分析手順

1. 各スライドのキーワードを特定
2. そのキーワードが最初に言及されるセグメントを見つける
3. そのセグメントの開始時刻をスライドの開始時刻とする
4. 次のスライドの開始時刻を現在のスライドの終了時刻とする
5. 最後のスライドは音声終了まで表示

---

## 出力形式

以下のJSON形式で、全{slide_count}枚のスライドのタイミングを返してください:

{{
  "analysis": "マッピングの根拠の説明（日本語で簡潔に）",
  "timing_map": [
    {{
      "slide_number": 1,
      "start_time": 0.0,
      "end_time": 数値,
      "matched_segments": [マッチしたセグメントIDのリスト],
      "match_reason": "このタイミングにした理由"
    }},
    ...（全{slide_count}枚分）
  ]
}}

重要:
- start_time と end_time は小数点以下1桁の数値
- 隣接するスライドの end_time と start_time は一致させる
- スライド1の start_time は必ず 0.0
- スライド{slide_count}の end_time は必ず {total_duration:.1f}"""


def validate_and_fix_timing(
    timing_map: List[Dict[str, Any]], 
    slide_count: int, 
    total_duration: float,
    segments: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    タイミングマップを検証し修正
    - 全スライドが存在することを確認
    - ギャップや重複を修正
    - 音声の全時間をカバー
    """
    
    # 空の場合はフォールバック
    if not timing_map:
        return fallback_even_distribution(slide_count, total_duration)
    
    # スライド番号でソート
    timing_map.sort(key=lambda x: x.get("slide_number", 0))
    
    # 欠けているスライドを追加
    existing_numbers = {t.get("slide_number") for t in timing_map}
    for i in range(1, slide_count + 1):
        if i not in existing_numbers:
            timing_map.append({
                "slide_number": i,
                "start_time": 0,
                "end_time": 0,
                "matched_segments": [],
                "match_reason": "自動補完"
            })
    
    # 再度ソート
    timing_map.sort(key=lambda x: x.get("slide_number", 0))
    
    # スライド数を調整
    timing_map = timing_map[:slide_count]
    
    # 時間の整合性を確保
    # 最初のスライドは0秒から
    timing_map[0]["start_time"] = 0.0
    
    # start_timeでソート（番号順ではなく時間順に修正が必要な場合）
    timing_map.sort(key=lambda x: (x.get("start_time", 0), x.get("slide_number", 0)))
    
    # スライド番号を再割り当て（時間順に）
    for i, item in enumerate(timing_map):
        item["slide_number"] = i + 1
    
    # 連続性を確保
    for i in range(len(timing_map)):
        if i == 0:
            timing_map[i]["start_time"] = 0.0
        else:
            # 前のスライドの終了時刻を現在の開始時刻に
            timing_map[i]["start_time"] = timing_map[i-1]["end_time"]
        
        # 終了時刻が開始時刻より前の場合、修正
        if timing_map[i].get("end_time", 0) <= timing_map[i]["start_time"]:
            if i < len(timing_map) - 1:
                # 次のスライドまでの時間を計算
                remaining_duration = total_duration - timing_map[i]["start_time"]
                remaining_slides = len(timing_map) - i
                timing_map[i]["end_time"] = timing_map[i]["start_time"] + (remaining_duration / remaining_slides)
            else:
                timing_map[i]["end_time"] = total_duration
    
    # 最後のスライドは必ず音声終了まで
    timing_map[-1]["end_time"] = total_duration
    
    # 最小表示時間（3秒）を確保
    min_duration = 3.0
    for i in range(len(timing_map) - 1):
        current_duration = timing_map[i]["end_time"] - timing_map[i]["start_time"]
        if current_duration < min_duration:
            # 時間が足りない場合、後続スライドから借りる
            needed = min_duration - current_duration
            available = timing_map[i+1]["end_time"] - timing_map[i+1]["start_time"] - min_duration
            
            if available > 0:
                adjust = min(needed, available)
                timing_map[i]["end_time"] += adjust
                timing_map[i+1]["start_time"] += adjust
    
    # 最終検証: 合計時間が total_duration と一致
    actual_end = timing_map[-1]["end_time"]
    if abs(actual_end - total_duration) > 0.1:
        timing_map[-1]["end_time"] = total_duration
    
    return timing_map


def fallback_even_distribution(slide_count: int, total_duration: float) -> List[Dict[str, Any]]:
    """フォールバック: スライドを均等に分配"""
    if slide_count == 0:
        slide_count = 1
    
    duration_per_slide = total_duration / slide_count
    
    timing_map = []
    for i in range(slide_count):
        timing_map.append({
            "slide_number": i + 1,
            "start_time": round(i * duration_per_slide, 1),
            "end_time": round((i + 1) * duration_per_slide, 1),
            "matched_segments": [],
            "match_reason": "均等分配（自動）"
        })
    
    # 最後のスライドの終了時刻を正確に
    timing_map[-1]["end_time"] = total_duration
    
    return timing_map


def find_keyword_in_segments(keyword: str, segments: List[Dict[str, Any]]) -> Tuple[int, float]:
    """
    キーワードが最初に出現するセグメントを見つける
    Returns: (segment_id, start_time)
    """
    keyword_lower = keyword.lower()
    
    for seg in segments:
        text = seg.get("text", "").lower()
        if keyword_lower in text:
            return (seg.get("id", 0), seg.get("start", 0))
    
    return (-1, -1)


def calculate_semantic_similarity(slide_content: str, segment_text: str) -> float:
    """
    スライド内容とセグメントテキストの意味的類似度を計算
    シンプルなキーワードマッチングベース
    """
    # キーワードを抽出
    slide_words = set(re.findall(r'\w+', slide_content.lower()))
    segment_words = set(re.findall(r'\w+', segment_text.lower()))
    
    # 共通キーワード数
    common = slide_words & segment_words
    
    if not slide_words:
        return 0.0
    
    return len(common) / len(slide_words)

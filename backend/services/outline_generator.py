"""
VoiceSlide AI v3 - 高精度音声同期アウトラインジェネレーター
タイムスタンプ精度を最優先にしたスライド設計
"""

import json
import re
from typing import List, Dict, Any
from openai import OpenAI
import google.generativeai as genai

from config import OPENAI_API_KEY, GEMINI_API_KEY


# Initialize clients
openai_client = OpenAI(api_key=OPENAI_API_KEY)
genai.configure(api_key=GEMINI_API_KEY)


def repair_and_parse_json(text: str, source: str = "API") -> Dict[str, Any]:
    """
    JSONを修復してパースする
    長い音声でGeminiが返す壊れたJSONを修復
    """
    # まず直接パースを試みる
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        print(f"[{source}] JSON parse failed at char {e.pos}, attempting repair...")
    
    # Step 1: markdownのコードブロックからJSONを抽出
    if "```json" in text:
        match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
        if match:
            text = match.group(1)
    elif "```" in text:
        match = re.search(r'```\s*(.*?)\s*```', text, re.DOTALL)
        if match:
            text = match.group(1)
    
    # Step 2: 末尾の不完全な部分を除去して閉じる
    # 最後の有効な } または ] を見つける
    text = text.strip()
    
    # トレイリングカンマを除去
    text = re.sub(r',\s*}', '}', text)
    text = re.sub(r',\s*]', ']', text)
    
    # Step 3: 括弧のバランスを確認して修正
    open_braces = text.count('{')
    close_braces = text.count('}')
    open_brackets = text.count('[')
    close_brackets = text.count(']')
    
    # 足りない閉じ括弧を追加
    if close_brackets < open_brackets:
        text = text.rstrip()
        if text.endswith(','):
            text = text[:-1]
        text += ']' * (open_brackets - close_brackets)
    
    if close_braces < open_braces:
        text = text.rstrip()
        if text.endswith(','):
            text = text[:-1]
        text += '}' * (open_braces - close_braces)
    
    # Step 4: もう一度パースを試みる
    try:
        result = json.loads(text)
        print(f"[{source}] JSON repaired successfully!")
        return result
    except json.JSONDecodeError as e:
        print(f"[{source}] JSON repair failed at pos {e.pos}: {str(e)[:100]}")
        
        # Step 5: 最後の手段 - 有効なJSONの範囲を見つける
        # 最後の有効な閉じ括弧の位置を見つけて切り詰める
        for end_pos in range(len(text), 0, -1):
            try:
                truncated = text[:end_pos]
                # バランスを調整
                truncated = truncated.rstrip()
                if truncated.endswith(','):
                    truncated = truncated[:-1]
                
                ob = truncated.count('{')
                cb = truncated.count('}')
                ob2 = truncated.count('[')
                cb2 = truncated.count(']')
                
                truncated += ']' * max(0, ob2 - cb2)
                truncated += '}' * max(0, ob - cb)
                
                result = json.loads(truncated)
                print(f"[{source}] JSON truncated and repaired at position {end_pos}")
                return result
            except:
                continue
        
        raise ValueError(f"Could not repair JSON from {source}")


def extract_keywords_from_text(text: str) -> List[str]:
    """
    テキストから重要なキーワードを抽出
    自動生成スライド用のシンプルな抽出
    """
    if not text:
        return []
    
    # 日本語の助詞・接続詞などを除外
    stop_words = {
        "です", "ます", "した", "して", "という", "ている", "これ", "それ", "あれ",
        "この", "その", "あの", "ので", "から", "けど", "けれど", "でも", "しかし",
        "そして", "また", "さて", "では", "ところ", "こと", "もの", "ため", "よう",
        "など", "とか", "って", "みたい", "ような", "ように", "っていう", "っている",
        "本当", "自分", "今", "僕", "私", "あなた"
    }
    
    # テキストを単語に分割（簡易的）
    # 句読点で分割してから、長い単語を抽出
    words = []
    for part in re.split(r'[、。！？\s]+', text):
        # 2-8文字の単語を抽出（カタカナ・漢字・アルファベット）
        matches = re.findall(r'[ァ-ヴA-Za-z]{2,10}|[一-龥々]{2,6}', part)
        for word in matches:
            if word.lower() not in stop_words and word not in stop_words:
                words.append(word)
    
    # 重複を除去して最初の6個を返す
    seen = set()
    unique_words = []
    for word in words:
        if word not in seen:
            seen.add(word)
            unique_words.append(word)
            if len(unique_words) >= 6:
                break
    
    return unique_words

# ============================================================
# プロフェッショナル・プレゼンテーション・タイミング設計
# ============================================================

PRECISE_TIMESTAMP_PROMPT = """# 役割
あなたは20年の経験を持つプレゼンテーションコーチであり、
TEDトークやAppleの基調講演の演出を手がけてきたスライド同期の専門家です。

# プロフェッショナルのスライドタイミング設計原則

## 基本哲学
**「スライドは話し手のパートナーであり、視聴者の理解を助ける道具」**

スライドは早すぎても遅すぎてもいけません。
視聴者が「今の話の要点はこれか」と確認できる**最適なタイミング**が存在します。

---

## 1. スライド切り替えの黄金ルール

### A) オープニング・タイトルスライド
- **タイミング**: 冒頭の挨拶・自己紹介の間ずっと表示
- **理由**: 視聴者がプレゼンのテーマを把握する時間
- **目安**: 最初の20-30秒間

### B) 新しいトピックへの移行
- **悪い例**: 「次は〇〇について...」と言った瞬間に切り替え ❌
- **良い例**: 「次は〇〇について」の後、**実際に内容を説明し始めた時点**で切り替え ✅
- **理由**: 導入句の間はまだ前のスライドで脳が処理中
- **目安**: トピック宣言の **2-4秒後**

### C) 具体的な情報・データの提示
- **タイミング**: 話し手がデータや事実を言い始める**直前**に切り替え
- **理由**: 数字やグラフは「見ながら聞く」方が理解しやすい
- **注意**: これだけは例外的に「先出し」が有効

### D) ストーリー・エピソード
- **タイミング**: ストーリーが始まって**5-10秒後**にイメージスライドを表示
- **理由**: まず聞き手の想像力を働かせ、その後ビジュアルで補強
- **または**: ストーリー中はシンプルスライドを維持、結論で切り替え

### E) 結論・まとめ
- **タイミング**: 「まとめると」「つまり」の **1-2秒後** に切り替え
- **理由**: 視聴者が「これが結論だ」と認識してから視覚確認

---

## 2. 視聴者の認知プロセスを考慮

### 情報処理の時間
- 聴覚情報の処理: 約0.5秒
- 視覚情報の認識: 約0.3秒
- 両者の統合: 1-2秒
- **結論**: スライド切り替えは音声の **1.5-3秒後** が最適

### 「認知的負荷」の軽減
- スライドが変わる瞬間、視聴者の注意は画面に移る
- その間、音声は聞き流される
- **対策**: 重要なフレーズの**後**、次の文の**前**で切り替え

---

## 3. スライド表示時間の目安

| スライドタイプ | 最小時間 | 最適時間 | 最大時間 |
|---------------|---------|---------|---------|
| タイトル | 30秒 | 45-60秒 | 90秒 |
| 内容（テキスト中心） | 40秒 | 60-90秒 | 120秒 |
| データ・グラフ | 45秒 | 60-90秒 | 120秒 |
| 画像・ビジュアル | 30秒 | 45-60秒 | 90秒 |
| 区切り・セクション移行 | 20秒 | 30-45秒 | 60秒 |

---

## 4. 切り替えNGタイミング

絶対に避けるべきタイミング：
❌ 話し手が重要な単語を言っている最中
❌ 質問を投げかけている最中（「〜だと思いませんか？」）
❌ 視聴者が笑っている・反応している最中
❌ 感情的なクライマックスの瞬間
❌ 間（ま）を取っている最中

---

# 入力: 音声セグメント

{segments_with_timestamps}

# 音声の総時間: {total_duration}秒

---

# タスク

上記の音声セグメントを分析し、プロフェッショナルなタイミングでスライドアウトラインを作成してください。

## 分析手順

1. **音声の流れを把握**: 全体のストーリー構造を理解
2. **トピック転換点を特定**: 話題が変わる瞬間を見つける
3. **各トピックの性質を判断**: データ説明？ストーリー？結論？
4. **最適な切り替えタイミングを決定**: 上記原則に基づいて

## 判断基準

「このタイミングでスライドが変わったら、視聴者はどう感じるか？」

- 自然に感じる ✅
- 「あ、今の話の要点だ」と確認できる ✅
- 次の話題への心の準備ができる ✅
- 話を聞き逃した気がする ❌
- 唐突に感じる ❌
- ネタバレされた気がする ❌

---

# 🎯 最重要: 話題の転換点で分割する

## スライドを分割すべき場所（話題の転換シグナル）

以下のような**話題の転換を示す言葉**が出た**後**でスライドを切り替えてください：

### トピック転換の接続詞
- 「**さて**」「**では**」「**それでは**」→ 新しい話題の開始
- 「**次に**」「**続いて**」「**もう一つは**」→ 次のポイントへ
- 「**つまり**」「**ということで**」「**まとめると**」→ 結論・まとめ
- 「**例えば**」「**具体的には**」→ 具体例の開始
- 「**だから**」「**なので**」「**ですから**」→ 結論への導入

### 文の完結パターン
- 「〜**です。**」「〜**ですね。**」「〜**でした。**」→ 完結した文の後
- 「〜**と思います。**」「〜**と感じました。**」→ 意見の完結
- 「〜**ということなんですね。**」→ 説明の完結

## 絶対に分割してはいけない場所

❌ **文の途中**で分割しない（「〜して、」「〜けど、」の後で分割しない）
❌ **接続詞の直前**で分割しない（「さて」の前ではなく後で分割）
❌ **具体例の途中**で分割しない（「例えば〜」から結論まで同じスライド）
❌ **同じ話題の異なる側面**を別スライドにしない

## 実践的な判断基準

**質問**: 「ここでスライドが変わったら、視聴者は『あ、次の話題だ』と自然に感じるか？」

- **はい** → 分割OK ✅
- **いいえ、話の途中に見える** → 分割NG ❌

---

# 重要なルール

## スライド枚数の制限（最重要）
- **目安**: 音声1分あたり1枚程度（45-60秒に1スライド）
- **例**: 10分の音声 → 10-12枚程度、13分の音声 → 12-15枚程度
- **NG**: 13分の音声で18枚以上はスライドが細切れ過ぎ

## タイミングのバランス
- **各スライドの時間差は2倍以内**に抑える
- 例: 30秒のスライドがあれば、最長でも60秒程度
- **最後のスライドだけ極端に長い**のはNG（均等に分配）

## 基本ルール
1. **最初のスライドは 0.0秒 から開始**
2. **最後のスライドは {total_duration}秒 で終了**
3. **スライド間に隙間なし**
4. **最小表示時間: 30秒**（ゆったりとした視聴体験）
5. **最大表示時間: 120秒**（飽きさせない）
6. **トピック導入句の後に2-4秒待ってから切り替え**
7. **話題の転換シグナル（さて、では等）の後で分割する**

---

# 最重要: タイミングと内容の完全一致

## 設計の順序（これが最も重要）

1. **まず時間区間を決定する**
   - セグメントを分析し、話題の区切りを特定
   - 各スライドの timestamp_start と timestamp_end を決定

2. **次にその時間区間の内容を抽出する**
   - その時間内に話されている**実際の言葉**からタイトルを抽出
   - その時間内のキーワードのみを使用
   - speakers_wordsはその時間内の発言を正確に要約

## 内容と時間の整合性チェック

各スライドについて以下を確認:
✅ title: その時間帯（timestamp_start〜end）に話されている内容か？
✅ keywords: その時間帯に実際に発せられた言葉か？
✅ speakers_words: その時間帯の発言のみを含んでいるか？

❌ 過去の時間帯の内容を含んでいないか？
❌ 未来の時間帯の内容を含んでいないか？
❌ 全体のテーマを安易にタイトルにしていないか？

---

# 出力形式

以下のJSON形式で返してください。
**各スライドには、ユーザーがそのままスライド作成に使える詳細なコピーを含めてください。**

{{
  "presentation_title": "プレゼン全体のタイトル",
  "total_duration": {total_duration},
  "slides": [
    {{
      "number": 1,
      "timestamp_start": 0.0,
      "timestamp_end": 数値,
      "segment_ids": [この時間帯に該当するセグメントID],
      "title": "スライドのタイトル（slide_copy.headlineと同じ内容）",
      
      "slide_copy": {{
        "headline": "スライドのメインタイトル（大きく表示する見出し）",
        "subheadline": "サブタイトル（あれば）",
        "bullet_points": [
          "ポイント1: この時間帯に話し手が説明した具体的な内容",
          "ポイント2: 数字やデータがあれば含める",
          "ポイント3: 話し手の言葉をそのまま使う",
          "ポイント4: 具体例やエピソード"
        ],
        "key_message": "このスライドで最も伝えたい一文（話し手の言葉から抽出）",
        "call_to_action": "視聴者に促したいアクション（あれば）",
        "note_for_designer": "デザイナーへの補足説明"
      }},
      
      "speakers_words": "この時間帯に話し手が実際に言った言葉の正確な引用または要約",
      "keywords": ["この時間帯のキーワード1", "キーワード2", "キーワード3"],
      
      "visual_suggestion": {{
        "type": "text_only / image / chart / icon / diagram",
        "description": "推奨するビジュアル要素の説明",
        "image_prompt": "画像生成する場合のプロンプト案"
      }},
      
      "energy_level": "high/medium/low",
      "timing_reason": "なぜこのタイミングで切り替えるのか"
    }}
  ],
  "total_slides": スライド総数,
  "audio_match_score": 95
}}

---

# 具体例

## 入力セグメント例:
[ID:0] [00:00 - 00:08] 「皆さんこんにちは、本日はAIについてお話しします」
[ID:1] [00:08 - 00:20] 「まず最初に、AIとは何かを説明します」
[ID:2] [00:20 - 00:35] 「AIは人工知能の略で、機械学習がベースになっています」

## 正しい出力:
スライド1 (0.0秒〜20.0秒):
  title: "本日はAIについてお話しします" ← 00:00-00:08の発言から
  speakers_words: "挨拶とAIの説明を開始する導入" ← この時間帯の要約
  keywords: ["AI", "本日"] ← この時間帯に発せられた言葉

スライド2 (20.0秒〜35.0秒):
  title: "AIとは何か" ← 00:20-00:35の発言から  
  speakers_words: "AIは人工知能の略で機械学習がベース" ← この時間帯の要約
  keywords: ["人工知能", "機械学習"] ← この時間帯に発せられた言葉

## 間違いの例:
❌ スライド1のtitleに「機械学習」を含める（まだ話されていない）
❌ スライド2のkeywordsに「こんにちは」を含める（もう話し終わった）

---

# 重要な注意

- **各スライドの内容は、その時間帯(timestamp_start〜end)の発言のみに基づく**
- セグメントIDは入力の [ID:X] の X の値
- 隣接するスライドの timestamp_end と timestamp_start は同じ値にする
- title は必ずその時間帯の話し手の言葉から抽出する
"""


POLISH_PROMPT = """# タスク
アウトラインのタイムスタンプ精度を検証し、改善してください。

# 検証ポイント
1. スライド1の開始が0.0秒か
2. 最後のスライドの終了が総時間と一致しているか
3. スライド間に隙間がないか（前の終了 = 次の開始）
4. 各スライドが最低5秒あるか

# 入力セグメント情報
{segments_info}

# 現在のアウトライン
{current_outline}

# 出力
修正されたアウトラインを同じJSON形式で返してください。
"""


async def generate_outline(
    transcript: str, 
    segments: List[Dict[str, Any]], 
    gemini_key: str = None,
    slide_count_mode: str = "auto",
    custom_slide_count: int = 10
) -> Dict[str, Any]:
    """
    高精度タイムスタンプ同期のスライドアウトラインを生成
    
    Args:
        transcript: ユーザーが編集した可能性のある文字起こし（これを優先）
        segments: 元のタイムスタンプ情報（タイミング用）
        gemini_key: Optional Gemini API key from user
        slide_count_mode: "auto", "fewer", "more", or "custom"
        custom_slide_count: Target slide count when mode is "custom"
    """
    
    # Configure Gemini with provided key or default
    if gemini_key:
        genai.configure(api_key=gemini_key)
    elif GEMINI_API_KEY:
        genai.configure(api_key=GEMINI_API_KEY)
    else:
        raise ValueError("Gemini API key is required. Please set it in settings.")
    
    if not segments:
        return create_fallback_outline(transcript)
    
    # 正確なタイムスタンプ付きセグメント情報を作成
    segments_text = format_segments_precisely(segments)
    
    # 音声の総時間
    total_duration = segments[-1].get("end", 0)
    
    # スライド枚数の指示を生成
    slide_count_instruction = ""
    if slide_count_mode == "fewer":
        slide_count_instruction = "\n\n⚠️ スライド枚数の指示: **少なめ（5-7枚）** でまとめてください。トピックを大きくグループ化し、簡潔なスライドにしてください。\n"
    elif slide_count_mode == "more":
        slide_count_instruction = "\n\n⚠️ スライド枚数の指示: **多め（15枚以上）** で細かく分割してください。各ポイントを個別のスライドにし、詳細な説明を含めてください。\n"
    elif slide_count_mode == "custom":
        slide_count_instruction = f"\n\n⚠️ スライド枚数の指示: **ちょうど{custom_slide_count}枚** になるように調整してください。\n"
    
    # 編集されたトランスクリプトを追加（ユーザー編集を反映）
    edited_transcript_section = f"""
{slide_count_instruction}
# ユーザー編集後のトランスクリプト（最新版）

以下はユーザーが編集した可能性のあるトランスクリプトです。
**スライドの内容（タイトル、キーワード、コピー）はこのテキストから抽出してください。**
タイムスタンプはセグメント情報を参照してください。

---
{transcript}
---

"""
    
    prompt = PRECISE_TIMESTAMP_PROMPT.format(
        segments_with_timestamps=segments_text + edited_transcript_section,
        total_duration=f"{total_duration:.1f}"
    )
    
    try:
        # Gemini で高精度生成 (複数モデルを試行)
        model_names = ["gemini-2.0-flash-exp", "gemini-1.5-flash-latest", "gemini-pro"]
        response = None
        
        for model_name in model_names:
            try:
                print(f"[Outline] Trying model: {model_name}")
                model = genai.GenerativeModel(model_name)
                response = model.generate_content(
                    prompt,
                    generation_config=genai.GenerationConfig(
                        response_mime_type="application/json",
                        temperature=0.1,
                        max_output_tokens=16384  # Support long audio (10+ minutes)
                    )
                )
                print(f"[Outline] Success with {model_name}!")
                break
            except Exception as e:
                print(f"[Outline] Model {model_name} failed: {str(e)[:100]}")
                continue
        
        if response is None:
            raise ValueError("All Gemini models failed")
        
        result = repair_and_parse_json(response.text, "Gemini")
        
    except Exception as e:
        print(f"Gemini outline failed: {e}, falling back to GPT-4o")
        
        try:
            response = openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system", 
                        "content": "You are a timestamp-precise slide architect. Return valid JSON only. All timestamps must be accurate to 0.1 seconds."
                    },
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.1
            )
            result = repair_and_parse_json(response.choices[0].message.content, "GPT-4o")
            
        except Exception as e2:
            print(f"GPT-4o also failed: {e2}")
            return create_fallback_outline(transcript, segments)
    
    # タイムスタンプの検証と修正
    result = validate_and_fix_outline_timestamps(result, segments, total_duration)
    
    # セグメント情報を保持
    result["_segments"] = segments
    result["_total_duration"] = total_duration
    
    return result


async def polish_outline(outline: Dict[str, Any]) -> Dict[str, Any]:
    """
    アウトラインのタイムスタンプ精度を維持しながらブラッシュアップ
    """
    segments = outline.pop("_segments", [])
    total_duration = outline.pop("_total_duration", 0)
    
    segments_info = format_segments_precisely(segments) if segments else ""
    outline_json = json.dumps(outline, ensure_ascii=False, indent=2)
    
    prompt = POLISH_PROMPT.format(
        segments_info=segments_info,
        current_outline=outline_json
    )
    
    try:
        model_names = ["gemini-2.0-flash-exp", "gemini-1.5-flash-latest", "gemini-pro"]
        response = None
        
        for model_name in model_names:
            try:
                model = genai.GenerativeModel(model_name)
                response = model.generate_content(
                    prompt,
                    generation_config=genai.GenerationConfig(
                        response_mime_type="application/json",
                        max_output_tokens=16384  # Support long audio
                    )
                )
                break
            except Exception as e:
                print(f"[Polish Outline] Model {model_name} failed: {str(e)[:100]}")
                continue
        
        if response is None:
            raise ValueError("All Gemini models failed")
        
        result = json.loads(response.text)
        
    except Exception as e:
        print(f"Gemini polish failed: {e}, keeping original")
        result = outline
    
    # 再度タイムスタンプ検証
    if segments:
        result = validate_and_fix_outline_timestamps(result, segments, total_duration)
    
    result["_segments"] = segments
    result["_total_duration"] = total_duration
    
    return result


def format_segments_precisely(segments: List[Dict[str, Any]]) -> str:
    """
    セグメントを正確なタイムスタンプ付きでフォーマット
    """
    lines = []
    
    for seg in segments:
        seg_id = seg.get("id", 0)
        start = seg.get("start", 0)
        end = seg.get("end", 0)
        text = seg.get("text", "").strip()
        
        # MM:SS.S形式と秒数の両方を表示
        start_str = f"{int(start//60):02d}:{int(start%60):02d}"
        end_str = f"{int(end//60):02d}:{int(end%60):02d}"
        
        lines.append(f"[ID:{seg_id}] [{start_str} - {end_str}] (開始:{start:.1f}秒 終了:{end:.1f}秒)")
        lines.append(f"    「{text}」")
        lines.append("")
    
    return "\n".join(lines)


def validate_and_fix_outline_timestamps(
    outline: Dict[str, Any], 
    segments: List[Dict[str, Any]], 
    total_duration: float
) -> Dict[str, Any]:
    """
    アウトラインのタイムスタンプを検証・修正
    """
    slides = outline.get("slides", [])
    
    if not slides:
        return outline
    
    # スライド番号でソート
    slides.sort(key=lambda x: x.get("number", 0))
    
    # 1. 最初のスライドは0秒から
    slides[0]["timestamp_start"] = 0.0
    
    # 2. 連続性を確保（前のスライドの終了 = 次のスライドの開始）
    for i in range(len(slides)):
        if i > 0:
            slides[i]["timestamp_start"] = slides[i-1]["timestamp_end"]
        
        # 終了時刻が開始より前または未設定の場合
        current_end = slides[i].get("timestamp_end", 0)
        if current_end <= slides[i]["timestamp_start"]:
            # 残りの時間を均等に分配
            remaining = total_duration - slides[i]["timestamp_start"]
            remaining_slides = len(slides) - i
            slides[i]["timestamp_end"] = slides[i]["timestamp_start"] + (remaining / remaining_slides)
    
    # 3. 最後のスライドは総時間で終了
    slides[-1]["timestamp_end"] = total_duration
    
    # 4. 最後のスライドが極端に長い場合は分割（JSONが途中で切れた場合の対策）
    max_slide_duration = 120.0  # 最大2分
    last_slide_duration = slides[-1]["timestamp_end"] - slides[-1]["timestamp_start"]
    
    if last_slide_duration > max_slide_duration and segments:
        print(f"[Outline] Warning: Last slide is {last_slide_duration:.1f}s, splitting with content extraction...")
        
        # 残りの時間を適切な数のスライドに分割
        extra_time = last_slide_duration - max_slide_duration
        extra_slides_needed = int(extra_time / 60) + 1  # 60秒ごとに1スライド追加
        
        # 最後のスライドの開始時刻を調整
        original_start = slides[-1]["timestamp_start"]
        segment_duration = (total_duration - original_start) / (extra_slides_needed + 1)
        
        # 最後のスライドを短くして、追加スライドを作成
        slides[-1]["timestamp_end"] = original_start + segment_duration
        
        # 追加スライドを生成（セグメントから実際の内容を抽出）
        for j in range(extra_slides_needed):
            new_start = original_start + segment_duration * (j + 1)
            new_end = original_start + segment_duration * (j + 2)
            
            # この時間範囲のセグメントを抽出
            segment_texts = []
            for seg in segments:
                seg_start = seg.get("start", 0)
                seg_end = seg.get("end", 0)
                # この時間範囲に重なるセグメントを取得
                if seg_end > new_start and seg_start < new_end:
                    segment_texts.append(seg.get("text", ""))
            
            # セグメントからコンテンツを抽出
            combined_text = " ".join(segment_texts).strip()
            
            # タイトルを生成（最初の20文字程度）
            if combined_text:
                # 最初の文を取得
                first_sentence = combined_text.split("。")[0] if "。" in combined_text else combined_text[:30]
                title = first_sentence[:25] + "..." if len(first_sentence) > 25 else first_sentence
            else:
                title = f"セクション {len(slides) + 1}"
            
            # キーワードを抽出（重要そうな単語）
            keywords = extract_keywords_from_text(combined_text) if combined_text else []
            
            new_slide = {
                "number": len(slides) + 1,
                "title": title,
                "timestamp_start": round(new_start, 1),
                "timestamp_end": round(new_end, 1),
                "segment_ids": [],
                "speakers_words": combined_text[:200] if combined_text else "",
                "keywords": keywords[:6],  # 最大6個
                "visual_role": "内容を視覚的に補強",
                "main_visual": "テキストとアイコン",
                "energy_level": "medium",
                "_auto_generated": True
            }
            slides.append(new_slide)
        
        # 最後のスライドを総時間に合わせる
        slides[-1]["timestamp_end"] = total_duration
        
        print(f"[Outline] Split into {extra_slides_needed + 1} slides with extracted content")
    
    # 5. 最小時間（10秒）の確保 - プロフェッショナル基準
    min_duration = 10.0
    for i in range(len(slides) - 1):
        duration = slides[i]["timestamp_end"] - slides[i]["timestamp_start"]
        if duration < min_duration:
            # 時間を延長（後続スライドから借りる）
            needed = min_duration - duration
            slides[i]["timestamp_end"] += needed
            slides[i + 1]["timestamp_start"] = slides[i]["timestamp_end"]
    
    # 6. 小数点1桁に丸める
    for slide in slides:
        slide["timestamp_start"] = round(slide["timestamp_start"], 1)
        slide["timestamp_end"] = round(slide["timestamp_end"], 1)
    
    outline["slides"] = slides
    outline["total_duration"] = total_duration
    
    return outline


def create_fallback_outline(transcript: str, segments: List[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    フォールバック: 均等分配のアウトラインを作成
    """
    total_duration = 60.0
    if segments and len(segments) > 0:
        total_duration = segments[-1].get("end", 60.0)
    
    # 5スライドに均等分配
    slide_count = 5
    duration_per_slide = total_duration / slide_count
    
    slides = []
    for i in range(slide_count):
        slides.append({
            "number": i + 1,
            "title": f"セクション {i + 1}",
            "timestamp_start": round(i * duration_per_slide, 1),
            "timestamp_end": round((i + 1) * duration_per_slide, 1),
            "segment_ids": [],
            "speakers_words": "",
            "keywords": [],
            "visual_role": "内容を視覚的に補強",
            "main_visual": "テキストとアイコン",
            "energy_level": "medium"
        })
    
    slides[-1]["timestamp_end"] = total_duration
    
    return {
        "presentation_title": "プレゼンテーション",
        "total_duration": total_duration,
        "slides": slides,
        "total_slides": slide_count,
        "audio_match_score": 50,
        "_segments": segments or [],
        "_total_duration": total_duration
    }


def format_outline_for_export(outline: Dict[str, Any]) -> str:
    """
    アウトラインをMarkdown形式でエクスポート
    詳細なスライドコピーを含む
    """
    lines = []
    
    title = outline.get("presentation_title", "プレゼンテーション")
    total_duration = outline.get("total_duration", 0)
    
    lines.append(f"# {title}")
    lines.append("")
    
    # 総時間
    total_min = int(total_duration // 60)
    total_sec = int(total_duration % 60)
    lines.append(f"**音声の長さ**: {total_min}分{total_sec}秒")
    lines.append("")
    
    lines.append("---")
    lines.append("")
    
    slides = outline.get("slides", [])
    for slide in slides:
        num = slide.get("number", "")
        
        # タイムスタンプ
        start = slide.get("timestamp_start", 0)
        end = slide.get("timestamp_end", 0)
        start_str = f"{int(start//60):02d}:{int(start%60):02d}"
        end_str = f"{int(end//60):02d}:{int(end%60):02d}"
        duration = end - start
        
        # スライドコピーを取得
        slide_copy = slide.get("slide_copy", {})
        headline = slide_copy.get("headline") or slide.get("title", f"スライド {num}")
        subheadline = slide_copy.get("subheadline", "")
        bullet_points = slide_copy.get("bullet_points", [])
        key_message = slide_copy.get("key_message", "")
        note_for_designer = slide_copy.get("note_for_designer", "")
        
        lines.append(f"## スライド {num}")
        lines.append(f"**⏱️ {start_str} - {end_str}** ({duration:.0f}秒間)")
        lines.append("")
        
        # ヘッドライン
        lines.append(f"### 📌 見出し")
        lines.append(f"**{headline}**")
        if subheadline:
            lines.append(f"*{subheadline}*")
        lines.append("")
        
        # キーメッセージ
        if key_message:
            lines.append(f"### 💡 キーメッセージ")
            lines.append(f"> {key_message}")
            lines.append("")
        
        # 箇条書き
        if bullet_points:
            lines.append(f"### 📝 ポイント")
            for point in bullet_points:
                lines.append(f"- {point}")
            lines.append("")
        
        # キーワード
        keywords = slide.get("keywords", [])
        if keywords:
            lines.append(f"**🔑 キーワード**: {', '.join(keywords)}")
            lines.append("")
        
        # ビジュアル提案
        visual_suggestion = slide.get("visual_suggestion", {})
        if visual_suggestion:
            visual_type = visual_suggestion.get("type", "")
            visual_desc = visual_suggestion.get("description", "")
            if visual_type or visual_desc:
                lines.append(f"### 🎨 ビジュアル提案")
                if visual_type:
                    lines.append(f"- タイプ: {visual_type}")
                if visual_desc:
                    lines.append(f"- 内容: {visual_desc}")
                lines.append("")
        
        # デザイナーへのメモ
        if note_for_designer:
            lines.append(f"📋 *デザインメモ: {note_for_designer}*")
            lines.append("")
        
        # 話し手の言葉
        speakers_words = slide.get("speakers_words", "")
        if speakers_words:
            lines.append(f"💬 この時間帯の発言: 「{speakers_words}」")
            lines.append("")
        
        lines.append("---")
        lines.append("")
    
    return "\n".join(lines)


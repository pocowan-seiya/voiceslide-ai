# VoiceSlide AI

音声から自動でプレゼンテーション動画を生成するAIツール

## 機能

- 🎙️ 音声ファイルから文字起こし
- ✨ AIによるテキストブラッシュアップ
- 📋 スライドアウトライン自動生成
- 🎨 AIスライドデザイン（フルAIモード）
- 🎬 音声同期動画生成

## 必要な環境

- Node.js 20+
- Python 3.11+
- FFmpeg

## ローカル開発

```bash
# フロントエンド
npm install
npm run dev

# バックエンド
cd backend
pip install -r requirements.txt
python main.py
```

## 環境変数

`.env`ファイルを作成：

```
OPENAI_API_KEY=sk-xxx
GEMINI_API_KEY=xxx
```

## デプロイ

Railwayでデプロイ可能。詳細は `env.template` を参照。

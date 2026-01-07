# VoiceSlide AI

音声から自動でプレゼンテーション動画を生成するAIツール

## 機能

- 🎙️ 音声ファイルから文字起こし（フィラー除去対応）
- ✨ AIによるテキストブラッシュアップ
- 📋 スライドアウトライン自動生成
- 🎨 AIスライドデザイン（フルAIモード）
- 🔍 スライド自己検証・自動修正
- 🎬 音声同期動画生成

## 必要な環境

- Node.js 20+
- Python 3.11+
- FFmpeg
- Playwright（ブラウザ自動化）

---

## 🖥️ ローカル開発（Mac）

### 1. 依存関係のインストール

```bash
# フロントエンド
cd voiceslide-ai
npm install

# バックエンド
cd backend
pip install -r requirements.txt
playwright install chromium
```

### 2. 環境変数の設定

```bash
# ローカル用テンプレートからコピー
cp env.local.template .env.local
```

.env.local を編集（APIキーはブラウザから入力するため不要）:
```
NEXT_PUBLIC_API_URL=http://localhost:8000
OUTPUT_DIR=./outputs
DEBUG=true
```

### 3. 起動

**方法A: ワンコマンド起動（推奨）**
```bash
chmod +x start-local.sh
./start-local.sh
```

**方法B: 個別起動**
```bash
# ターミナル1: バックエンド
cd backend
python main.py

# ターミナル2: フロントエンド
npm run dev
```

### 4. アクセス

- 🌐 フロントエンド: http://localhost:3000
- 📡 バックエンド API: http://localhost:8000

ブラウザで http://localhost:3000 を開き、⚙️設定からAPIキーを入力してください。

---

## 🚀 本番デプロイ（Railway）

`env.template` を参照してください。

```bash
# Railwayでデプロイ
railway up
```

---

## 📁 ディレクトリ構成

```
voiceslide-ai/
├── app/              # Next.js フロントエンド
├── backend/          # FastAPI バックエンド
│   ├── services/     # AI・動画生成サービス
│   └── main.py       # APIエントリーポイント
├── components/       # Reactコンポーネント
├── outputs/          # 生成されたファイル（ローカル）
└── start-local.sh    # ローカル起動スクリプト
```

---

## 🔑 APIキー

以下のAPIキーが必要です（ブラウザから入力）:

- **Gemini API Key**: [Google AI Studio](https://aistudio.google.com/)
- **OpenAI API Key** (オプション): [OpenAI](https://platform.openai.com/)

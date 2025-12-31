# VoiceSlide AI - Production Dockerfile
# FFmpegを含むPython + Next.js環境

FROM node:20-slim AS frontend-builder

WORKDIR /app/frontend

# フロントエンドの依存関係をインストール
COPY package*.json ./
RUN npm ci

# フロントエンドをビルド
COPY . .
RUN npm run build

# -----------------------------------
# Production Image
# -----------------------------------
FROM python:3.11-slim

# 必要なシステムパッケージをインストール（FFmpeg含む）
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Node.jsをインストール（Next.jsサーバー用）
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python依存関係
COPY backend/requirements.txt ./backend/
RUN pip install --no-cache-dir -r backend/requirements.txt

# バックエンドコード
COPY backend ./backend

# フロントエンドビルド成果物
COPY --from=frontend-builder /app/frontend/.next ./.next
COPY --from=frontend-builder /app/frontend/node_modules ./node_modules
COPY --from=frontend-builder /app/frontend/package.json ./
COPY --from=frontend-builder /app/frontend/public ./public

# 出力・アップロードディレクトリ
RUN mkdir -p /app/outputs /app/uploads

# 起動スクリプト
COPY start.sh ./
RUN chmod +x start.sh

# ポート
EXPOSE 3000 8000

# 起動
CMD ["./start.sh"]

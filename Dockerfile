# VoiceSlide AI - Railway Dockerfile
# シンプルな構成：Next.js + Python Backend

FROM python:3.11-slim

# 必要なシステムパッケージをインストール（日本語フォント含む）
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    poppler-utils \
    fonts-noto-cjk \
    fonts-noto-cjk-extra \
    fontconfig \
    && rm -rf /var/lib/apt/lists/* \
    && fc-cache -fv

# Node.jsをインストール
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python依存関係をインストール
COPY backend/requirements.txt ./backend/
RUN pip install --no-cache-dir -r backend/requirements.txt

# Playwright Chromiumをインストール（HTMLレンダリング用）
RUN playwright install chromium --with-deps

# Node.js依存関係をインストール（フロントエンド）
COPY package*.json ./
RUN npm ci

# Backend Node.js依存関係（html-to-image renderer）
COPY backend/package*.json ./backend/
RUN cd backend && npm install

# アプリケーションコードをコピー
COPY . .

# ビルド引数を受け取る（Railwayの環境変数をビルド時に注入）
ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

# Next.jsをビルド
RUN npm run build

# 出力・アップロードディレクトリを作成
RUN mkdir -p /app/outputs /app/uploads

# ポート
ENV PORT=3000
EXPOSE 3000

# 起動スクリプト
COPY start.sh ./
RUN chmod +x start.sh

CMD ["./start.sh"]

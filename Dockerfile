# VoiceSlide AI - Railway Dockerfile
# シンプルな構成：Next.js + Python Backend

FROM python:3.11-slim

# 必要なシステムパッケージをインストール
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Node.jsをインストール
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python依存関係をインストール
COPY backend/requirements.txt ./backend/
RUN pip install --no-cache-dir -r backend/requirements.txt

# Node.js依存関係をインストール
COPY package*.json ./
RUN npm ci

# アプリケーションコードをコピー
COPY . .

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

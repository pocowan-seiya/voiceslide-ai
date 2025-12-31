#!/bin/bash
# VoiceSlide AI - 起動スクリプト

set -e

echo "🚀 Starting VoiceSlide AI..."

# Railwayは$PORTを提供
FRONTEND_PORT=${PORT:-3000}
BACKEND_PORT=8001

echo "Frontend will run on port: $FRONTEND_PORT"
echo "Backend will run on port: $BACKEND_PORT"

# ディレクトリ作成
mkdir -p /app/outputs /app/uploads

# バックエンドを起動（ポート8001）
echo "📡 Starting backend on port $BACKEND_PORT..."
cd /app/backend
PORT=$BACKEND_PORT python main.py &
BACKEND_PID=$!

# バックエンドの起動を待機
sleep 5

# フロントエンドを起動（npm経由）
echo "🌐 Starting frontend on port $FRONTEND_PORT..."
cd /app
PORT=$FRONTEND_PORT npm start &
FRONTEND_PID=$!

echo "✅ VoiceSlide AI is running!"

# シグナルハンドリング
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null" SIGTERM SIGINT EXIT

# 両方のプロセスを待機
wait

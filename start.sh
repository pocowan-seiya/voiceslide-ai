#!/bin/bash
# VoiceSlide AI - 起動スクリプト

set -e

echo "🚀 Starting VoiceSlide AI..."

# Railwayの$PORTを保存（フロントエンド用）
RAILWAY_PORT=${PORT:-3000}

echo "Railway PORT: $RAILWAY_PORT"

# ディレクトリ作成
mkdir -p /app/outputs /app/uploads

# バックエンドを起動（サブシェルで環境変数を隔離）
echo "📡 Starting backend on port 8001..."
(
  cd /app/backend
  export PORT=8001
  python main.py
) &
BACKEND_PID=$!

# バックエンドの起動を待機
sleep 5

# フロントエンドを起動（元のPORTで）
echo "🌐 Starting frontend on port $RAILWAY_PORT..."
(
  cd /app
  export PORT=$RAILWAY_PORT
  npm start
) &
FRONTEND_PID=$!

echo "✅ VoiceSlide AI is running!"
echo "   Frontend: http://localhost:$RAILWAY_PORT"
echo "   Backend:  http://localhost:8001"

# シグナルハンドリング
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null" SIGTERM SIGINT EXIT

# 両方のプロセスを待機
wait

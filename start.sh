#!/bin/bash
# VoiceSlide AI - 起動スクリプト

set -e

echo "🚀 Starting VoiceSlide AI..."

# 環境変数
export PORT=${PORT:-3000}
export BACKEND_PORT=8000

# ディレクトリ作成
mkdir -p /app/outputs /app/uploads

# バックエンドを起動（バックグラウンド）
echo "📡 Starting backend on port $BACKEND_PORT..."
cd /app/backend
python main.py &
BACKEND_PID=$!

# バックエンドの起動を待機
sleep 3

# フロントエンドを起動
echo "🌐 Starting frontend on port $PORT..."
cd /app
npm start &
FRONTEND_PID=$!

echo "✅ VoiceSlide AI is running!"
echo "   Frontend: http://localhost:$PORT"
echo "   Backend:  http://localhost:$BACKEND_PORT"

# シグナルハンドリング
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null" SIGTERM SIGINT EXIT

# 両方のプロセスを待機
wait

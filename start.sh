#!/bin/bash
# VoiceSlide AI - Railway起動スクリプト

set -e

echo "🚀 Starting VoiceSlide AI..."

# Railwayの$PORT（フロントエンド用）
FRONTEND_PORT=${PORT:-3000}
echo "Frontend PORT: $FRONTEND_PORT"

# ディレクトリ作成
mkdir -p /app/outputs /app/uploads

# バックエンドを起動（BACKEND_PORT環境変数を使用）
echo "📡 Starting backend on port 8001..."
cd /app/backend
export BACKEND_PORT=8001
python main.py &
BACKEND_PID=$!

# バックエンドの起動を待機
sleep 5

# Next.jsを起動（node_modules内のnextを直接実行）
echo "🌐 Starting frontend on port $FRONTEND_PORT..."
cd /app
./node_modules/.bin/next start -p $FRONTEND_PORT &
FRONTEND_PID=$!

echo "✅ VoiceSlide AI is running!"
echo "   Frontend: http://localhost:$FRONTEND_PORT"
echo "   Backend:  http://localhost:8001"

# シグナルハンドリング
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null" SIGTERM SIGINT EXIT

# 両方のプロセスを待機
wait

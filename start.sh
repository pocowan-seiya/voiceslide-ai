#!/bin/bash
# VoiceSlide AI - 起動スクリプト

set -e

echo "🚀 Starting VoiceSlide AI..."

# Railwayは$PORTを提供（通常3000）
# フロントエンドはRailwayの$PORTを使用
# バックエンドは内部ポート8001を使用（競合回避）
FRONTEND_PORT=${PORT:-3000}
BACKEND_PORT=8001

# ディレクトリ作成
mkdir -p /app/outputs /app/uploads

# バックエンドを起動（バックグラウンド、ポート8001）
echo "📡 Starting backend on port $BACKEND_PORT..."
cd /app/backend
PORT=$BACKEND_PORT python main.py &
BACKEND_PID=$!

# バックエンドの起動を待機
sleep 5

# フロントエンドを起動
echo "🌐 Starting frontend on port $FRONTEND_PORT..."
cd /app
export PORT=$FRONTEND_PORT
next start -p $FRONTEND_PORT &
FRONTEND_PID=$!

echo "✅ VoiceSlide AI is running!"
echo "   Frontend: http://localhost:$FRONTEND_PORT"
echo "   Backend:  http://localhost:$BACKEND_PORT"

# シグナルハンドリング
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null" SIGTERM SIGINT EXIT

# 両方のプロセスを待機
wait

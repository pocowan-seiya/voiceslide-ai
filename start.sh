#!/bin/bash
# VoiceSlide AI - 起動スクリプト

# 環境変数のデフォルト値
export PORT=${PORT:-3000}
export BACKEND_PORT=${BACKEND_PORT:-8000}

# バックエンドを起動（バックグラウンド）
cd /app/backend
python main.py &
BACKEND_PID=$!

# フロントエンドを起動
cd /app
npm start &
FRONTEND_PID=$!

# シグナルハンドリング
trap "kill $BACKEND_PID $FRONTEND_PID" SIGTERM SIGINT

# 両方のプロセスを待機
wait

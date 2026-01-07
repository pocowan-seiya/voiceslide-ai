#!/bin/bash
# VoiceSlide AI - ローカル開発用起動スクリプト
# Mac/Linux対応

set -e

echo "🚀 VoiceSlide AI - ローカル起動"
echo "================================"

# 作業ディレクトリ
cd "$(dirname "$0")"

# 出力ディレクトリ作成
mkdir -p outputs uploads

# 環境変数設定
export OUTPUT_DIR="$(pwd)/outputs"
export UPLOAD_DIR="$(pwd)/uploads"
export DEBUG=true

# バックエンドを起動
echo ""
echo "📡 バックエンドを起動中 (http://localhost:8000)..."
cd backend
python main.py &
BACKEND_PID=$!
cd ..

# バックエンドの起動を待機
sleep 3

# フロントエンドを起動（開発モード）
echo ""
echo "🌐 フロントエンドを起動中 (http://localhost:3000)..."
npm run dev &
FRONTEND_PID=$!

echo ""
echo "✅ VoiceSlide AI が起動しました！"
echo ""
echo "   🌐 フロントエンド: http://localhost:3000"
echo "   📡 バックエンド:   http://localhost:8000"
echo ""
echo "   停止するには Ctrl+C を押してください"
echo ""

# シグナルハンドリング
cleanup() {
    echo ""
    echo "🛑 サーバーを停止中..."
    kill $BACKEND_PID $FRONTEND_PID 2>/dev/null
    echo "✅ 停止完了"
    exit 0
}
trap cleanup SIGTERM SIGINT

# 両方のプロセスを待機
wait

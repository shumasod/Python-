#!/bin/bash

echo "========================================="
echo "JRA競馬予測システム - フロントエンド起動"
echo "========================================="
echo ""

# プロジェクトルートに移動
cd "$(dirname "$0")/frontend"

# 依存関係チェック
if [ ! -d "node_modules" ]; then
    echo "📦 依存関係をインストール中..."
    npm install
fi

# サーバー起動
echo ""
echo "🚀 React開発サーバーを起動中..."
echo ""
npm run dev

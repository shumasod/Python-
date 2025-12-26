# JRA競馬予測システム - フロントエンド

React + Vite で構築された競馬予測システムのフロントエンドアプリケーション

## 機能

- 馬の情報入力フォーム
- AI機械学習による着順予測
- リアルタイムでのバックエンドAPI連携
- レスポンシブデザイン（モバイル対応）

## 技術スタック

- **React 18**: UIライブラリ
- **Vite**: 高速ビルドツール
- **Tailwind CSS**: ユーティリティファーストCSS
- **Axios**: HTTP通信ライブラリ

## セットアップ

### 前提条件

- Node.js 18以上
- npm または yarn

### インストール

```bash
# 依存関係のインストール
npm install

# または
yarn install
```

### 開発サーバーの起動

```bash
npm run dev

# または
yarn dev
```

開発サーバーは `http://localhost:3000` で起動します。

### 環境変数の設定

`.env.example` をコピーして `.env` ファイルを作成：

```bash
cp .env.example .env
```

必要に応じて環境変数を編集：

```env
VITE_API_URL=http://localhost:5000
```

## ビルド

本番用ビルドを作成：

```bash
npm run build

# または
yarn build
```

ビルド成果物は `dist/` ディレクトリに出力されます。

## プレビュー

ビルドしたアプリケーションをプレビュー：

```bash
npm run preview

# または
yarn preview
```

## プロジェクト構成

```
frontend/
├── src/
│   ├── api/              # API通信モジュール
│   │   └── keiba.js      # 競馬予測API
│   ├── components/       # Reactコンポーネント
│   │   ├── Header.jsx
│   │   ├── HealthStatus.jsx
│   │   ├── PredictionForm.jsx
│   │   └── PredictionResult.jsx
│   ├── App.jsx           # メインアプリケーション
│   ├── main.jsx          # エントリーポイント
│   └── index.css         # グローバルスタイル
├── index.html
├── package.json
├── vite.config.js
└── tailwind.config.js
```

## 主要コンポーネント

### PredictionForm

馬の情報を入力するフォームコンポーネント。バリデーション機能付き。

### PredictionResult

予測結果を表示するコンポーネント。着順と信頼度を視覚的に表示。

### HealthStatus

バックエンドサーバーのヘルスステータスを表示。

## バックエンド連携

このフロントエンドは、以下のバックエンドAPIエンドポイントと連携します：

- `POST /predict` - 着順予測
- `GET /health` - ヘルスチェック
- `GET /api/v1/info` - API情報取得

バックエンドサーバーは別途起動する必要があります。

## ライセンス

MIT

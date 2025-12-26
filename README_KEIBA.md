# JRA競馬予測システム

機械学習を活用したJRA競馬の着順予測システム。PythonのFlaskバックエンドとReactフロントエンドで構成されています。

## 概要

このシステムは、馬の基本情報（枠番、馬番、斤量、人気、単勝オッズ、馬体重など）から、RandomForestモデルを使用して着順を予測します。

## システム構成

```
.
├── Keiba/                  # バックエンド (Python/Flask)
│   ├── models.py           # 機械学習モデル
│   ├── app.py              # Flaskアプリケーション
│   ├── main.py             # エントリーポイント
│   ├── services.py         # 予測サービス
│   ├── schemas.py          # データスキーマ
│   ├── exceptions.py       # カスタム例外
│   └── config.py           # Flaskアプリ設定
└── frontend/               # フロントエンド (React/Vite)
    ├── src/
    │   ├── components/     # Reactコンポーネント
    │   ├── api/            # API通信
    │   ├── App.jsx
    │   └── main.jsx
    ├── package.json
    └── vite.config.js
```

## 主要機能

### バックエンド

- **機械学習モデル**: RandomForestRegressorによる着順予測
- **データ前処理**: One-hotエンコーディング、スケーリング
- **REST API**: Flask APIエンドポイント
- **バリデーション**: Pydanticによる入力データ検証
- **ロギング**: 詳細なログ記録
- **エラーハンドリング**: 包括的な例外処理

### フロントエンド

- **レスポンシブUI**: Tailwind CSSによるモダンなデザイン
- **リアルタイム予測**: Axiosを使った非同期API通信
- **バリデーション**: フォーム入力の検証
- **視覚的フィードバック**: 予測結果と信頼度の視覚化
- **ヘルスチェック**: バックエンドステータスの監視

## セットアップ

### 前提条件

- **バックエンド**:
  - Python 3.8以上
  - pip

- **フロントエンド**:
  - Node.js 18以上
  - npm または yarn

### バックエンドのセットアップ

1. 依存関係のインストール:

```bash
cd Keiba
pip install -r requirements.txt
```

2. 環境変数の設定（オプション）:

```bash
export FLASK_HOST=0.0.0.0
export FLASK_PORT=5000
export FLASK_DEBUG=true
export MODEL_PATH=./models/jra_model.pkl
```

3. サーバーの起動:

```bash
python -m Keiba.main --port 5000 --debug
```

または、app.pyを直接実行:

```bash
python Keiba/app.py
```

### フロントエンドのセットアップ

1. 依存関係のインストール:

```bash
cd frontend
npm install
```

2. 環境変数の設定:

```bash
cp .env.example .env
# .env ファイルを編集して VITE_API_URL を設定
```

3. 開発サーバーの起動:

```bash
npm run dev
```

フロントエンドは `http://localhost:3000` で起動します。

## 使い方

1. **バックエンドとフロントエンドの両方を起動**

2. **ブラウザで `http://localhost:3000` にアクセス**

3. **馬の情報を入力**:
   - 枠番 (1-8)
   - 馬番 (1-18)
   - 斤量 (40-65kg)
   - 人気順位 (1-18)
   - 単勝オッズ
   - 馬体重 (300-600kg)
   - 馬体重増減 (-50 〜 +50kg)
   - 性齢 (牡/牝/セ + 年齢)
   - 騎手

4. **「予測を実行」ボタンをクリック**

5. **予測結果を確認**:
   - 予測着順
   - 予測の信頼度

## API エンドポイント

### POST /predict

馬のデータから着順を予測

**リクエスト例**:

```json
{
  "枠番": 3,
  "馬番": 5,
  "斤量": 55.0,
  "人気": 2,
  "単勝": 3.5,
  "馬体重": 480,
  "増減": 2,
  "性齢": "牡4",
  "騎手": "川田将雅"
}
```

**レスポンス例**:

```json
{
  "prediction": 3,
  "confidence": 0.85
}
```

### GET /health

サーバーのヘルスチェック

**レスポンス例**:

```json
{
  "status": "healthy",
  "model_loaded": true,
  "version": "1.0.0"
}
```

### GET /api/v1/info

API情報の取得

## 技術スタック

### バックエンド

- **Flask**: Webフレームワーク
- **Scikit-learn**: 機械学習ライブラリ
- **Pandas**: データ処理
- **NumPy**: 数値計算
- **Pydantic**: データバリデーション
- **Joblib**: モデルの永続化

### フロントエンド

- **React 18**: UIライブラリ
- **Vite**: ビルドツール
- **Tailwind CSS**: CSSフレームワーク
- **Axios**: HTTP通信

## 開発

### バックエンドのテスト

```bash
cd Keiba
python -m pytest tests/
```

### フロントエンドのビルド

```bash
cd frontend
npm run build
```

ビルド成果物は `frontend/dist/` に出力されます。

## 本番環境へのデプロイ

### バックエンド

```bash
# Gunicornを使用した本番環境デプロイ
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 'Keiba.app:create_app()'
```

### フロントエンド

```bash
# ビルド
npm run build

# 静的ファイルサーバーで配信
npm install -g serve
serve -s dist -l 3000
```

## 注意事項

- この予測システムは機械学習モデルによるものであり、実際の競馬の結果を保証するものではありません
- モデルの精度は学習データの質と量に依存します
- 実際の投票には慎重な判断が必要です

## ライセンス

MIT

## 貢献

プルリクエストを歓迎します。大きな変更の場合は、まずissueを開いて変更内容を議論してください。

## サポート

問題が発生した場合は、GitHubのissueを作成してください。

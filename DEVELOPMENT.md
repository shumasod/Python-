# 開発サーバー起動ガイド

## クイックスタート

### ターミナル1: バックエンド起動

```bash
cd /home/user/Python-
./start-backend.sh
```

または手動で：

```bash
cd /home/user/Python-
python -m Keiba.app
```

**起動確認:**
- サーバーが http://localhost:5000 で起動
- ブラウザまたはcurlで確認:
  ```bash
  curl http://localhost:5000/health
  ```

### ターミナル2: フロントエンド起動

```bash
cd /home/user/Python-
./start-frontend.sh
```

または手動で：

```bash
cd /home/user/Python-/frontend
npm install  # 初回のみ
npm run dev
```

**起動確認:**
- サーバーが http://localhost:3000 で起動
- ブラウザでアクセス

## アクセスURL

| サービス | URL | 説明 |
|---------|-----|------|
| フロントエンド | http://localhost:3000 | React UI |
| バックエンド | http://localhost:5000 | Flask API |
| ヘルスチェック | http://localhost:5000/health | サーバー状態確認 |
| API情報 | http://localhost:5000/api/v1/info | API仕様 |

## 初回セットアップ

### バックエンド

```bash
# Python依存関係のインストール
cd /home/user/Python-
pip install -r Keiba/requirements.txt
```

**必要なパッケージ:**
- Flask 3.0.0
- scikit-learn 1.3.2
- pandas 2.1.4
- numpy 1.26.2
- pydantic 2.5.3

### フロントエンド

```bash
# Node.js依存関係のインストール
cd /home/user/Python-/frontend
npm install
```

**必要なパッケージ:**
- React 18.2.0
- Vite 5.0.8
- Tailwind CSS 3.4.0
- Axios 1.6.0

## トラブルシューティング

### バックエンドが起動しない

**エラー: ModuleNotFoundError**
```bash
# 依存関係を再インストール
pip install -r Keiba/requirements.txt
```

**エラー: ImportError**
```bash
# __init__.pyが存在するか確認
ls -la Keiba/__init__.py

# なければ作成
touch Keiba/__init__.py
```

**ポートが使用中**
```bash
# ポート5000を使用しているプロセスを確認
lsof -i :5000

# プロセスを終了
kill -9 <PID>

# または別のポートで起動
python -m Keiba.main --port 5001
```

### フロントエンドが起動しない

**エラー: npm コマンドが見つからない**
```bash
# Node.jsがインストールされているか確認
node --version
npm --version

# インストールされていない場合はインストール
# (環境に応じた方法でインストール)
```

**ポートが使用中**
```bash
# ポート3000を使用しているプロセスを確認
lsof -i :3000

# プロセスを終了
kill -9 <PID>
```

**依存関係のエラー**
```bash
# node_modulesを削除して再インストール
rm -rf node_modules package-lock.json
npm install
```

### APIに接続できない

**CORS エラー**
- バックエンドにflask-corsがインストールされているか確認
- app.pyでCORSが有効になっているか確認

**接続タイムアウト**
- バックエンドが起動しているか確認:
  ```bash
  curl http://localhost:5000/health
  ```
- フロントエンドの.envファイルでAPI URLが正しいか確認

## 開発のヒント

### ホットリロード

- **バックエンド**: デバッグモードで自動リロード有効
  ```bash
  python -m Keiba.main --debug
  ```

- **フロントエンド**: Viteが自動でホットリロード

### ログの確認

**バックエンド:**
- コンソール出力を確認
- `logs/` ディレクトリにログファイルが作成される

**フロントエンド:**
- ブラウザの開発者ツール（F12）→ Consoleタブ
- ネットワークタブでAPI通信を確認

### APIのテスト

```bash
# 予測APIのテスト
curl -X POST http://localhost:5000/predict \
  -H "Content-Type: application/json" \
  -d '{
    "枠番": 3,
    "馬番": 5,
    "斤量": 55.0,
    "人気": 2,
    "単勝": 3.5,
    "馬体重": 480,
    "増減": 2,
    "性齢": "牡4",
    "騎手": "川田将雅"
  }'
```

## 環境変数

### バックエンド

```bash
export FLASK_HOST=0.0.0.0
export FLASK_PORT=5000
export FLASK_DEBUG=true
export MODEL_PATH=./models/jra_model.pkl
export LOG_LEVEL=INFO
```

### フロントエンド

`.env` ファイルを作成:
```env
VITE_API_URL=http://localhost:5000
```

## 停止方法

### バックエンド
- `Ctrl + C` でサーバーを停止

### フロントエンド
- `Ctrl + C` でサーバーを停止

## さらなる情報

- **全体ドキュメント**: README_KEIBA.md
- **フロントエンド詳細**: frontend/README.md
- **バックエンドAPI**: Keiba/README.md（作成予定）

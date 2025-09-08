# requirements.txt

Flask==2.3.3
numpy==1.24.3
pandas==2.0.3
scikit-learn==1.3.0
requests==2.31.0

-----

# Dockerfile

FROM python:3.9-slim

WORKDIR /app

# 依存関係をインストール

COPY requirements.txt .
RUN pip install –no-cache-dir -r requirements.txt

# アプリケーションをコピー

COPY . .

# ポートを公開

EXPOSE 5000

# 本番環境用の設定

ENV FLASK_ENV=production

# アプリケーション実行

CMD [“python”, “congestion_api.py”]

-----

# docker-compose.yml

version: ‘3.8’

services:
congestion-api:
build: .
ports:
- “5000:5000”
environment:
- FLASK_ENV=production
volumes:
- ./logs:/app/logs
restart: unless-stopped

-----

# .env.example

# APIサーバー設定

API_HOST=0.0.0.0
API_PORT=5000
DEBUG=false

# モデル設定

MODEL_RETRAIN_INTERVAL=24  # hours
DATA_CACHE_SIZE=1000

# ログ設定

LOG_LEVEL=INFO
LOG_FILE=logs/api.log

-----

# 実行方法 (README.md)

## 混雑予測API

機械学習を使用した混雑予測システムのREST APIです。

### 機能

- 時間、曜日、天気、気温などの要因を考慮した混雑度予測
- 単一時点予測と複数時間の予測をサポート
- RESTful APIによる簡単なインテグレーション
- リアルタイム予測と信頼度計算

### インストールと実行

#### 1. 基本実行

```bash
# 依存関係インストール
pip install -r requirements.txt

# APIサーバー起動
python congestion_api.py
```

#### 2. Docker実行

```bash
# Dockerイメージをビルドして実行
docker-compose up --build
```

### API仕様

#### エンドポイント

1. **ヘルスチェック**
- `GET /`
- サーバーの状態確認
1. **単一予測**
- `POST /predict`
- 指定した時刻の混雑度予測
1. **バッチ予測**
- `POST /predict/batch`
- 複数時間の連続予測
1. **モデル情報**
- `GET /model/info`
- モデルの詳細情報

### リクエスト例

```bash
# 単一予測
curl -X POST http://localhost:5000/predict \
  -H "Content-Type: application/json" \
  -d '{
    "datetime": "2024-03-11T08:00:00",
    "temperature": 20.0,
    "weather_code": 0,
    "is_holiday": false
  }'

# 24時間予測
curl -X POST http://localhost:5000/predict/batch \
  -H "Content-Type: application/json" \
  -d '{
    "start_datetime": "2024-03-11T00:00:00",
    "hours": 24,
    "temperature": 22.0,
    "weather_code": 1
  }'
```

### 天気コード

- 0: 晴れ
- 1: 曇り
- 2: 雨
- 3: 雪

### レスポンス形式

```json
{
  "success": true,
  "prediction": {
    "congestion_level": 75.3,
    "confidence": 88.2,
    "status": "やや混雑",
    "features_used": {
      "hour": 8,
      "day_of_week": 0,
      "is_weekend": 0,
      "temperature": 20.0,
      "weather_code": 0
    }
  }
}
```

### クライアント使用例

```python
# クライアントテスト実行
python api_client_example.py
```

### カスタマイズ

実際の運用では以下をカスタマイズしてください：

- `generate_sample_data()` を実際のデータソースに置き換え
- 特徴量の追加（イベント情報、施設固有データなど）
- モデルの改善（深層学習、時系列モデルなど）
- データベース連携の追加
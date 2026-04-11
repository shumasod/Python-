# 競艇予想AI システム

LightGBM + FastAPI による競艇レース予測システム。

## ディレクトリ構成

```
project/
├── app/
│   ├── main.py              # FastAPI エントリーポイント
│   ├── api/predict.py       # POST /api/v1/predict エンドポイント
│   ├── model/
│   │   ├── features.py      # 特徴量生成・前処理
│   │   ├── train.py         # LightGBM 学習
│   │   └── predict.py       # 推論・三連単・ケリー基準
│   ├── data/loader.py       # データ読み込み
│   └── utils/logger.py      # ロータリーファイルロガー
├── scripts/train_model.py   # 学習 CLI
├── scraper.py               # 競艇データスクレイパー
├── simulator.py             # 回収率シミュレーター
├── terraform/               # AWS インフラ (Terraform)
│   ├── main.tf / variables.tf / outputs.tf
│   └── modules/ {iam, ecr, s3, rds, cloudwatch, ecs}
├── Dockerfile
└── requirements.txt
```

## クイックスタート

### 1. セットアップ
```bash
cd project
pip install -r requirements.txt
```

### 2. モデル学習
```bash
# サンプルデータで学習（実データなしでも動作確認可）
python scripts/train_model.py --use-sample --n-races 2000

# 実データ（CSV）で学習
python scripts/train_model.py --data-path data/training.csv
```

### 3. APIサーバー起動
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 4. 予測リクエスト例
```bash
curl -X POST http://localhost:8000/api/v1/predict \
  -H "Content-Type: application/json" \
  -d '{
    "race_id": "race_001",
    "race": {
      "boats": [
        {"boat_number":1,"racer_rank":"A1","win_rate":35.0,"motor_score":60.0,
         "course_win_rate":42.0,"start_timing":0.15,"motor_2rate":48.0,
         "boat_2rate":45.0,"recent_3_avg":2.1},
        {"boat_number":2,"racer_rank":"A2","win_rate":22.0,"motor_score":48.0,
         "course_win_rate":28.0,"start_timing":0.18,"motor_2rate":35.0,
         "boat_2rate":32.0,"recent_3_avg":3.2},
        {"boat_number":3,"racer_rank":"B1","win_rate":18.0,"motor_score":44.0,
         "course_win_rate":20.0,"start_timing":0.20,"motor_2rate":28.0,
         "boat_2rate":25.0,"recent_3_avg":3.8},
        {"boat_number":4,"racer_rank":"B1","win_rate":15.0,"motor_score":42.0,
         "course_win_rate":15.0,"start_timing":0.22,"motor_2rate":24.0,
         "boat_2rate":22.0,"recent_3_avg":4.0},
        {"boat_number":5,"racer_rank":"B2","win_rate":10.0,"motor_score":38.0,
         "course_win_rate":10.0,"start_timing":0.25,"motor_2rate":18.0,
         "boat_2rate":16.0,"recent_3_avg":4.5},
        {"boat_number":6,"racer_rank":"B2","win_rate":8.0,"motor_score":35.0,
         "course_win_rate":8.0,"start_timing":0.28,"motor_2rate":14.0,
         "boat_2rate":12.0,"recent_3_avg":5.0}
      ],
      "weather": {"condition":"晴","wind_speed":2.0,"water_temp":22.0}
    }
  }'
```

### 5. Docker で起動
```bash
cd project
docker build -t boat-race-ai .
docker run -p 8000:8000 -v $(pwd)/models:/app/models boat-race-ai
```

### 6. スクレイパー実行
```bash
# ドライランで動作確認
python scraper.py --dry-run

# 過去30日のレース結果を収集
python scraper.py --target results

# 選手情報収集
python scraper.py --target racers
```

### 7. 回収率シミュレーション
```bash
# デフォルト（200レース・期待値閾値1.0）
python simulator.py

# 厳選モード（期待値1.2以上・ハーフケリー）
python simulator.py --n-races 500 --ev-threshold 1.2 --kelly-frac 0.5

# グラフ保存
python simulator.py --save-plot output/simulation.png
```

## AWS デプロイ（Terraform）

```bash
cd project/terraform
terraform init
terraform plan -var="db_password=YOUR_SECURE_PASSWORD"
terraform apply -var="db_password=YOUR_SECURE_PASSWORD"
```

## コスト最適化ポイント

| リソース | コスト対策 |
|---------|-----------|
| ECS Fargate | CPU/メモリを最小構成から開始・Auto Scaling で増減 |
| RDS | db.t3.micro + gp3ストレージ・開発環境はMulti-AZ無効 |
| NAT Gateway | 開発環境では削除（代わりにVPCエンドポイント） |
| S3 | Intelligent Tiering → Glacier への自動移行 |
| ECR | ライフサイクルポリシーで古いイメージを自動削除 |
| CloudWatch Logs | 保持期間を30日に制限 |

## セキュリティ考慮事項

- DBパスワードは Secrets Manager / Parameter Store で管理
- S3 はパブリックアクセスを完全ブロック + HTTPS のみ許可
- ECS タスクは最小権限 IAM ロール
- RDS はプライベートサブネット配置・外部からアクセス不可
- Docker コンテナは非 root ユーザーで実行

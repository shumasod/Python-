# 競艇予想AI システム

![Tests](https://img.shields.io/badge/tests-144%20passed-brightgreen)
![Python](https://img.shields.io/badge/python-3.11-blue)
![License](https://img.shields.io/badge/license-MIT-green)

---

## 概要

LightGBM + FastAPI で構築した競艇レース予測システムです。6艇の特徴量をもとに勝率・三連単確率を算出し、ケリー基準による最適ベット額を提案します。モデルバージョン管理・アンサンブル・ドリフト検出・A/Bテスト・シャドウモードを備え、AWS（ECS Fargate + RDS）および Kubernetes への本番デプロイに対応しています。

---

## 特徴

- **高精度予測**: LightGBM マルチクラス分類（6クラス）＋ StratifiedKFold CV による安定した推定
- **多彩な賭け戦略**: 勝率・三連単確率・ケリー基準ベット額を一括出力
- **バッチ推論**: 1リクエストで最大 20 レースを並列予測
- **モデルバージョン管理**: ModelRegistry によるバージョン管理・ロールバック
- **アンサンブル予測**: CV ログ損失による重み付き平均アンサンブル
- **ドリフト検出**: PSI + KL ダイバージェンスによるデータ分布変化の自動検知
- **A/B テスト**: MD5 決定論的ルーティング＋ z 検定による統計的有意差検証
- **シャドウモード**: 本番に影響なく新モデルをサイレント評価
- **Redis キャッシュ**: TTL 付きキャッシュで高速レスポンス
- **レート制限・認証**: slowapi によるレート制限 + SHA-256 API キー認証
- **完全な監視基盤**: Prometheus / Grafana / CloudWatch アラーム対応
- **フルマネージド CI/CD**: GitHub Actions → ECR → ECS Fargate 自動デプロイ
- **Kubernetes 対応**: HPA・Ingress・kustomize オーバーレイ（dev/production）
- **Airflow パイプライン**: スクレイピング → バリデーション → ドリフト検査 → 再学習 の自動化

---

## ディレクトリ構成

```
project/
├── app/
│   ├── main.py                        # FastAPI エントリーポイント
│   ├── api/
│   │   ├── predict.py                 # 予測エンドポイント
│   │   ├── feedback.py                # 実績記録エンドポイント
│   │   ├── health.py                  # ヘルスチェック
│   │   ├── metrics.py                 # Prometheus メトリクス
│   │   ├── auth.py                    # API キー認証
│   │   └── ratelimit.py               # レート制限
│   ├── model/
│   │   ├── train.py                   # LightGBM 学習
│   │   ├── predict.py                 # 推論・三連単・ケリー基準
│   │   ├── features.py                # 特徴量生成・前処理
│   │   ├── ensemble.py                # アンサンブル予測
│   │   ├── drift.py                   # ドリフト検出 (PSI/KL)
│   │   ├── versioning.py              # ModelRegistry
│   │   ├── ab_test.py                 # A/B テスト
│   │   └── shadow.py                  # シャドウモード
│   ├── data/loader.py                 # データ読み込み
│   ├── cache.py                       # Redis キャッシュ
│   ├── db.py                          # PostgreSQL 接続
│   ├── cli.py                         # CLI エントリーポイント
│   └── utils/
│       ├── logger.py                  # ロータリーファイルロガー
│       └── notification.py            # アラート通知
├── scripts/
│   ├── train_model.py
│   ├── analyze_model.py
│   ├── convert_data.py
│   ├── fetch_odds.py
│   └── promote_model.py
├── tests/                             # 144 テスト
├── dags/boat_race_pipeline.py         # Airflow DAG
├── terraform/                         # AWS インフラ
│   └── modules/ {iam, ecr, s3, rds, cloudwatch, ecs}
├── k8s/                               # Kubernetes マニフェスト
│   └── overlays/ {dev, production}
├── docker/
├── Dockerfile
├── docker-compose.yml
├── docker-compose.monitoring.yml
├── docker-compose.airflow.yml
├── Makefile
├── pyproject.toml
├── requirements.txt
├── scraper.py
├── simulator.py
├── backtester.py
└── .github/workflows/boat-race-ci.yml
```

---

## クイックスタート

### 1. インストール

```bash
git clone <repository-url>
cd project
pip install -r requirements.txt
```

### 2. 環境変数の設定

```bash
cp .env.example .env
# .env を編集して各値を設定（詳細は「環境変数リファレンス」参照）
```

### 3. モデル学習

```bash
# サンプルデータで学習（実データなしで動作確認可）
make train

# または直接実行
python -m app.cli model train --use-sample --n-races 2000

# 実データ（CSV）で学習
python -m app.cli model train --data-path data/training.csv
```

### 4. API サーバー起動

```bash
# ローカル起動
make serve

# Docker Compose で起動（Redis + PostgreSQL + API + Trainer）
make docker-up
```

### 5. 予測リクエスト例

```bash
curl -X POST http://localhost:8000/api/v1/predict \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your_api_key" \
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

---

## API リファレンス

| メソッド | パス | 説明 |
|---------|------|------|
| `POST` | `/api/v1/predict` | 単一レースの予測（勝率・三連単・ケリー基準ベット） |
| `POST` | `/api/v1/predict/batch` | バッチ予測（最大 20 レース） |
| `POST` | `/api/v1/result/{race_id}` | 実際のレース結果を記録 |
| `GET`  | `/api/v1/result/{race_id}` | 記録済み結果の取得 |
| `GET`  | `/api/v1/result/summary` | 的中率サマリーの取得 |
| `GET`  | `/api/v1/stats` | 予測統計情報の取得 |
| `DELETE` | `/api/v1/cache/{race_id}` | 指定レースのキャッシュ削除 |
| `GET`  | `/health` | 基本ヘルスチェック |
| `GET`  | `/health/detail` | 詳細ヘルスチェック（DB・Redis・モデル状態） |
| `GET`  | `/metrics` | Prometheus メトリクス |

### バッチ予測リクエスト例

```bash
curl -X POST http://localhost:8000/api/v1/predict/batch \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your_api_key" \
  -d '{"races": [{"race_id": "race_001", "race": {...}}, {"race_id": "race_002", "race": {...}}]}'
```

### 結果記録例

```bash
curl -X POST http://localhost:8000/api/v1/result/race_001 \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your_api_key" \
  -d '{"winner": 1, "trifecta": [1, 3, 2]}'
```

---

## モデル管理

### バージョン管理

```bash
# 利用可能なモデルバージョン一覧
make versions

# モデルのプロモーション（staging → production）
make promote

# 古いモデルのクリーンアップ
make cleanup-models

# CLI 直接操作
python -m app.cli model list
python -m app.cli model promote --version v1.2.0
python -m app.cli model rollback --version v1.1.0
```

### アンサンブル予測

アンサンブルモードでは複数のモデルを CV ログ損失で重み付けして予測します。

```bash
# アンサンブルモードで学習
python -m app.cli model train --ensemble --n-folds 5

# 重み付きアンサンブルで推論（weighted / average を選択可）
python -m app.cli model predict --ensemble-mode weighted
```

### A/B テスト

MD5 ハッシュによる決定論的ルーティングで、同一リクエストは常に同じモデルに割り当てられます。

```bash
# A/B テストの開始
python -m app.cli model ab-start \
  --model-a v1.1.0 --model-b v1.2.0 --traffic-b 0.2

# 統計的有意差の確認（z 検定）
python -m app.cli model ab-status

# A/B テストの終了
python -m app.cli model ab-stop --winner b
```

### シャドウモード

本番モデルへの影響なく、新モデルをサイレント評価できます。

```bash
# シャドウモードの有効化
python -m app.cli shadow start --shadow-model v1.3.0-rc

# シャドウ評価結果の確認（KL ダイバージェンス）
make shadow-stats

# シャドウモードの無効化
python -m app.cli shadow stop
```

### バックテスト・シミュレーション

```bash
# 回収率シミュレーション
make simulate

# バックテスト実行
make backtest

# 厳選モード（期待値 1.2 以上・ハーフケリー）
python simulator.py --n-races 500 --ev-threshold 1.2 --kelly-frac 0.5
```

---

## 監視

### Prometheus / Grafana

```bash
# 監視スタックの起動
docker compose -f docker-compose.monitoring.yml up -d

# アクセス先
# Grafana:    http://localhost:3000  (admin / admin)
# Prometheus: http://localhost:9090
```

収集されるメトリクスの例:

| メトリクス名 | 説明 |
|------------|------|
| `boat_race_predictions_total` | 総予測リクエスト数 |
| `boat_race_prediction_latency_seconds` | 予測レイテンシ（ヒストグラム） |
| `boat_race_model_version` | 稼働中モデルバージョン |
| `boat_race_cache_hit_total` | キャッシュヒット数 |
| `boat_race_drift_psi` | PSI ドリフトスコア |

### ドリフト検出

PSI（Population Stability Index）と KL ダイバージェンスを用いて特徴量の分布変化を自動検知します。

```bash
# ドリフト検査の実行
make drift

# 閾値: PSI > 0.2 → alert、0.1〜0.2 → warn、< 0.1 → stable
python -m app.cli data drift-check --reference-data data/baseline.csv
```

### CloudWatch アラーム

Terraform で以下のアラームが自動設定されます:

| アラーム | 条件 |
|---------|------|
| API エラー率 | 5xx > 5% / 5 分 |
| 予測レイテンシ | p99 > 2 秒 |
| ECS CPU 使用率 | > 80% / 10 分 |
| RDS 接続数 | > 90% of max |
| Redis メモリ | > 85% |

---

## インフラ構成

### Terraform（AWS）

```bash
cd terraform
terraform init

# プラン確認
terraform plan -var="db_password=YOUR_SECURE_PASSWORD"

# デプロイ
terraform apply -var="db_password=YOUR_SECURE_PASSWORD"
```

**作成されるリソース:**

| モジュール | リソース |
|----------|---------|
| `vpc` | VPC、パブリック/プライベートサブネット、NAT Gateway |
| `ecs` | ECS Fargate クラスタ、タスク定義、ALB |
| `rds` | PostgreSQL（db.t3.micro）、プライベートサブネット配置 |
| `ecr` | Docker イメージリポジトリ（ライフサイクルポリシー付き） |
| `s3` | モデルアーティファクト・ログ保存（パブリックアクセス全ブロック） |
| `cloudwatch` | ロググループ、アラーム、ダッシュボード |
| `iam` | ECS タスク用最小権限ロール |

### Kubernetes デプロイ

```bash
# 共通マニフェストの適用
kubectl apply -f k8s/

# 開発環境（kustomize オーバーレイ）
kubectl apply -k k8s/overlays/dev

# 本番環境
kubectl apply -k k8s/overlays/production

# デプロイ状況確認
kubectl get pods -n boat-race
kubectl get hpa -n boat-race
```

**含まれるリソース:**

| リソース | 説明 |
|---------|------|
| `Deployment` | API サーバー（replicas: 2〜10） |
| `Service` | ClusterIP サービス |
| `HPA` | CPU 70% 超で自動スケールアウト |
| `Ingress` | TLS 終端・ルーティング |
| `PVC` | モデルファイル永続化ボリューム |

### Airflow パイプライン

```bash
# Airflow の起動
docker compose -f docker-compose.airflow.yml up -d

# アクセス先: http://localhost:8080 (airflow / airflow)
```

DAG `boat_race_pipeline` のフロー:

```
scrape_races → validate_data → drift_check ─→ notify
                                    └──────→ retrain（ドリフト検出時）
scrape_racers（毎週）
```

---

## CI/CD

GitHub Actions（`.github/workflows/boat-race-ci.yml`）で以下のジョブが自動実行されます。

| ジョブ | トリガー | 内容 |
|-------|---------|------|
| `lint` | push / PR | flake8・mypy によるコード品質チェック |
| `test` | push / PR | pytest（144 テスト）・カバレッジ計測 |
| `build` | main へのマージ | Docker イメージのビルド・ECR へのプッシュ |
| `deploy` | main へのマージ | ECS Fargate への Blue/Green デプロイ |
| `terraform-validate` | PR | Terraform フォーマット・バリデーション |

```
push/PR → lint → test → (main のみ) build → deploy
                                    └──────→ terraform-validate
```

---

## テスト

```bash
# 全テスト実行
make test

# カバレッジレポート付き
make test-cov

# 特定モジュールのみ
pytest tests/test_model/ -v
pytest tests/test_api/ -v

# 直接実行
pytest --cov=app --cov-report=html tests/
open htmlcov/index.html
```

**テスト構成（合計 144 テスト）:**

| ディレクトリ | 対象 |
|------------|------|
| `tests/test_api/` | エンドポイント・認証・レート制限 |
| `tests/test_model/` | 学習・推論・特徴量・アンサンブル |
| `tests/test_drift/` | ドリフト検出・PSI・KL ダイバージェンス |
| `tests/test_ab/` | A/B テスト・シャドウモード |
| `tests/test_cli/` | CLI コマンド |
| `tests/test_integration/` | エンドツーエンド統合テスト |

---

## 環境変数リファレンス

| 変数名 | デフォルト | 説明 |
|-------|----------|------|
| `API_KEY_HASH` | ― | SHA-256 ハッシュ化された API キー（必須） |
| `DATABASE_URL` | `postgresql://localhost/boatrace` | PostgreSQL 接続 URL |
| `REDIS_URL` | `redis://localhost:6379` | Redis 接続 URL |
| `MODEL_DIR` | `models/` | モデルファイル保存ディレクトリ |
| `MODEL_VERSION` | `latest` | 使用するモデルバージョン |
| `CACHE_TTL` | `300` | Redis キャッシュ TTL（秒） |
| `RATE_LIMIT` | `100/minute` | レート制限（slowapi 形式） |
| `ENSEMBLE_MODE` | `weighted` | アンサンブルモード（`weighted` / `average`） |
| `AB_TEST_ENABLED` | `false` | A/B テストの有効化 |
| `SHADOW_ENABLED` | `false` | シャドウモードの有効化 |
| `DRIFT_PSI_THRESHOLD` | `0.2` | ドリフトアラート閾値（PSI） |
| `LOG_LEVEL` | `INFO` | ログレベル |
| `PROMETHEUS_PORT` | `8001` | Prometheus メトリクス公開ポート |
| `AWS_REGION` | `ap-northeast-1` | AWS リージョン |
| `S3_BUCKET` | ― | モデルアーティファクト用 S3 バケット名 |
| `SLACK_WEBHOOK_URL` | ― | アラート通知用 Slack Webhook URL |

---

## ライセンス

MIT License — 詳細は [LICENSE](LICENSE) を参照してください。

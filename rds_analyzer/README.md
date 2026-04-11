# RDS Cost & Performance Analyzer

Amazon RDS のコスト見積もりとパフォーマンス改善分析ツール

> ⚠️ **注意**: コスト計算結果は推定値です。実際の請求額は AWS Console でご確認ください。

---

## 概要

| 機能 | 内容 |
|------|------|
| コスト分析 | 月次コスト算出・内訳表示（コンピュート/ストレージ/IOPS/転送） |
| パフォーマンス分析 | CPU/メモリ/I/O/コネクションのボトルネック検知 |
| 改善提案 | 優先度付き提案（gp3移行/スケールダウン/Aurora移行等） |
| スコアリング | コスト効率スコア・パフォーマンス健全性スコア（0〜100） |

---

## ディレクトリ構成

```
rds_analyzer/
├── models/
│   ├── rds.py              # RDSインスタンス設定モデル
│   ├── metrics.py          # CloudWatchメトリクスモデル
│   └── costs.py            # コスト内訳モデル
├── analyzers/
│   ├── cost_analyzer.py    # コスト計算エンジン
│   ├── performance_analyzer.py  # パフォーマンス分析エンジン
│   └── recommendation_engine.py # 改善提案エンジン
├── collectors/
│   ├── cloudwatch_collector.py  # CloudWatch APIコレクター
│   ├── cost_explorer_collector.py # Cost Explorer APIコレクター
│   └── lambda_handler.py   # Lambda エントリーポイント
├── api/
│   ├── routes.py           # FastAPI ルート定義
│   └── schemas.py          # API スキーマ
└── main.py                 # FastAPI アプリ本体

terraform/
├── main.tf                 # AWSリソース定義
├── variables.tf            # 変数定義
└── outputs.tf              # 出力値

frontend/rds-dashboard/    # React ダッシュボード
```

---

## クイックスタート

### バックエンド起動

```bash
pip install -r rds_analyzer/requirements.txt
uvicorn rds_analyzer.main:app --reload
# → http://localhost:8000/docs で Swagger UI
```

### API 動作確認

```bash
# 1. インスタンスを登録
curl -X POST http://localhost:8000/api/v1/rds \
  -H "Content-Type: application/json" \
  -d '{
    "instance_id": "prod-mysql-001",
    "engine": "mysql",
    "engine_version": "8.0.35",
    "instance_class": "db.m5.large",
    "storage_type": "gp2",
    "allocated_storage_gb": 200
  }'

# 2. メトリクスを投入
curl -X POST http://localhost:8000/api/v1/rds/prod-mysql-001/metrics \
  -H "Content-Type: application/json" \
  -d '{
    "instance_id": "prod-mysql-001",
    "period_hours": 24,
    "cpu_avg_pct": 75.0, "cpu_max_pct": 92.0, "cpu_p95_pct": 88.0,
    "freeable_memory_avg_gb": 1.5, "freeable_memory_min_gb": 0.8,
    "read_iops_avg": 300.0, "write_iops_avg": 150.0,
    "read_iops_max": 500.0, "write_iops_max": 280.0,
    "read_latency_avg_ms": 8.0, "write_latency_avg_ms": 10.0,
    "connections_avg": 120.0, "connections_max": 180.0,
    "free_storage_gb": 80.0
  }'

# 3. 分析結果を取得
curl http://localhost:8000/api/v1/rds/prod-mysql-001/analysis

# 4. 改善提案を取得
curl http://localhost:8000/api/v1/rds/prod-mysql-001/recommendations
```

### フロントエンド起動

```bash
cd frontend/rds-dashboard
npm install
npm run dev
# → http://localhost:3000
```

### テスト実行

```bash
pytest tests/ -v --cov=rds_analyzer
```

---

## API エンドポイント

| メソッド | パス | 説明 |
|---------|------|------|
| GET | `/api/v1/health` | ヘルスチェック |
| POST | `/api/v1/rds` | インスタンス登録 |
| POST | `/api/v1/rds/{id}/metrics` | メトリクス手動投入 |
| GET | `/api/v1/rds/summary` | 全インスタンス概要 |
| GET | `/api/v1/rds/{id}/analysis` | 詳細分析 |
| GET | `/api/v1/rds/{id}/recommendations` | 改善提案 |

---

## インフラ構築（Terraform）

```bash
cd terraform
terraform init
terraform plan -var="environment=dev"
terraform apply -var="environment=dev"
```

---

## アーキテクチャ

```
[React Dashboard] → [API Gateway] → [Lambda (FastAPI)] → [DynamoDB]
                                           ↑
[EventBridge (5分)] → [Lambda Collector] → [CloudWatch API]
                                         → [Cost Explorer API]
```

---

## 分析ロジックの閾値

| 指標 | WARNING | CRITICAL |
|------|---------|---------|
| CPU使用率 | 70% | 85% |
| 空きメモリ比率 | 15% | 5% |
| IOPS使用率 | 75% | 90% |
| コネクション使用率 | 70% | 85% |
| ストレージ使用率 | 80% | 90% |

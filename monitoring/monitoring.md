# リアルタイムログ監視システム

## プロジェクト概要
- リポジトリ名: realtime-log-monitor
- 技術スタック:
  - バックエンド: Node.js + Express + Socket.IO
  - フロントエンド: React + TailwindCSS
  - データベース: MongoDB
  - ログ収集: Fluentd
  - コンテナ化: Docker

## リポジトリ構成
```
realtime-log-monitor/
├── .github/
│   └── workflows/
│       └── ci.yml
├── backend/
│   ├── src/
│   │   ├── controllers/
│   │   ├── models/
│   │   ├── services/
│   │   ├── routes/
│   │   └── websocket/
│   ├── Dockerfile
│   └── package.json
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── hooks/
│   │   ├── pages/
│   │   └── services/
│   ├── Dockerfile
│   └── package.json
├── fluentd/
│   ├── conf/
│   └── Dockerfile
├── docker-compose.yml
└── README.md
```

## 実装手順

### 1. プロジェクトの初期化
```bash
mkdir realtime-log-monitor
cd realtime-log-monitor
git init
```

### 2. バックエンド実装

#### 2.1 依存関係のインストール
```bash
cd backend
npm init -y
npm install express socket.io mongoose winston fluentd-logger
npm install --save-dev typescript @types/node @types/express
```

#### 2.2 Express サーバーセットアップ (src/server.ts)
```typescript
import express from 'express';
import { createServer } from 'http';
import { Server } from 'socket.io';
import mongoose from 'mongoose';
import { logRoutes } from './routes/logRoutes';

const app = express();
const httpServer = createServer(app);
const io = new Server(httpServer, {
  cors: {
    origin: process.env.FRONTEND_URL || 'http://localhost:3000',
    methods: ['GET', 'POST']
  }
});

mongoose.connect(process.env.MONGODB_URI || 'mongodb://localhost:27017/logs');

app.use(express.json());
app.use('/api/logs', logRoutes);

// WebSocket接続処理
io.on('connection', (socket) => {
  console.log('Client connected');
  
  socket.on('subscribe', (filters) => {
    // フィルター条件に基づいてログストリームを開始
  });
  
  socket.on('disconnect', () => {
    console.log('Client disconnected');
  });
});

const PORT = process.env.PORT || 4000;
httpServer.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});
```

#### 2.3 ログモデル定義 (src/models/Log.ts)
```typescript
import mongoose from 'mongoose';

const LogSchema = new mongoose.Schema({
  timestamp: {
    type: Date,
    default: Date.now
  },
  level: {
    type: String,
    enum: ['INFO', 'WARN', 'ERROR'],
    required: true
  },
  message: {
    type: String,
    required: true
  },
  source: String,
  metadata: mongoose.Schema.Types.Mixed
}, { timestamps: true });

export const Log = mongoose.model('Log', LogSchema);
```

### 3. フロントエンド実装

#### 3.1 Reactプロジェクトの作成
```bash
cd ../frontend
npx create-react-app . --template typescript
npm install @heroicons/react tailwindcss socket.io-client
```

#### 3.2 ログビューアコンポーネント (src/components/LogViewer.tsx)
```typescript
import React, { useEffect, useState } from 'react';
import { socket } from '../services/socket';

interface Log {
  timestamp: string;
  level: string;
  message: string;
  source: string;
  metadata: any;
}

export const LogViewer: React.FC = () => {
  const [logs, setLogs] = useState<Log[]>([]);
  const [filters, setFilters] = useState({
    level: 'ALL',
    source: 'ALL'
  });

  useEffect(() => {
    socket.emit('subscribe', filters);

    socket.on('log', (newLog: Log) => {
      setLogs(prevLogs => [...prevLogs, newLog]);
    });

    return () => {
      socket.off('log');
    };
  }, [filters]);

  return (
    <div className="flex flex-col h-screen">
      <div className="flex gap-4 p-4 bg-gray-100">
        {/* フィルターコントロール */}
      </div>
      <div className="flex-1 overflow-auto">
        <table className="min-w-full">
          <thead>
            <tr>
              <th>Timestamp</th>
              <th>Level</th>
              <th>Message</th>
              <th>Source</th>
            </tr>
          </thead>
          <tbody>
            {logs.map((log, index) => (
              <tr key={index}>
                <td>{new Date(log.timestamp).toLocaleString()}</td>
                <td>{log.level}</td>
                <td>{log.message}</td>
                <td>{log.source}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
```

### 4. Fluentd設定 (fluentd/conf/fluent.conf)
```apache
<source>
  @type forward
  port 24224
  bind 0.0.0.0
</source>

<match app.**>
  @type mongo
  database logs
  collection logs
  host mongodb
  port 27017

  <buffer>
    @type memory
    flush_interval 1s
  </buffer>
</match>
```

### 5. Docker設定

#### 5.1 Backend Dockerfile
```dockerfile
FROM node:18-alpine

WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build

EXPOSE 4000
CMD ["npm", "start"]
```

#### 5.2 Frontend Dockerfile
```dockerfile
FROM node:18-alpine

WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build

EXPOSE 3000
CMD ["npm", "start"]
```

#### 5.3 docker-compose.yml
```yaml
version: '3.8'

services:
  mongodb:
    image: mongo:latest
    ports:
      - "27017:27017"
    volumes:
      - mongodb_data:/data/db

  fluentd:
    build: ./fluentd
    volumes:
      - ./fluentd/conf:/fluentd/etc
    ports:
      - "24224:24224"
    depends_on:
      - mongodb

  backend:
    build: ./backend
    ports:
      - "4000:4000"
    environment:
      - MONGODB_URI=mongodb://mongodb:27017/logs
      - FLUENTD_HOST=fluentd
      - FLUENTD_PORT=24224
    depends_on:
      - mongodb
      - fluentd

  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    environment:
      - REACT_APP_BACKEND_URL=http://localhost:4000
    depends_on:
      - backend

volumes:
  mongodb_data:
```

## 使用方法

1. リポジトリのクローン:
```bash
git clone https://github.com/yourusername/realtime-log-monitor.git
cd realtime-log-monitor
```

2. 環境変数の設定:
```bash
cp .env.example .env
```

3. システムの起動:
```bash
docker-compose up -d
```

4. ログの確認:
ブラウザで `http://localhost:3000` にアクセス

## ログ送信方法

アプリケーションからのログ送信例:
```javascript
const { FluentClient } = require('fluent-logger');
const logger = new FluentClient('app', {
  host: process.env.FLUENTD_HOST,
  port: 24224
});

logger.emit('log', {
  level: 'INFO',
  message: 'Application started',
  source: 'backend',
  metadata: {
    version: '1.0.0'
  }
});
```

## 機能拡張案
- ログの検索機能
- ログレベルによるフィルタリング
- カスタムアラート設定
- ログの統計分析
- 複数のログソースの統合
- ログのエクスポート機能

## スケーリング設定（続き）

### Auto Scaling (terraform/modules/ecs/auto_scaling.tf)
```hcl
resource "aws_appautoscaling_policy" "ecs_policy" {
  target_tracking_scaling_policy_configuration {
    target_value = 75.0
    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageCPUUtilization"
    }
  }
}
```

## ディザスタリカバリ設定

### クロスリージョンレプリケーション (terraform/modules/dr/main.tf)
```hcl
resource "aws_dynamodb_table" "log_metadata" {
  name             = "${var.environment}-log-metadata"
  billing_mode     = "PAY_PER_REQUEST"
  hash_key         = "id"
  stream_enabled   = true
  stream_view_type = "NEW_AND_OLD_IMAGES"

  replica {
    region_name = var.dr_region
  }

  attribute {
    name = "id"
    type = "S"
  }
}
```

## ログ保持ポリシー

### S3ライフサイクルルール (terraform/modules/s3/lifecycle.tf)
```hcl
resource "aws_s3_bucket_lifecycle_configuration" "log_archive" {
  bucket = aws_s3_bucket.log_archive.id

  rule {
    id     = "archive_old_logs"
    status = "Enabled"

    transition {
      days          = 30
      storage_class = "STANDARD_IA"
    }

    transition {
      days          = 90
      storage_class = "GLACIER"
    }

    expiration {
      days = 365
    }
  }
}
```

## モニタリングとアラート

### Grafanaダッシュボード設定 (monitoring/grafana/dashboard.json)
```json
{
  "annotations": {
    "list": [
      {
        "builtIn": 1,
        "datasource": "-- Grafana --",
        "enable": true,
        "hide": true,
        "iconColor": "rgba(0, 211, 255, 1)",
        "name": "Annotations & Alerts",
        "type": "dashboard"
      }
    ]
  },
  "editable": true,
  "panels": [
    {
      "title": "Log Volume",
      "type": "graph",
      "datasource": "CloudWatch",
      "targets": [
        {
          "region": "${var.region}",
          "namespace": "AWS/Logs",
          "metricName": "IncomingLogEvents",
          "dimensions": {
            "LogGroupName": "/aws/ecs/log-monitor"
          },
          "period": "5m",
          "statistic": "Sum"
        }
      ]
    }
  ]
}
```

## セキュリティ設定

### WAF設定 (terraform/modules/waf/main.tf)
```hcl
resource "aws_wafv2_web_acl" "main" {
  name        = "${var.environment}-log-monitor-waf"
  description = "WAF for Log Monitor"
  scope       = "REGIONAL"

  default_action {
    allow {}
  }

  rule {
    name     = "RateLimit"
    priority = 1

    override_action {
      none {}
    }

    statement {
      rate_based_statement {
        limit              = 2000
        aggregate_key_type = "IP"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name               = "RateLimitMetric"
      sampled_requests_enabled  = true
    }
  }
}
```

## ネットワークセキュリティ

### VPCフローログ設定 (terraform/modules/vpc/flow_logs.tf)
```hcl
resource "aws_flow_log" "main" {
  iam_role_arn    = aws_iam_role.vpc_flow_log_role.arn
  log_destination = aws_cloudwatch_log_group.vpc_flow_log.arn
  traffic_type    = "ALL"
  vpc_id          = module.vpc.vpc_id
}
```

## 本番環境のデプロイチェックリスト

1. インフラストラクチャ検証:
```bash
# VPC設定の検証
aws ec2 describe-vpcs --filters Name=tag:Environment,Values=production

# セキュリティグループのチェック
aws ec2 describe-security-groups --filters Name=tag:Environment,Values=production

# ECSクラスターの状態確認
aws ecs describe-clusters --clusters production-log-monitor
```

2. アプリケーション検証:
```bash
# ヘルスチェックエンドポイントの確認
curl https://api.logmonitor.example.com/health

# メトリクスの確認
aws cloudwatch get-metric-statistics \
    --namespace AWS/ECS \
    --metric-name CPUUtilization \
    --dimensions Name=ClusterName,Value=production-log-monitor \
    --start-time $(date -u +%Y-%m-%dT%H:%M:%S -d '1 hour ago') \
    --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
    --period 300 \
    --statistics Average
```

3. バックアップ検証:
```bash
# バックアップジョブの状態確認
aws backup list-backup-jobs \
    --by-resource-arn arn:aws:mongodb:region:account-id:cluster/production-log-monitor

# リストア演習の実施
aws backup start-restore-job \
    --recovery-point-arn arn:aws:backup:region:account-id:recovery-point:backup-vault-name \
    --metadata file://restore-metadata.json
```

## 運用手順

### スケーリング調整
```bash
# ECSサービスのスケーリング設定更新
aws ecs update-service \
    --cluster production-log-monitor \
    --service log-monitor-service \
    --desired-count 4
```

### ログローテーション
```bash
# CloudWatch Logsのリテンション期間設定
aws logs put-retention-policy \
    --log-group-name /ecs/production-log-monitor \
    --retention-in-days 90
```

### メンテナンス手順
```bash
# ECSタスク定義の更新
aws ecs register-task-definition \
    --family production-log-monitor \
    --cli-input-json file://task-definition.json

# ローリングデプロイの実行
aws ecs update-service \
    --cluster production-log-monitor \
    --service log-monitor-service \
    --task-definition production-log-monitor:latest \
    --force-new-deployment
```

## トラブルシューティングガイド

### 一般的な問題の解決手順

1. コネクション問題:
```bash
# VPCエンドポイントの確認
aws ec2 describe-vpc-endpoints \
    --filters Name=vpc-id,Values=vpc-xxxxx

# セキュリティグループのルール確認
aws ec2 describe-security-group-rules \
    --filters Name=group-id,Values=sg-xxxxx
```

2. パフォーマンス問題:
```bash
# ECSサービスのメトリクス確認
aws cloudwatch get-metric-data \
    --metric-data-queries file://metric-query.json \
    --start-time $(date -u +%Y-%m-%dT%H:%M:%S -d '1 hour ago') \
    --end-time $(date -u +%Y-%m-%dT%H:%M:%S)

# コンテナログの確認
aws logs get-log-events \
    --log-group-name /ecs/production-log-monitor \
    --log-stream-name container/latest
```

## セキュリティベストプラクティス

1. 定期的なセキュリティレビュー:
- AWS SecurityHubの有効化
- AWS Inspectorの定期スキャン
- IAMアクセスレビュー

2. 暗号化設定:
- 転送中の暗号化（TLS 1.3）
- 保存時の暗号化（KMS）
- シークレット管理（AWS Secrets Manager）

3. コンプライアンス:
- AWS Config Rules
- CloudTrail監査
- セキュリティグループの定期レビュー

## パフォーマンスチューニング

1. データベース最適化:
```javascript
// MongoDBインデックス
db.logs.createIndex({ timestamp: 1 });
db.logs.createIndex({ level: 1 });
db.logs.createIndex({ source: 1 });
```

2. キャッシュ戦略:
```typescript
// Redisキャッシュ設定
const cacheConfig = {
  host: process.env.REDIS_HOST,
  port: 6379,
  maxRetryAttempts: 3,
  retryDelay: 1000
};
```

3. コネクションプーリング:
```typescript
// MongoDBコネクションプール設定
mongoose.connect(process.env.MONGODB_URI, {
  maxPoolSize: 100,
  minPoolSize: 10,
  maxIdleTimeMS: 30000
});
```


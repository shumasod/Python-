# DynamoDB「Dinosaurs」テーブル作成ガイド（修正版）

Amazon DynamoDBは、NoSQLデータベースサービスであり、高い可用性とスケーラビリティを提供します。このガイドでは、恐竜データを格納する「Dinosaurs」テーブルの作成方法を説明します。

## 1. DynamoDBテーブル作成の基本要素

テーブルを作成する際に必要な要素：

- **テーブル名**: テーブルの名前（例：Dinosaurs）
- **パーティションキー**: DynamoDBで必須のプライマリキー
- **ソートキー**（オプション）: 複合キーを構成する場合
- **課金モード**: プロビジョンドまたはオンデマンド
- **Global Secondary Index**（オプション）: クエリの柔軟性を向上

## 2. AWSマネジメントコンソールでの作成

### 手順

1. AWSコンソールにログインし、DynamoDBサービスを選択
1. 「テーブルの作成」ボタンをクリック
1. 基本情報を入力：
- **テーブル名**: `Dinosaurs`
- **パーティションキー**: `DinosaurID`（文字列型）
1. 課金モードを選択：
- **オンデマンド**: 不規則なアクセスパターンに適している
- **プロビジョンド**: 予測可能なトラフィック向け
1. 設定を確認後、「作成」をクリック

## 3. AWS SDK for Python (Boto3) での作成

### 事前準備

```bash
# Boto3のインストール
pip install boto3

# AWS認証情報の設定
aws configure
```

### 基本的なテーブル作成（オンデマンド課金）

```python
import boto3
from botocore.exceptions import ClientError

def create_dinosaurs_table():
    # DynamoDBリソースを作成
    dynamodb = boto3.resource('dynamodb', region_name='ap-northeast-1')
    
    try:
        # テーブルを作成
        table = dynamodb.create_table(
            TableName='Dinosaurs',
            KeySchema=[
                {
                    'AttributeName': 'DinosaurID',
                    'KeyType': 'HASH'  # パーティションキー
                }
            ],
            AttributeDefinitions=[
                {
                    'AttributeName': 'DinosaurID',
                    'AttributeType': 'S'  # 文字列型
                }
            ],
            BillingMode='PAY_PER_REQUEST',  # オンデマンド課金
            Tags=[
                {
                    'Key': 'Project',
                    'Value': 'DinosaurDatabase'
                }
            ]
        )

        # テーブル作成完了まで待機
        print("テーブルを作成中...")
        table.meta.client.get_waiter('table_exists').wait(TableName='Dinosaurs')
        print(f'テーブル "{table.table_name}" が正常に作成されました。')
        
        return table

    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'ResourceInUseException':
            print("テーブル 'Dinosaurs' は既に存在します。")
            return dynamodb.Table('Dinosaurs')
        else:
            print(f"テーブル作成中にエラーが発生しました: {e}")
            raise

# テーブル作成を実行
table = create_dinosaurs_table()
```

### 高度なテーブル作成（GSI付き）

```python
def create_advanced_dinosaurs_table():
    dynamodb = boto3.resource('dynamodb', region_name='ap-northeast-1')
    
    try:
        table = dynamodb.create_table(
            TableName='Dinosaurs',
            KeySchema=[
                {
                    'AttributeName': 'Period',      # 地質年代をパーティションキーに
                    'KeyType': 'HASH'
                },
                {
                    'AttributeName': 'DinosaurID',  # 恐竜IDをソートキーに
                    'KeyType': 'RANGE'
                }
            ],
            AttributeDefinitions=[
                {
                    'AttributeName': 'Period',
                    'AttributeType': 'S'
                },
                {
                    'AttributeName': 'DinosaurID',
                    'AttributeType': 'S'
                },
                {
                    'AttributeName': 'Diet',
                    'AttributeType': 'S'
                },
                {
                    'AttributeName': 'Name',
                    'AttributeType': 'S'
                }
            ],
            BillingMode='PAY_PER_REQUEST',
            GlobalSecondaryIndexes=[
                {
                    'IndexName': 'DietIndex',
                    'KeySchema': [
                        {
                            'AttributeName': 'Diet',
                            'KeyType': 'HASH'
                        }
                    ],
                    'Projection': {
                        'ProjectionType': 'ALL'
                    }
                },
                {
                    'IndexName': 'NameIndex',
                    'KeySchema': [
                        {
                            'AttributeName': 'Name',
                            'KeyType': 'HASH'
                        }
                    ],
                    'Projection': {
                        'ProjectionType': 'ALL'
                    }
                }
            ],
            Tags=[
                {
                    'Key': 'Environment',
                    'Value': 'Development'
                },
                {
                    'Key': 'Project',
                    'Value': 'DinosaurDatabase'
                }
            ]
        )

        print("高度なテーブルを作成中...")
        table.meta.client.get_waiter('table_exists').wait(TableName='Dinosaurs')
        print(f'テーブル "{table.table_name}" が正常に作成されました（GSI付き）。')
        
        return table

    except ClientError as e:
        print(f"テーブル作成中にエラーが発生しました: {e}")
        raise
```

## 4. テーブル状態の確認

```python
def check_table_status(table_name='Dinosaurs'):
    dynamodb = boto3.resource('dynamodb', region_name='ap-northeast-1')
    
    try:
        table = dynamodb.Table(table_name)
        
        # テーブル情報を取得
        response = table.meta.client.describe_table(TableName=table_name)
        table_info = response['Table']
        
        print(f"テーブル名: {table_info['TableName']}")
        print(f"ステータス: {table_info['TableStatus']}")
        print(f"作成日時: {table_info['CreationDateTime']}")
        print(f"項目数: {table_info.get('ItemCount', 0)}")
        print(f"課金モード: {table_info.get('BillingModeSummary', {}).get('BillingMode', 'PROVISIONED')}")
        
        # GSIの情報も表示
        if 'GlobalSecondaryIndexes' in table_info:
            print("\nGlobal Secondary Indexes:")
            for gsi in table_info['GlobalSecondaryIndexes']:
                print(f"  - {gsi['IndexName']}: {gsi['IndexStatus']}")

    except ClientError as e:
        print(f"テーブル情報の取得中にエラーが発生しました: {e}")

# テーブル状態を確認
check_table_status()
```

## 5. サンプルデータの挿入

### 単一アイテムの挿入

```python
def insert_sample_dinosaur(table):
    try:
        response = table.put_item(
            Item={
                'Period': 'Cretaceous',
                'DinosaurID': 'T-REX-001',
                'Name': 'Tyrannosaurus Rex',
                'Diet': 'Carnivore',
                'Length': '12-13 meters',
                'Weight': '8-14 tons',
                'Habitat': 'North America',
                'Discovered': '1905'
            },
            ConditionExpression='attribute_not_exists(DinosaurID)'  # 重複防止
        )
        print("恐竜データが正常に挿入されました。")
        
    except ClientError as e:
        if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
            print("この恐竜IDは既に存在します。")
        else:
            print(f"データ挿入中にエラーが発生しました: {e}")

# サンプルデータを挿入
table = boto3.resource('dynamodb').Table('Dinosaurs')
insert_sample_dinosaur(table)
```

### 複数アイテムのバッチ挿入

```python
def insert_multiple_dinosaurs(table):
    dinosaurs = [
        {
            'Period': 'Jurassic',
            'DinosaurID': 'ALLO-001',
            'Name': 'Allosaurus',
            'Diet': 'Carnivore',
            'Length': '8-12 meters',
            'Weight': '2.3-4.6 tons',
            'Habitat': 'North America'
        },
        {
            'Period': 'Cretaceous',
            'DinosaurID': 'TRICE-001',
            'Name': 'Triceratops',
            'Diet': 'Herbivore',
            'Length': '8-9 meters',
            'Weight': '6-12 tons',
            'Habitat': 'North America'
        },
        {
            'Period': 'Jurassic',
            'DinosaurID': 'BRACHIO-001',
            'Name': 'Brachiosaurus',
            'Diet': 'Herbivore',
            'Length': '20-23 meters',
            'Weight': '35-56 tons',
            'Habitat': 'North America'
        }
    ]
    
    try:
        with table.batch_writer() as batch:
            for dinosaur in dinosaurs:
                batch.put_item(Item=dinosaur)
        
        print(f"{len(dinosaurs)}件の恐竜データが正常に挿入されました。")
        
    except ClientError as e:
        print(f"バッチ挿入中にエラーが発生しました: {e}")

# 複数データを挿入
insert_multiple_dinosaurs(table)
```

## 6. データクエリの例

### パーティションキーでのクエリ

```python
def query_by_period(table, period):
    try:
        response = table.query(
            KeyConditionExpression=boto3.dynamodb.conditions.Key('Period').eq(period)
        )
        
        items = response['Items']
        print(f"{period}時代の恐竜: {len(items)}件")
        
        for item in items:
            print(f"  - {item['Name']} ({item['Diet']})")
            
        return items
        
    except ClientError as e:
        print(f"クエリ中にエラーが発生しました: {e}")

# 白亜紀の恐竜を検索
cretaceous_dinosaurs = query_by_period(table, 'Cretaceous')
```

### GSIを使ったクエリ

```python
def query_by_diet(table, diet):
    try:
        response = table.query(
            IndexName='DietIndex',
            KeyConditionExpression=boto3.dynamodb.conditions.Key('Diet').eq(diet)
        )
        
        items = response['Items']
        print(f"{diet}の恐竜: {len(items)}件")
        
        for item in items:
            print(f"  - {item['Name']} ({item['Period']}時代)")
            
        return items
        
    except ClientError as e:
        print(f"GSIクエリ中にエラーが発生しました: {e}")

# 肉食恐竜を検索
carnivores = query_by_diet(table, 'Carnivore')
```

## 7. ベストプラクティス

### セキュリティ

- IAMロールを使用してアクセス制御を実装
- 最小権限の原則に従ってアクセス許可を設定

### パフォーマンス

- ホットパーティションを避けるためのキー設計
- 必要な属性のみをプロジェクション

### コスト最適化

- 開発環境ではオンデマンド課金を使用
- 本番環境では使用パターンに応じて課金モードを選択

### エラーハンドリング

```python
import time
from botocore.exceptions import ClientError

def robust_put_item(table, item, max_retries=3):
    """指数バックオフでリトライするput_item"""
    for attempt in range(max_retries):
        try:
            return table.put_item(Item=item)
        except ClientError as e:
            if e.response['Error']['Code'] == 'ProvisionedThroughputExceededException':
                if attempt < max_retries - 1:
                    wait_time = (2 ** attempt) + (random.randint(0, 1000) / 1000)
                    print(f"スループット制限に達しました。{wait_time}秒待機中...")
                    time.sleep(wait_time)
                    continue
            raise
```

## まとめ

このガイドでは、DynamoDBで恐竜データを管理するためのテーブル作成から基本的なデータ操作まで、実用的なコード例とともに説明しました。本番環境では、セキュリティ、パフォーマンス、コストを考慮した設計を行うことが重要です。
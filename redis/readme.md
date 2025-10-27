# Redis Clone - シンプルなRedis実装

Pythonで実装した基本的なRedisクローンです。主要な機能をサポートしています。

## 特徴

- ✅ 基本的なキー・バリューストア
- ✅ TTL（Time To Live）サポート
- ✅ マルチスレッド対応
- ✅ Redis互換のコマンド
- ✅ ソケット通信

## サポートするコマンド

| コマンド | 説明 | 例 |
|---------|------|-----|
| `SET key value [EX seconds]` | キーに値を設定 | `SET mykey "hello"` |
| `GET key` | キーの値を取得 | `GET mykey` |
| `DEL key` | キーを削除 | `DEL mykey` |
| `EXISTS key` | キーの存在確認 | `EXISTS mykey` |
| `EXPIRE key seconds` | キーに有効期限を設定 | `EXPIRE mykey 60` |
| `TTL key` | キーの残り時間を取得 | `TTL mykey` |
| `KEYS pattern` | パターンに一致するキーを取得 | `KEYS *` |
| `INCR key` | 整数値をインクリメント | `INCR counter` |
| `DECR key` | 整数値をデクリメント | `DECR counter` |
| `PING` | サーバーの疎通確認 | `PING` |
| `QUIT` | 接続を終了 | `QUIT` |

## 使い方

### 1. サーバーの起動

```bash
python3 redis_clone.py
```

デフォルトで `127.0.0.1:6380` で起動します。

### 2. クライアントの使用

#### 対話モード

```bash
python3 redis_client.py
```

#### テストの実行

```bash
python3 redis_client.py test
```

### 3. コマンド例

```bash
redis> SET username "taro"
+OK

redis> GET username
$4
taro

redis> SET counter 0
+OK

redis> INCR counter
:1

redis> INCR counter
:2

redis> GET counter
$1
2

redis> SET session abc123 EX 10
+OK

redis> TTL session
:10

redis> KEYS *
*3
$8
username
$7
counter
$7
session
```

## アーキテクチャ

### データ構造

- `data: Dict[str, Any]` - キーと値を保存
- `expiry: Dict[str, float]` - キーの有効期限（UNIXタイムスタンプ）

### スレッド安全性

- `threading.Lock` を使用してデータへの同時アクセスを制御

### プロトコル

Redis互換のRESPプロトコル風の実装：
- Simple Strings: `+OK\r\n`
- Errors: `-ERR message\r\n`
- Integers: `:123\r\n`
- Bulk Strings: `$6\r\nfoobar\r\n`
- Arrays: `*2\r\n$3\r\nfoo\r\n$3\r\nbar\r\n`

## 制限事項

- データは永続化されません（メモリ上のみ）
- 文字列型のみサポート（リスト、セット等は未実装）
- パターンマッチングは基本的な機能のみ
- パフォーマンスは本家Redisには及びません

## 拡張案

さらに機能を追加する場合：
- AOF/RDBによる永続化
- レプリケーション
- クラスタリング
- リスト、セット、ハッシュ等のデータ型
- Pub/Sub機能
- トランザクション（MULTI/EXEC）
- Luaスクリプト

## ライセンス

MIT License

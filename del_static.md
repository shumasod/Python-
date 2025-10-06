# Netconf ルート削除スクリプト 使用方法

## 概要
このスクリプトは、Cisco IOS-XE デバイスからNetconfを使用してスタティックルートを削除するためのツールです。

## 前提条件
- Python 3.7以上
- 必要なPythonパッケージ:
  ```bash
  pip install ncclient lxml PyYAML
  ```
- Cisco IOS-XE デバイスでNetconfが有効化されていること

## インストールと設定

### 1. 依存関係のインストール
```bash
pip install ncclient lxml PyYAML
```

### 2. 設定ファイルの作成
```bash
python netconf_route_manager.py --create-sample-config
```
これにより `netconf_config.yml` が作成されます。

### 3. 設定ファイルの編集
`netconf_config.yml` を編集して、適切な接続情報を設定してください。

## 使用方法

### 基本的な使用方法

#### コマンドラインでルートを指定
```bash
python netconf_route_manager.py --routes 1.1.1.1/32 1.1.1.2/32 1.1.1.3/32
```

#### ファイルからルートを読み込み
```bash
python netconf_route_manager.py --routes-file routes.txt
```

#### ドライラン（実際の変更なし）
```bash
python netconf_route_manager.py --dry-run --routes 1.1.1.1/32
```

### 高度なオプション

#### 接続テストのみ実行
```bash
python netconf_route_manager.py --test-connection
```

#### デバッグログを有効にして実行
```bash
python netconf_route_manager.py --log-level DEBUG --routes 1.1.1.1/32
```

#### ログをファイルに出力
```bash
python netconf_route_manager.py --log-file netconf.log --routes 1.1.1.1/32
```

#### カスタム設定ファイルを使用
```bash
python netconf_route_manager.py --config my_config.yml --routes 1.1.1.1/32
```

## コマンドライン引数

| 引数 | 説明 | デフォルト値 |
|------|------|-------------|
| `-c, --config` | 設定ファイルのパス | netconf_config.yml |
| `-r, --routes` | 削除するルート (CIDR記法) | - |
| `-f, --routes-file` | ルートリストファイル | - |
| `--dry-run` | ドライランモード | False |
| `--test-connection` | 接続テストのみ | False |
| `--create-sample-config` | サンプル設定作成 | False |
| `--log-level` | ログレベル | INFO |
| `--log-file` | ログファイル | - |

## 設定ファイル形式

```yaml
host: '192.168.1.1'      # デバイスのIPアドレス
port: 830                 # Netconfポート
username: 'admin'         # ユーザー名
password: null            # パスワード（nullの場合は実行時入力）
timeout: 30               # 接続タイムアウト
device_type: 'iosxe'      # デバイスタイプ
verify_ssl: false         # SSL証明書検証
max_retries: 3            # 最大リトライ回数
retry_delay: 5            # リトライ間隔
```

## ルートファイル形式

```
# コメント行は '#' で始めます
1.1.1.1/32
1.1.1.2/32
192.168.100.0/24
```

## エラー対応

### よくあるエラー

1. **接続エラー**
   - デバイスのIPアドレスとポートを確認
   - Netconfが有効化されているか確認
   - ファイアウォール設定を確認

2. **認証エラー**
   - ユーザー名とパスワードを確認
   - ユーザーにNetconf権限があるか確認

3. **XML構文エラー**
   - ルート形式が正しいか確認（CIDR記法）
   - 特殊文字や不正な文字が含まれていないか確認

### トラブルシューティング

1. **接続テスト**
   ```bash
   python netconf_route_manager.py --test-connection
   ```

2. **デバッグモード実行**
   ```bash
   python netconf_route_manager.py --log-level DEBUG --dry-run --routes 1.1.1.1/32
   ```

3. **ペイロード確認**
   デバッグモードで生成されるXMLペイロードを確認してください。

## セキュリティ注意事項

1. **パスワード管理**
   - 設定ファイルにパスワードを平文で保存しないでください
   - `password: null` に設定して実行時入力を推奨

2. **アクセス制御**
   - 必要最小限の権限を持つユーザーを使用
   - 本番環境では必ずドライランで検証

3. **ログファイル**
   - ログファイルに機密情報が記録される可能性があります
   - 適切なファイル権限を設定してください

## 動作確認

### Cisco IOS-XE でのNetconf有効化
```
configure terminal
netconf-yang
netconf-yang cisco-odm polling-enable
netconf-yang cisco-odm actions INTERFACE,OSPF,BGP
end
```

### 設定確認
```
show netconf-yang sessions
show netconf-yang statistics
```

## サポート

このスクリプトは以下の環境でテストされています:
- Cisco IOS-XE 16.x以降
- Python 3.7-3.11
- ncclient 0.6.x以降

問題が発生した場合は、デバッグログと併せてエラー内容を確認してください。

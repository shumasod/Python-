# Netconf 接続設定ファイル
# このファイルを参考に設定を変更してください

# デバイスの接続情報
host: '192.168.1.1'  # デバイスのIPアドレスまたはホスト名
port: 830            # Netconfポート（通常は830）
username: 'admin'    # ユーザー名
password: null       # パスワード（nullの場合は実行時に入力を求められます）

# 接続オプション
timeout: 30          # 接続タイムアウト（秒）
device_type: 'iosxe' # デバイスタイプ（Cisco IOS-XE）
verify_ssl: false    # SSL証明書の検証（通常はfalse）

# リトライ設定
max_retries: 3       # 最大リトライ回数
retry_delay: 5       # リトライ間隔（秒）

# 使用例:
# 1. このファイルを netconf_config.yml として保存
# 2. 適切な値に変更
# 3. スクリプト実行: python netconf_route_manager.py

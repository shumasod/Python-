#!/usr/bin/env python3
"""
Redis Clone クライアント
"""

import socket


class RedisClient:
    def __init__(self, host: str = '127.0.0.1', port: int = 6380):
        self.host = host
        self.port = port
        self.socket = None
    
    def connect(self):
        """サーバーに接続"""
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect((self.host, self.port))
        print(f"[+] サーバーに接続しました: {self.host}:{self.port}")
    
    def send_command(self, command: str) -> str:
        """コマンドを送信して結果を受信"""
        if not self.socket:
            raise Exception("サーバーに接続していません")
        
        self.socket.send(f"{command}\r\n".encode('utf-8'))
        response = self.socket.recv(4096).decode('utf-8')
        return response.strip()
    
    def close(self):
        """接続を閉じる"""
        if self.socket:
            self.socket.close()
            print("[+] 接続を閉じました")
    
    def interactive(self):
        """対話モード"""
        print("\n=== Redis Clone クライアント ===")
        print("コマンドを入力してください (終了: quit)")
        print("=" * 35 + "\n")
        
        self.connect()
        
        try:
            while True:
                command = input("redis> ")
                if not command:
                    continue
                
                response = self.send_command(command)
                print(response)
                
                if command.strip().upper() == "QUIT":
                    break
        
        except KeyboardInterrupt:
            print("\n[+] 終了します")
        
        finally:
            self.close()


def run_tests():
    """基本的なテストを実行"""
    print("\n=== Redis Clone テスト実行 ===\n")
    
    client = RedisClient()
    client.connect()
    
    tests = [
        ("PING", "サーバーの動作確認"),
        ("SET mykey hello", "値の設定"),
        ("GET mykey", "値の取得"),
        ("EXISTS mykey", "キーの存在確認"),
        ("SET counter 10", "カウンター初期化"),
        ("INCR counter", "インクリメント"),
        ("INCR counter", "インクリメント"),
        ("GET counter", "カウンター値取得"),
        ("DECR counter", "デクリメント"),
        ("GET counter", "カウンター値取得"),
        ("SET tempkey temporary EX 5", "5秒で期限切れのキー設定"),
        ("TTL tempkey", "残り時間確認"),
        ("KEYS *", "全キー一覧"),
        ("DEL mykey", "キー削除"),
        ("EXISTS mykey", "削除後の存在確認"),
    ]
    
    for command, description in tests:
        print(f"[テスト] {description}")
        print(f"コマンド: {command}")
        response = client.send_command(command)
        print(f"結果: {response}")
        print("-" * 50)
    
    client.close()
    print("\n[+] テスト完了")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        run_tests()
    else:
        client = RedisClient()
        client.interactive()

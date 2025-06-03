import os
import requests
from requests.auth import HTTPBasicAuth
import time
import logging
from datetime import datetime, timedelta

# シンプルなログ設定
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class APIClient:
    def __init__(self, base_url, client_id, client_secret, timeout=10):
        self.base_url = base_url
        self.client_id = client_id
        self.client_secret = client_secret
        self.timeout = timeout
        self.access_token = None
        self.token_expiry = None
        self.session = requests.Session()
        self.session.headers.update({'Content-Type': 'application/json'})
    
    def _retry_request(self, func, *args, **kwargs):
        """シンプルなリトライ機能"""
        for attempt in range(3):
            try:
                return func(*args, **kwargs)
            except requests.RequestException as e:
                if attempt == 2:  # 最後の試行
                    raise
                logger.warning(f"リトライ {attempt + 1}/3: {e}")
                time.sleep(0.5 * (2 ** attempt))  # 指数的バックオフ
    
    def get_access_token(self):
        """トークン取得（有効期限チェック付き）"""
        if self.access_token and self.token_expiry and datetime.now() < self.token_expiry:
            return self.access_token
        
        logger.info("新しいトークンを取得中...")
        auth = HTTPBasicAuth(self.client_id, self.client_secret)
        
        def _get_token():
            response = self.session.post(
                f"{self.base_url}/oauth/token",
                auth=auth,
                data={'grant_type': 'client_credentials', 'scope': '*'},
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
        
        token_data = self._retry_request(_get_token)
        self.access_token = token_data['access_token']
        
        # トークン有効期限設定
        if 'expires_in' in token_data:
            self.token_expiry = datetime.now() + timedelta(seconds=token_data['expires_in'] - 10)
        
        return self.access_token
    
    def request(self, endpoint, method='GET', data=None, params=None):
        """APIリクエスト実行"""
        self.get_access_token()
        
        def _make_request():
            response = self.session.request(
                method,
                f"{self.base_url}{endpoint}",
                headers={'Authorization': f'Bearer {self.access_token}'},
                json=data,
                params=params,
                timeout=self.timeout
            )
            
            # 認証エラーの場合、トークン再取得
            if response.status_code in (401, 403, 419):
                logger.warning("認証エラー: トークンを再取得")
                self.access_token = None
                self.get_access_token()
                response = self.session.request(
                    method,
                    f"{self.base_url}{endpoint}",
                    headers={'Authorization': f'Bearer {self.access_token}'},
                    json=data,
                    params=params,
                    timeout=self.timeout
                )
            
            response.raise_for_status()
            return response.json()
        
        return self._retry_request(_make_request)
    
    def health_check(self):
        """シンプルなヘルスチェック"""
        try:
            # トークン取得テスト
            self.get_access_token()
            
            # APIエンドポイントテスト（必要に応じてエンドポイントを変更）
            try:
                self.request('/api/user')
                return {"status": "ok", "timestamp": datetime.now().isoformat()}
            except Exception as e:
                return {"status": "error", "error": str(e), "timestamp": datetime.now().isoformat()}
        except Exception as e:
            return {"status": "error", "error": f"認証失敗: {str(e)}", "timestamp": datetime.now().isoformat()}
    
    def close(self):
        """セッションクローズ"""
        self.session.close()

def main():
    """メイン実行関数"""
    # 環境変数取得
    base_url = os.environ.get("API_BASE_URL")
    client_id = os.environ.get("CLIENT_ID")
    client_secret = os.environ.get("CLIENT_SECRET")
    timeout = int(os.environ.get("API_TIMEOUT", 10))
    
    if not all([base_url, client_id, client_secret]):
        logger.error("必要な環境変数が設定されていません: API_BASE_URL, CLIENT_ID, CLIENT_SECRET")
        exit(1)
    
    try:
        client = APIClient(base_url, client_id, client_secret, timeout)
        result = client.health_check()
        
        logger.info(f"ヘルスチェック結果: {result}")
        print(result)
        
        client.close()
        exit(0 if result["status"] == "ok" else 1)
        
    except Exception as e:
        logger.error(f"エラー: {e}")
        exit(2)

if __name__ == "__main__":
    main()
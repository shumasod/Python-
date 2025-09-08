import os
import requests
from requests.auth import HTTPBasicAuth
import time
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Union
import json

# 詳細なログ設定

logging.basicConfig(
level=logging.INFO,
format=’%(asctime)s - %(name)s - %(levelname)s - %(message)s’,
handlers=[
logging.StreamHandler(),
# 必要に応じてファイルハンドラーも追加
# logging.FileHandler(‘api_client.log’)
]
)
logger = logging.getLogger(**name**)

class APIClientError(Exception):
“”“APIクライアント専用例外”””
pass

class AuthenticationError(APIClientError):
“”“認証エラー”””
pass

class APIClient:
def **init**(self, base_url: str, client_id: str, client_secret: str, timeout: int = 10):
self.base_url = base_url.rstrip(’/’)  # 末尾のスラッシュを削除
self.client_id = client_id
self.client_secret = client_secret
self.timeout = timeout
self.access_token: Optional[str] = None
self.token_expiry: Optional[datetime] = None
self.session = requests.Session()
self.session.headers.update({
‘Content-Type’: ‘application/json’,
‘User-Agent’: ‘APIClient/1.0’
})

```
    # レート制限対応
    self.last_request_time = 0
    self.min_request_interval = 0.1  # 100ms間隔

def _wait_for_rate_limit(self):
    """レート制限対応の待機"""
    current_time = time.time()
    time_since_last = current_time - self.last_request_time
    if time_since_last < self.min_request_interval:
        sleep_time = self.min_request_interval - time_since_last
        time.sleep(sleep_time)
    self.last_request_time = time.time()

def _retry_request(self, func, *args, max_retries: int = 3, **kwargs):
    """改良されたリトライ機能"""
    last_exception = None
    
    for attempt in range(max_retries):
        try:
            self._wait_for_rate_limit()
            return func(*args, **kwargs)
        except requests.exceptions.Timeout as e:
            last_exception = e
            logger.warning(f"タイムアウト - リトライ {attempt + 1}/{max_retries}: {e}")
        except requests.exceptions.ConnectionError as e:
            last_exception = e
            logger.warning(f"接続エラー - リトライ {attempt + 1}/{max_retries}: {e}")
        except requests.exceptions.RequestException as e:
            last_exception = e
            # 4xxエラーはリトライしない
            if hasattr(e, 'response') and e.response is not None:
                if 400 <= e.response.status_code < 500 and e.response.status_code not in [429]:
                    raise APIClientError(f"クライアントエラー {e.response.status_code}: {e}")
            logger.warning(f"リクエストエラー - リトライ {attempt + 1}/{max_retries}: {e}")
        
        if attempt < max_retries - 1:
            wait_time = min(2 ** attempt, 10)  # 最大10秒まで
            logger.info(f"{wait_time}秒待機後にリトライします...")
            time.sleep(wait_time)
    
    raise APIClientError(f"最大リトライ回数に達しました: {last_exception}")

def get_access_token(self) -> str:
    """トークン取得（有効期限チェック付き）"""
    # 既存のトークンが有効な場合はそれを返す
    if (self.access_token and 
        self.token_expiry and 
        datetime.now() < self.token_expiry):
        return self.access_token
    
    logger.info("新しいアクセストークンを取得中...")
    auth = HTTPBasicAuth(self.client_id, self.client_secret)
    
    def _get_token():
        response = self.session.post(
            f"{self.base_url}/oauth/token",
            auth=auth,
            data={
                'grant_type': 'client_credentials',
                'scope': '*'
            },
            timeout=self.timeout,
            headers={'Content-Type': 'application/x-www-form-urlencoded'}
        )
        
        if response.status_code == 401:
            raise AuthenticationError("認証情報が無効です")
        elif response.status_code == 403:
            raise AuthenticationError("アクセスが拒否されました")
        
        response.raise_for_status()
        return response.json()
    
    try:
        token_data = self._retry_request(_get_token)
    except Exception as e:
        raise AuthenticationError(f"トークン取得に失敗: {e}")
    
    # レスポンス検証
    if 'access_token' not in token_data:
        raise AuthenticationError("レスポンスにaccess_tokenが含まれていません")
    
    self.access_token = token_data['access_token']
    
    # トークン有効期限設定（安全マージン付き）
    expires_in = token_data.get('expires_in', 3600)  # デフォルト1時間
    safety_margin = min(expires_in * 0.1, 300)  # 10%または5分の小さい方
    self.token_expiry = datetime.now() + timedelta(seconds=expires_in - safety_margin)
    
    logger.info(f"アクセストークン取得成功 (有効期限: {self.token_expiry})")
    return self.access_token

def request(self, endpoint: str, method: str = 'GET', 
           data: Optional[Dict] = None, params: Optional[Dict] = None,
           raw_response: bool = False) -> Union[Dict, requests.Response]:
    """APIリクエスト実行"""
    # エンドポイントの正規化
    if not endpoint.startswith('/'):
        endpoint = '/' + endpoint
    
    url = f"{self.base_url}{endpoint}"
    
    def _make_request():
        # トークン取得
        token = self.get_access_token()
        
        headers = {
            'Authorization': f'Bearer {token}',
            **self.session.headers
        }
        
        logger.debug(f"{method} {url}")
        
        response = self.session.request(
            method=method,
            url=url,
            headers=headers,
            json=data if data else None,
            params=params,
            timeout=self.timeout
        )
        
        # 認証エラーの場合、トークンをクリアして再試行
        if response.status_code in (401, 403, 419):
            logger.warning(f"認証エラー ({response.status_code}): トークンを再取得")
            self.access_token = None
            self.token_expiry = None
            
            # 再度トークン取得してリクエスト
            token = self.get_access_token()
            headers['Authorization'] = f'Bearer {token}'
            
            response = self.session.request(
                method=method,
                url=url,
                headers=headers,
                json=data if data else None,
                params=params,
                timeout=self.timeout
            )
        
        # レスポンス検証
        if response.status_code >= 400:
            error_msg = f"HTTP {response.status_code}"
            try:
                error_detail = response.json().get('message', response.text)
                error_msg += f": {error_detail}"
            except (ValueError, AttributeError):
                error_msg += f": {response.text}"
            raise requests.HTTPError(error_msg, response=response)
        
        return response
    
    response = self._retry_request(_make_request)
    
    if raw_response:
        return response
    
    # JSONレスポンスの解析
    try:
        return response.json()
    except ValueError as e:
        logger.warning(f"JSONデコードエラー: {e}")
        return {"raw_response": response.text}

def health_check(self) -> Dict[str, Any]:
    """改良されたヘルスチェック"""
    start_time = time.time()
    result = {
        "timestamp": datetime.now().isoformat(),
        "status": "unknown",
        "checks": {}
    }
    
    try:
        # 1. 認証チェック
        logger.info("認証テスト中...")
        auth_start = time.time()
        self.get_access_token()
        result["checks"]["authentication"] = {
            "status": "ok",
            "duration_ms": round((time.time() - auth_start) * 1000, 2)
        }
        
        # 2. APIエンドポイントチェック
        logger.info("APIエンドポイントテスト中...")
        api_start = time.time()
        try:
            # 汎用的なエンドポイント（存在しない場合は404が返る）
            test_endpoints = ['/api/health', '/api/status', '/api/user', '/health', '/status']
            
            api_response = None
            for endpoint in test_endpoints:
                try:
                    api_response = self.request(endpoint, raw_response=True)
                    if api_response.status_code == 200:
                        result["checks"]["api_endpoint"] = {
                            "status": "ok",
                            "endpoint": endpoint,
                            "duration_ms": round((time.time() - api_start) * 1000, 2)
                        }
                        break
                except requests.HTTPError as e:
                    if hasattr(e, 'response') and e.response.status_code == 404:
                        continue
                    raise
            
            if "api_endpoint" not in result["checks"]:
                result["checks"]["api_endpoint"] = {
                    "status": "warning",
                    "message": "利用可能なテストエンドポイントが見つかりません",
                    "duration_ms": round((time.time() - api_start) * 1000, 2)
                }
                
        except Exception as e:
            result["checks"]["api_endpoint"] = {
                "status": "error",
                "error": str(e),
                "duration_ms": round((time.time() - api_start) * 1000, 2)
            }
        
        # 3. 全体ステータス判定
        all_checks_ok = all(
            check.get("status") == "ok" 
            for check in result["checks"].values()
        )
        
        has_errors = any(
            check.get("status") == "error" 
            for check in result["checks"].values()
        )
        
        if has_errors:
            result["status"] = "error"
        elif all_checks_ok:
            result["status"] = "ok"
        else:
            result["status"] = "warning"
            
    except AuthenticationError as e:
        result["status"] = "error"
        result["checks"]["authentication"] = {
            "status": "error",
            "error": str(e)
        }
    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)
    
    result["total_duration_ms"] = round((time.time() - start_time) * 1000, 2)
    return result

def close(self):
    """リソースクリーンアップ"""
    logger.info("APIクライアントを終了中...")
    self.session.close()
    self.access_token = None
    self.token_expiry = None
```

def main():
“”“メイン実行関数”””
logger.info(“APIクライアント ヘルスチェック開始”)

```
# 環境変数検証
required_vars = ["API_BASE_URL", "CLIENT_ID", "CLIENT_SECRET"]
missing_vars = [var for var in required_vars if not os.environ.get(var)]

if missing_vars:
    logger.error(f"必要な環境変数が設定されていません: {', '.join(missing_vars)}")
    return 1

# 設定取得
config = {
    "base_url": os.environ["API_BASE_URL"],
    "client_id": os.environ["CLIENT_ID"],
    "client_secret": os.environ["CLIENT_SECRET"],
    "timeout": int(os.environ.get("API_TIMEOUT", "10"))
}

logger.info(f"設定: base_url={config['base_url']}, timeout={config['timeout']}s")

client = None
try:
    # APIクライアント初期化
    client = APIClient(**config)
    
    # ヘルスチェック実行
    logger.info("ヘルスチェック実行中...")
    result = client.health_check()
    
    # 結果出力
    print(json.dumps(result, indent=2, ensure_ascii=False))
    
    # ログ出力
    if result["status"] == "ok":
        logger.info("✅ ヘルスチェック成功")
        return 0
    elif result["status"] == "warning":
        logger.warning("⚠️ ヘルスチェック警告あり")
        return 0
    else:
        logger.error("❌ ヘルスチェック失敗")
        return 1
        
except KeyboardInterrupt:
    logger.info("ユーザーによって中断されました")
    return 1
except Exception as e:
    logger.error(f"予期しないエラー: {e}", exc_info=True)
    return 2
finally:
    if client:
        client.close()
```

if **name** == “**main**”:
exit(main())
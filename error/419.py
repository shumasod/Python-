
import os
import requests
from requests.auth import HTTPBasicAuth
import time
from functools import wraps
import logging
import json
from datetime import datetime

# ロギングの設定を改善
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    handlers=[
        logging.FileHandler("api_client.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def retry_decorator(max_retries=3, backoff_factor=0.3, allowed_exceptions=(requests.exceptions.RequestException,)):
    """改善されたリトライデコレータ - タイムアウトと例外タイプを拡張"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            retries = 0
            while retries < max_retries:
                try:
                    return func(*args, **kwargs)
                except allowed_exceptions as e:
                    retries += 1
                    if retries == max_retries:
                        logger.error(f"リトライ上限に達しました。エラー: {e}", exc_info=True)
                        raise
                    wait_time = backoff_factor * (2 ** (retries - 1))
                    logger.warning(f"リトライ {retries}/{max_retries} - {wait_time:.2f}秒後に再試行します。エラー: {str(e)}")
                    time.sleep(wait_time)
        return wrapper
    return decorator

class APIClient:
    def __init__(self, base_url, client_id, client_secret, timeout=10):
        self.base_url = base_url
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token = None
        self.token_expiry = None
        self.timeout = timeout
        # 接続プーリングのためのセッションを使用
        self.session = requests.Session()
        # デフォルトのHTTPヘッダー
        self.session.headers.update({'Content-Type': 'application/json'})
    
    def __del__(self):
        """リソースのクリーンアップ"""
        if hasattr(self, 'session'):
            self.session.close()
    
    @retry_decorator(max_retries=5, backoff_factor=0.5)
    def get_access_token(self):
        """アクセストークンの取得と有効期限の管理"""
        # トークンが既に有効か確認
        if self.access_token and self.token_expiry and datetime.now() < self.token_expiry:
            logger.debug("既存のトークンが有効です")
            return self.access_token
            
        logger.info("新しいアクセストークンを取得しています")
        auth = HTTPBasicAuth(self.client_id, self.client_secret)
        try:
            response = self.session.post(
                f"{self.base_url}/oauth/token", 
                auth=auth, 
                data={'grant_type': 'client_credentials', 'scope': '*'},
                timeout=self.timeout
            )
            response.raise_for_status()
            token_data = response.json()
            self.access_token = token_data['access_token']
            
            # トークンの有効期限を設定（データに含まれている場合）
            if 'expires_in' in token_data:
                # 安全マージンとして10秒引く
                expiry_seconds = int(token_data['expires_in']) - 10
                self.token_expiry = datetime.now().replace(microsecond=0) + \
                                   datetime.timedelta(seconds=expiry_seconds)
                logger.info(f"トークンの有効期限: {self.token_expiry}")
            
            return self.access_token
        except requests.exceptions.RequestException as e:
            logger.error(f"トークン取得エラー: {str(e)}", exc_info=True)
            raise

    @retry_decorator(max_retries=4, backoff_factor=0.5)
    def make_api_request(self, endpoint, method='GET', data=None, params=None):
        """改善されたAPI要求メソッド - より良いエラー処理と検証を含む"""
        if not self.access_token:
            self.get_access_token()

        # リクエストごとに新しいヘッダーを設定
        headers = {'Authorization': f'Bearer {self.access_token}'}
        url = f"{self.base_url}{endpoint}"
        
        # リクエスト試行をログに記録
        logger.info(f"APIリクエスト: {method} {url}")
        if data:
            logger.debug(f"リクエストデータ: {json.dumps(data, ensure_ascii=False)[:500]}")

        try:
            response = self.session.request(
                method, 
                url, 
                headers=headers, 
                json=data,
                params=params,
                timeout=self.timeout
            )
            
            # 認証関連エラーの詳細なハンドリング
            if response.status_code in (401, 403, 419):
                logger.warning(f"認証エラー ({response.status_code}): アクセストークンを更新します")
                self.access_token = None  # トークンをリセット
                self.get_access_token()
                headers['Authorization'] = f'Bearer {self.access_token}'
                # リトライ
                response = self.session.request(
                    method, 
                    url, 
                    headers=headers, 
                    json=data,
                    params=params,
                    timeout=self.timeout
                )
            
            # その他のエラーチェック
            response.raise_for_status()
            
            # レスポンスの検証
            result = response.json()
            logger.debug(f"レスポンス: {json.dumps(result, ensure_ascii=False)[:500]} ...")
            return result
            
        except requests.exceptions.Timeout:
            logger.error(f"APIリクエストがタイムアウトしました: {url}", exc_info=True)
            raise
        except requests.exceptions.ConnectionError:
            logger.error(f"API接続エラー: {url}", exc_info=True)
            raise
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTPエラー: {e} - {url}", exc_info=True)
            # レスポンスボディをログに記録（可能な場合）
            try:
                logger.error(f"エラーレスポンス: {e.response.text}")
            except:
                pass
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"APIリクエストエラー: {str(e)}", exc_info=True)
            raise
        except json.JSONDecodeError:
            logger.error(f"JSONデコードエラー。有効なJSONレスポンスではありません: {url}", exc_info=True)
            raise

def check_api_health(client):
    """拡張されたAPIヘルスチェック機能"""
    health_status = {
        "status": "error",
        "timestamp": datetime.now().isoformat(),
        "checks": {}
    }
    
    try:
        # アクセストークン取得テスト
        start_time = time.time()
        client.get_access_token()
        token_time = time.time() - start_time
        health_status["checks"]["auth"] = {
            "status": "ok",
            "response_time": token_time
        }
        
        # APIエンドポイントテスト
        endpoints_to_check = [
            ('/api/user', 'GET'),
            # 他のエンドポイントを必要に応じて追加
        ]
        
        for endpoint, method in endpoints_to_check:
            start_time = time.time()
            try:
                result = client.make_api_request(endpoint, method=method)
                response_time = time.time() - start_time
                
                health_status["checks"][endpoint] = {
                    "status": "ok",
                    "response_time": response_time
                }
                logger.info(f"ヘルスチェック成功: {endpoint} - レスポンスタイム: {response_time:.2f}秒")
            except Exception as e:
                health_status["checks"][endpoint] = {
                    "status": "error",
                    "error": str(e)
                }
                logger.error(f"ヘルスチェック失敗: {endpoint} - エラー: {str(e)}")
        
        # 全体のステータスを設定
        errors = [check for check in health_status["checks"].values() if check["status"] == "error"]
        health_status["status"] = "error" if errors else "ok"
        
        return health_status
    except Exception as e:
        logger.error(f"ヘルスチェック中の予期しないエラー: {str(e)}", exc_info=True)
        health_status["error"] = str(e)
        return health_status

if __name__ == "__main__":
    # 環境変数から設定を読み込み
    url_to_check = os.environ.get("API_BASE_URL")
    client_id = os.environ.get("CLIENT_ID")
    client_secret = os.environ.get("CLIENT_SECRET")
    
    # タイムアウト設定（オプション）
    timeout = int(os.environ.get("API_TIMEOUT", 10))

    if all([url_to_check, client_id, client_secret]):
        try:
            client = APIClient(url_to_check, client_id, client_secret, timeout=timeout)
            health_result = check_api_health(client)
            
            # 結果をログと標準出力に出力
            logger.info(f"APIヘルスチェック結果: {json.dumps(health_result, ensure_ascii=False, indent=2)}")
            print(json.dumps(health_result, ensure_ascii=False, indent=2))
            
            # 終了ステータスの設定
            exit_code = 0 if health_result.get("status") == "ok" else 1
            exit(exit_code)
        except Exception as e:
            logger.critical(f"クリティカルエラー: {str(e)}", exc_info=True)
            exit(2)
    else:
        logger.error("必要な環境変数が設定されていません。API_BASE_URL, CLIENT_ID, CLIENT_SECRETが必要です。")
        print("エラー: 必要な環境変数が設定されていません")
        exit(3)

## 主な改善点

1. **接続管理の強化**:
   - `requests.Session`を使用して接続プーリングを実装
   - すべてのリクエストにタイムアウト設定を追加

2. **エラー処理の強化**:
   - より詳細なエラータイプの捕捉と処理
   - 401だけでなく403や419などの認証エラーも処理
   - JSONデコードエラーのハンドリング追加

3. **トークン管理の向上**:
   - トークンの有効期限を追跡して不要な再取得を防止
   - トークン更新のロジックを改善

4. **ロギングの強化**:
   - ファイルとコンソールの両方にログを出力
   - より詳細なコンテキスト情報を含むログ形式
   - エラー時のスタックトレース記録

5. **ヘルスチェックの強化**:
   - 複数のエンドポイントをチェック可能
   - レスポンスタイムの測定と記録
   - 構造化された健全性レポートの作成

6. **リソース管理**:
   - セッションの適切なクローズ処理
   - 終了コードによる状態通知

7. **全般的な改善**:
   - 日本語のエラーメッセージとログで理解しやすく
   - 文書化されたコード

これらの改善により、コードの可用性、回復力、およびモニタリング能力が大幅に向上します。​​​​​​​​​​​​​​​​
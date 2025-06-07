import requests
import logging
import os
import json
import re
from requests.exceptions import RequestException, JSONDecodeError, Timeout
from typing import Dict, Optional, Tuple
from urllib.parse import urlparse
import time

# ロギングの設定（機密情報をフィルタリング）
class SensitiveDataFilter(logging.Filter):
    """機密情報をログから除外するフィルター"""
    def filter(self, record):
        # トークン、パスワード、キーなどの機密情報をマスク
        if hasattr(record, 'msg'):
            record.msg = re.sub(
                r'(Bearer\s+|token["\']:\s*["\']|password["\']:\s*["\']|key["\']:\s*["\'])[\w\-\.]+',
                r'\1***MASKED***',
                str(record.msg),
                flags=re.IGNORECASE
            )
        return True

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
logger.addFilter(SensitiveDataFilter())

def validate_url(url: str) -> bool:
    """URLの妥当性とHTTPSの確認"""
    try:
        parsed = urlparse(url)
        if parsed.scheme != 'https':
            logger.error("HTTPSでないURLは使用できません")
            return False
        if not parsed.netloc:
            logger.error("無効なURLです")
            return False
        return True
    except Exception:
        return False

def sanitize_response_data(data: Dict) -> Dict:
    """レスポンスデータから機密情報を除去"""
    sanitized = data.copy()
    sensitive_keys = ['token', 'password', 'secret', 'key', 'authorization', 'auth']
    
    def _sanitize_dict(d):
        if isinstance(d, dict):
            for key in list(d.keys()):
                if any(sensitive in key.lower() for sensitive in sensitive_keys):
                    d[key] = "***MASKED***"
                elif isinstance(d[key], (dict, list)):
                    _sanitize_dict(d[key])
        elif isinstance(d, list):
            for item in d:
                _sanitize_dict(item)
    
    _sanitize_dict(sanitized)
    return sanitized

def retry_request(max_retries: int = 3, backoff_factor: float = 0.3) -> callable:
    def decorator(func):
        def wrapper(*args, **kwargs):
            retries = 0
            while retries < max_retries:
                try:
                    return func(*args, **kwargs)
                except (RequestException, Timeout) as e:
                    retries += 1
                    if retries == max_retries:
                        logger.error(f"最大リトライ回数に達しました。エラー: {type(e).__name__}")
                        raise
                    wait_time = backoff_factor * (2 ** (retries - 1))
                    logger.warning(f"リトライ {retries}/{max_retries} - {wait_time:.2f}秒後に再試行")
                    time.sleep(wait_time)
        return wrapper
    return decorator

@retry_request()
def make_request(url: str, method: str, headers: Optional[Dict] = None, data: Optional[Dict] = None, timeout: int = 30) -> Tuple[int, Dict]:
    """セキュアなHTTPリクエスト実行"""
    
    # URL検証
    if not validate_url(url):
        raise ValueError("無効または安全でないURLです")
    
    # デフォルトヘッダーの設定
    default_headers = {
        'User-Agent': 'SecureAPIClient/1.0',
        'Accept': 'application/json',
        'Content-Type': 'application/json'
    }
    
    if headers:
        default_headers.update(headers)
    
    try:
        # セキュアなリクエスト設定
        response = requests.request(
            method=method.upper(),
            url=url,
            headers=default_headers,
            json=data,
            timeout=timeout,
            verify=True,  # SSL証明書の検証を強制
            allow_redirects=False  # リダイレクトを無効化（セキュリティ向上）
        )
        
        # レスポンスサイズの制限（DoS攻撃対策）
        max_response_size = 10 * 1024 * 1024  # 10MB
        if len(response.content) > max_response_size:
            raise ValueError("レスポンスサイズが上限を超えています")
        
        try:
            response_data = response.json()
        except JSONDecodeError:
            logger.warning("JSONデコードに失敗しました。空のレスポンスを返します")
            response_data = {}
        
        return response.status_code, response_data
        
    except Timeout:
        logger.error("リクエストがタイムアウトしました")
        raise
    except RequestException as e:
        logger.error(f"リクエストエラー: {type(e).__name__}")
        raise

def check_for_405_error(api_url: str, http_method: str, headers: Optional[Dict] = None, 
                       data: Optional[Dict] = None, timeout: int = 30) -> bool:
    """405エラーのチェック（セキュリティ強化版）"""
    try:
        status_code, response_data = make_request(api_url, http_method, headers, data, timeout)
        
        if status_code == 405:
            logger.warning(f"405 Method Not Allowed: {http_method} -> {api_url}")
            
            # レスポンスデータをサニタイズしてログ出力
            sanitized_data = sanitize_response_data(response_data)
            logger.info(f"サニタイズ済みレスポンス: {json.dumps(sanitized_data, ensure_ascii=False)}")
            
            # 許可されているメソッドを確認
            allowed_methods = response_data.get('allowed_methods', [])
            if allowed_methods:
                logger.info(f"許可されているHTTPメソッド: {', '.join(allowed_methods)}")
            
            # エラーメッセージの取得（機密情報を除外）
            error_message = response_data.get('message', 'エラーメッセージが提供されていません')
            # 機密情報を含む可能性のあるメッセージをフィルタリング
            if len(error_message) > 500:  # 長すぎるメッセージは切り捨て
                error_message = error_message[:500] + "..."
            logger.info(f"エラーメッセージ: {error_message}")
            
            return True
            
        elif status_code == 200:
            logger.info(f"リクエスト成功 - ステータスコード: {status_code}")
        else:
            logger.warning(f"予期しないステータスコード: {status_code}")
            sanitized_data = sanitize_response_data(response_data)
            logger.info(f"レスポンス: {json.dumps(sanitized_data, ensure_ascii=False)}")
        
        return False
    
    except Exception as e:
        logger.error(f"リクエスト失敗: {type(e).__name__}")
        return False

def get_secure_headers() -> Dict[str, str]:
    """環境変数から安全にヘッダーを取得"""
    token = os.getenv('API_ACCESS_TOKEN')
    if not token:
        logger.error("API_ACCESS_TOKEN環境変数が設定されていません")
        raise ValueError("アクセストークンが設定されていません")
    
    # トークンの形式を簡単に検証
    if len(token) < 10:
        logger.error("アクセストークンが短すぎます")
        raise ValueError("無効なアクセストークン")
    
    return {"Authorization": f"Bearer {token}"}

if __name__ == "__main__":
    # 環境変数から設定を取得
    api_url_to_check = os.getenv('API_URL', 'https://api.example.com/endpoint')
    http_method_to_check = os.getenv('HTTP_METHOD', 'GET').upper()
    timeout = int(os.getenv('REQUEST_TIMEOUT', '30'))
    
    # HTTPメソッドの検証
    allowed_methods = ['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'HEAD', 'OPTIONS']
    if http_method_to_check not in allowed_methods:
        logger.error(f"サポートされていないHTTPメソッド: {http_method_to_check}")
        exit(1)
    
    try:
        headers = get_secure_headers()
        
        logger.info(f"APIエンドポイントのチェック開始: {http_method_to_check} {api_url_to_check}")
        
        is_405_error = check_for_405_error(
            api_url_to_check, 
            http_method_to_check, 
            headers, 
            timeout=timeout
        )
        
        if is_405_error:
            logger.info("正しいHTTPメソッドを使用するようAPIコールを更新してください")
            exit(1)
        else:
            logger.info("405エラーは検出されませんでした。APIコールは正しいHTTPメソッドを使用しています")
            exit(0)
            
    except Exception as e:
        logger.error(f"実行エラー: {type(e).__name__}")
        exit(2)
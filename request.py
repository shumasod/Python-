import requests
import json
from requests.exceptions import RequestException, Timeout, ConnectionError

def send_request(self, url, data, defaultHeaders, timeout=30):
    """
    HTTPリクエストを送信し、レスポンスを処理する
    
    Args:
        url (str): リクエスト先URL
        data (dict): 送信するデータ
        defaultHeaders (dict): リクエストヘッダー
        timeout (int): タイムアウト時間（秒）
    
    Returns:
        dict: レスポンスデータ
    """
    res = None
    
    try:
        # Content-Typeヘッダーを適切に設定
        headers = defaultHeaders.copy()
        if 'Content-Type' not in headers:
            headers['Content-Type'] = 'application/json'
        
        # requestsのjsonパラメータを使用してJSONを送信
        response = requests.post(
            url,
            json=data,  # dataパラメータではなくjsonパラメータを使用
            headers=headers,
            timeout=timeout
        )
        
        # HTTPステータスコードをチェック
        response.raise_for_status()
        
        # JSONレスポンスをパース
        res = response.json()
        
        self.logger.log("INFO", logGroup, f"Request successful. Status: {response.status_code}")
        
    except Timeout:
        self.logger.log("ERROR", logGroup, f"Request timeout after {timeout} seconds")
        res = {
            "status": 408,
            "summary": "リクエストタイムアウト",
            "error": "timeout"
        }
        
    except ConnectionError:
        self.logger.log("ERROR", logGroup, f"Connection error to {url}")
        res = {
            "status": 503,
            "summary": "接続エラー",
            "error": "connection_error"
        }
        
    except requests.exceptions.HTTPError as e:
        self.logger.log("ERROR", logGroup, f"HTTP error: {e.response.status_code} - {e}")
        res = {
            "status": e.response.status_code,
            "summary": f"HTTPエラー: {e.response.status_code}",
            "error": "http_error"
        }
        
    except json.JSONDecodeError:
        self.logger.log("ERROR", logGroup, "Failed to decode JSON response")
        res = {
            "status": 502,
            "summary": "不正なレスポンス形式",
            "error": "json_decode_error"
        }
        
    except RequestException as e:
        self.logger.log("ERROR", logGroup, f"Request failed: {e}")
        res = {
            "status": 500,
            "summary": "リクエストエラー",
            "error": "request_error"
        }
        
    except Exception as e:
        self.logger.log("ERROR", logGroup, f"Unexpected error: {e}")
        res = {
            "status": 999,
            "summary": "システムエラー",
            "error": "unexpected_error"
        }
    
    return res


# さらなる改善版：リトライ機能付き
import time
from functools import wraps

def with_retry(max_retries=3, backoff_factor=1):
    """リトライ機能を追加するデコレータ"""
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(self, *args, **kwargs)
                except (ConnectionError, Timeout) as e:
                    last_exception = e
                    if attempt < max_retries:
                        wait_time = backoff_factor * (2 ** attempt)
                        self.logger.log("WARN", logGroup, 
                                       f"Attempt {attempt + 1} failed, retrying in {wait_time}s: {e}")
                        time.sleep(wait_time)
                    else:
                        self.logger.log("ERROR", logGroup, 
                                       f"All {max_retries + 1} attempts failed")
                        break
                except Exception as e:
                    # 致命的なエラーはリトライしない
                    raise e
            
            # リトライが全て失敗した場合
            return {
                "status": 503,
                "summary": "接続失敗（リトライ回数上限）",
                "error": "max_retries_exceeded"
            }
        return wrapper
    return decorator

class APIClient:
    @with_retry(max_retries=3, backoff_factor=1)
    def send_request_with_retry(self, url, data, defaultHeaders, timeout=30):
        """リトライ機能付きのHTTPリクエスト送信"""
        return self.send_request(url, data, defaultHeaders, timeout)

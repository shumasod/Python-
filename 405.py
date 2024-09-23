import requests
import logging
from requests.exceptions import RequestException
from typing import Dict, Optional, Tuple
import time

# ロギングの設定
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def retry_request(max_retries: int = 3, backoff_factor: float = 0.3) -> callable:
    def decorator(func):
        def wrapper(*args, **kwargs):
            retries = 0
            while retries < max_retries:
                try:
                    return func(*args, **kwargs)
                except RequestException as e:
                    retries += 1
                    if retries == max_retries:
                        logger.error(f"Max retries reached. Error: {e}")
                        raise
                    wait_time = backoff_factor * (2 ** (retries - 1))
                    logger.warning(f"Retry {retries}/{max_retries} after {wait_time:.2f} seconds")
                    time.sleep(wait_time)
        return wrapper
    return decorator

@retry_request()
def make_request(url: str, method: str, headers: Optional[Dict] = None, data: Optional[Dict] = None) -> Tuple[int, Dict]:
    response = requests.request(method, url, headers=headers, json=data)
    return response.status_code, response.json()

def check_for_405_error(api_url: str, http_method: str, headers: Optional[Dict] = None, data: Optional[Dict] = None) -> bool:
    try:
        status_code, response_data = make_request(api_url, http_method, headers, data)
        
        if status_code == 405:
            logger.warning(f"405 Method Not Allowed error detected for {http_method} request to {api_url}")
            logger.info(f"Response data: {response_data}")
            
            # 許可されているメソッドを確認
            allowed_methods = response_data.get('allowed_methods', [])
            if allowed_methods:
                logger.info(f"Allowed HTTP methods for this endpoint: {', '.join(allowed_methods)}")
            
            # エラーメッセージの取得
            error_message = response_data.get('message', 'No specific error message provided')
            logger.info(f"Error message: {error_message}")
            
            return True
        elif status_code == 200:
            logger.info(f"Request successful. Status code: {status_code}")
        else:
            logger.warning(f"Unexpected status code: {status_code}")
            logger.info(f"Response data: {response_data}")
        
        return False
    
    except RequestException as e:
        logger.error(f"Request failed: {e}")
        return False

if __name__ == "__main__":
    api_url_to_check = "https://example.com/api/endpoint"
    http_method_to_check = "GET"
    headers = {"Authorization": "Bearer your_access_token_here"}
    
    is_405_error = check_for_405_error(api_url_to_check, http_method_to_check, headers)
    
    if is_405_error:
        logger.info("Consider updating your API call to use the correct HTTP method.")
    else:
        logger.info("No 405 error detected. Your API call seems to be using the correct HTTP method.")

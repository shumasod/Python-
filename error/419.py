import os
import requests
from requests.auth import HTTPBasicAuth
import time
from functools import wraps
import logging

# ロギングの設定
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def retry_decorator(max_retries=3, backoff_factor=0.3):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            retries = 0
            while retries < max_retries:
                try:
                    return func(*args, **kwargs)
                except requests.exceptions.RequestException as e:
                    retries += 1
                    if retries == max_retries:
                        logger.error(f"Max retries reached. Error: {e}")
                        raise
                    wait_time = backoff_factor * (2 ** (retries - 1))
                    logger.warning(f"Retry {retries}/{max_retries} after {wait_time:.2f} seconds")
                    time.sleep(wait_time)
        return wrapper
    return decorator

class APIClient:
    def __init__(self, base_url, client_id, client_secret):
        self.base_url = base_url
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token = None

    @retry_decorator()
    def get_access_token(self):
        auth = HTTPBasicAuth(self.client_id, self.client_secret)
        response = requests.post(f"{self.base_url}/oauth/token", 
                                 auth=auth, 
                                 data={'grant_type': 'client_credentials', 'scope': '*'})
        response.raise_for_status()
        self.access_token = response.json()['access_token']
        return self.access_token

    @retry_decorator()
    def make_api_request(self, endpoint, method='GET', data=None):
        if not self.access_token:
            self.get_access_token()

        headers = {'Authorization': f'Bearer {self.access_token}'}
        url = f"{self.base_url}{endpoint}"

        response = requests.request(method, url, headers=headers, json=data)
        
        if response.status_code == 419:
            logger.warning("419 Unknown error detected. Refreshing access token.")
            self.get_access_token()
            headers['Authorization'] = f'Bearer {self.access_token}'
            response = requests.request(method, url, headers=headers, json=data)
        
        response.raise_for_status()
        return response.json()

def check_api_health(client):
    try:
        result = client.make_api_request('/api/user')
        logger.info("API request successful.")
        return result
    except requests.exceptions.RequestException as e:
        logger.error(f"API request failed: {e}")
        return None

if __name__ == "__main__":
    url_to_check = os.environ.get("URL_TO_CHECK")
    client_id = os.environ.get("CLIENT_ID")
    client_secret = os.environ.get("CLIENT_SECRET")

    if all([url_to_check, client_id, client_secret]):
        client = APIClient(url_to_check, client_id, client_secret)
        result = check_api_health(client)
        if result:
            logger.info(f"API health check passed. User data: {result}")
    else:
        logger.error("Environment variables are not set correctly.")

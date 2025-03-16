import time
import requests
from bs4 import BeautifulSoup
import logging
import os

# ロギングの設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# 定数
URL = "https://example.com"
CLASS_NAME = 'div.newUserPageProfile_info_body.newUserPageProfile_description'
FILE = "elems_text.txt"
CHECK_INTERVAL = 20  # 秒

def is_changed(old_elem, new_elem):
    """要素が変更されたかどうかを確認します"""
    return old_elem != new_elem

def set_old_elems():
    """保存されている以前の要素を取得します"""
    try:
        if os.path.exists(FILE) and os.path.getsize(FILE) > 0:
            with open(FILE, 'r', encoding='utf-8') as f:
                old_elems = f.read()
                logging.info(f'Old element: {old_elems[:100]}...' if len(old_elems) > 100 else f'Old element: {old_elems}')
        else:
            old_elems = ''
            logging.info('No previous elements found or file is empty')
        return old_elems
    except Exception as e:
        logging.error(f"Error reading file: {e}")
        return ''

def set_new_elems():
    """ウェブサイトから新しい要素を取得します"""
    try:
        response = requests.get(URL, timeout=10)
        response.raise_for_status()  # HTTPエラーがあれば例外を発生させる
        
        response.encoding = response.apparent_encoding
        bs = BeautifulSoup(response.text, 'html.parser')
        elements = bs.select(CLASS_NAME)
        
        if not elements:
            logging.warning(f"No elements found with selector: {CLASS_NAME}")
            return ""
            
        new_elems = str(elements)
        logging.info(f'New element: {new_elems[:100]}...' if len(new_elems) > 100 else f'New element: {new_elems}')
        return new_elems
    except requests.RequestException as e:
        logging.error(f"Request error: {e}")
        return None
    except Exception as e:
        logging.error(f"Error fetching elements: {e}")
        return None

def display_result(old_elem, new_elem):
    """結果を表示し、必要に応じてファイルを更新します"""
    if new_elem is None:
        logging.warning("Cannot compare elements due to fetch error")
        return
        
    try:
        if is_changed(old_elem, new_elem):
            with open(FILE, 'w', encoding='utf-8') as f:
                f.write(new_elem)
            logging.info("Change detected! File updated.")
        else:
            logging.info("No changes detected")
    except IOError as e:
        logging.error(f"Error writing to file: {e}")

def main():
    """メイン処理ループ"""
    logging.info("Starting website change monitoring...")
    try:
        while True:
            logging.info("=" * 50)
            new_elems = set_new_elems()
            old_elems = set_old_elems()
            display_result(old_elems, new_elems)
            logging.info(f"Waiting {CHECK_INTERVAL} seconds before next check...")
            time.sleep(CHECK_INTERVAL)
    except KeyboardInterrupt:
        logging.info("Monitoring stopped by user")
    except Exception as e:
        logging.error(f"Unexpected error: {e}")

if __name__ == '__main__':
    main()

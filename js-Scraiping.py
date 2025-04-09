#!/usr/bin/env python3
import time
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException, NoSuchElementException

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def setup_chrome_options():
    """スクレイピングに最適化されたChromeオプションを設定する"""
    chrome_options = Options()
    
    # ヘッドレスモード設定
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    
    # 検出回避のための追加設定
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    
    # 一般的なユーザーエージェントを設定
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    # 自動化フラグを無効化
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)
    
    # 画像読み込みを無効化（オプション - パフォーマンス向上のため）
    # chrome_options.add_argument("--blink-settings=imagesEnabled=false")
    
    return chrome_options

def scrape_with_selenium(url, max_retries=3, wait_time=15):
    """
    Seleniumを使用してWebページの内容をスクレイピングする
    
    引数:
        url (str): スクレイピング対象のURL
        max_retries (int): 最大再試行回数
        wait_time (int): 最大待機時間（秒）
        
    戻り値:
        dict: タイトルと内容を含む辞書、失敗した場合はNone
    """
    retry_count = 0
    driver = None
    
    while retry_count < max_retries:
        try:
            logger.info(f"スクレイピング開始: {url} (試行 {retry_count + 1}/{max_retries})")
            
            # Chromeの設定
            chrome_options = setup_chrome_options()
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
            
            # タイムアウト設定
            driver.set_page_load_timeout(wait_time)
            
            # URLにアクセス
            logger.info(f"URLにアクセス中: {url}")
            driver.get(url)
            
            # ページが読み込まれるのを待機
            WebDriverWait(driver, wait_time).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # 動的コンテンツのためにさらに少し待機
            time.sleep(2)
            
            # ページタイトルを取得
            title = driver.title
            logger.info(f"ページタイトル: {title}")
            
            # スクレイピング戦略1: 段落要素を試みる
            paragraph_elements = driver.find_elements(By.TAG_NAME, 'p')
            
            if paragraph_elements:
                logger.info(f"{len(paragraph_elements)}個の段落要素が見つかりました")
                paragraph_texts = [p.text for p in paragraph_elements if p.text.strip()]
                
                result = {
                    "title": title,
                    "paragraphs": paragraph_texts,
                    "url": url
                }
                logger.info(f"スクレイピング成功: {len(paragraph_texts)}個のテキスト要素を取得")
                return result
            else:
                logger.warning("段落要素が見つかりませんでした、別の方法を試みます")
                
                # スクレイピング戦略2: div要素に含まれるテキストを試みる
                div_elements = driver.find_elements(By.TAG_NAME, 'div')
                div_texts = [div.text for div in div_elements if div.text.strip() and len(div.text) > 30]
                
                # スクレイピング戦略3: 記事や主要コンテンツを探す
                article_elements = driver.find_elements(By.TAG_NAME, 'article')
                if article_elements:
                    logger.info("記事要素が見つかりました")
                    article_texts = [article.text for article in article_elements if article.text.strip()]
                    div_texts = article_texts + div_texts
                
                # 主要なクラス名を持つ要素を探す
                content_candidates = [
                    "content", "main", "article", "post", "entry", "blog", 
                    "text", "body", "container"
                ]
                
                for candidate in content_candidates:
                    elements = driver.find_elements(By.CSS_SELECTOR, f".{candidate}")
                    if elements:
                        logger.info(f"'{candidate}'クラスの要素が見つかりました")
                        for element in elements:
                            if element.text.strip() and len(element.text) > 50:
                                div_texts.append(element.text)
                
                # 結果を返す
                result = {
                    "title": title,
                    "paragraphs": div_texts if div_texts else ["テキストコンテンツが見つかりませんでした"],
                    "url": url
                }
                
                logger.info(f"代替スクレイピング成功: {len(div_texts)}個のテキスト要素を取得")
                return result
                
        except TimeoutException:
            logger.warning(f"ページ読み込み中にタイムアウトが発生しました (試行 {retry_count + 1}/{max_retries})")
            retry_count += 1
            time.sleep(3)  # 再試行前に少し待機
            
        except WebDriverException as e:
            logger.error(f"WebDriverエラー: {str(e)}")
            retry_count += 1
            time.sleep(3)
            
        except Exception as e:
            logger.error(f"予期しないエラーが発生しました: {str(e)}", exc_info=True)
            retry_count += 1
            time.sleep(3)
            
        finally:
            # ブラウザを閉じる
            if driver:
                try:
                    driver.quit()
                    logger.info("ブラウザを閉じました")
                except Exception:
                    pass
    
    logger.error(f"{max_retries}回の試行後にスクレイピングに失敗しました: {url}")
    return None

def print_scrape_results(result):
    """スクレイピング結果を表示する"""
    if not result:
        print("スクレイピング結果がありません")
        return
    
    print("\n" + "="*60)
    print(f"スクレイピング結果: {result['url']}")
    print("="*60)
    print(f"ページタイトル: {result['title']}")
    print(f"取得したテキスト要素数: {len(result['paragraphs'])}")
    
    print("\n内容サンプル:")
    print("-"*60)
    for i, para in enumerate(result['paragraphs'][:3], 1):
        # 各段落の最初の100文字を表示
        if para:
            print(f"{i}. {para[:100]}{'...' if len(para) > 100 else ''}")
    print("="*60)

if __name__ == "__main__":
    target_url = "https://example.com"  # スクレイピングしたいサイトのURLを指定
    result = scrape_with_selenium(target_url)
    
    if result:
        print_scrape_results(result)
    else:
        print("スクレイピングに失敗しました。ログを確認してください。")

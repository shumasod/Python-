from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import time

def scrape_with_selenium(url):
    # Chromeオプションの設定
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # ヘッドレスモードで実行

    # WebDriverの設定
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)

    try:
        # ウェブページにアクセス
        driver.get(url)
        
        # ページの読み込みを待つ
        time.sleep(5)

        # タイトルを取得
        title = driver.title

        # 全ての段落要素を取得
        paragraphs = driver.find_elements(By.TAG_NAME, 'p')
        paragraph_texts = [p.text for p in paragraphs]

        return {
            "title": title,
            "paragraphs": paragraph_texts
        }

    finally:
        # ブラウザを閉じる
        driver.quit()

# 使用例
if __name__ == "__main__":
    url = "https://example.com"  # スクレイピングしたいウェブサイトのURLを指定
    result = scrape_with_selenium(url)
    
    print(f"ページタイトル: {result['title']}")
    print("\n最初の3つの段落:")
    for i, para in enumerate(result['paragraphs'][:3], 1):
        print(f"{i}. {para[:100]}...")  # 各段落の最初の100文字のみを表示
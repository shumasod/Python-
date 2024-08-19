import requests
from bs4 import BeautifulSoup

def scrape_website(url):
    # ウェブページの内容を取得
    response = requests.get(url)
    
    # レスポンスが成功したか確認
    if response.status_code == 200:
        # BeautifulSoupオブジェクトを作成
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 例: ページのタイトルを取得
        title = soup.title.string if soup.title else "タイトルなし"
        
        # 例: すべての段落テキストを取得
        paragraphs = [p.text for p in soup.find_all('p')]
        
        return {
            "title": title,
            "paragraphs": paragraphs
        }
    else:
        return f"エラー: ステータスコード {response.status_code}"

# 使用例
if __name__ == "__main__":
    url = "https://example.com"  # スクレイピングしたいウェブサイトのURLを指定
    result = scrape_website(url)
    
    print(f"ページタイトル: {result['title']}")
    print("\n最初の3つの段落:")
    for i, para in enumerate(result['paragraphs'][:3], 1):
        print(f"{i}. {para[:100]}...")  # 各段落の最初の100文字のみを表示
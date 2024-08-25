import pandas as pd
import requests
from bs4 import BeautifulSoup
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score
import time
import re

class JRAPredictionApp:
    def __init__(self):
        self.model = RandomForestClassifier()
        self.data = None

    def scrape_data(self, base_url, num_pages=5):
        all_data = []
        for page in range(1, num_pages + 1):
            url = f"{base_url}&page={page}"
            print(f"Scraping page {page}...")
            response = requests.get(url)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            race_tables = soup.find_all('table', class_='race_table_01')
            for table in race_tables:
                race_data = self.extract_race_data(table)
                all_data.extend(race_data)
            
            time.sleep(1)  # サーバーに負荷をかけないよう待機
        
        self.data = pd.DataFrame(all_data)
        print(f"{len(all_data)}件のデータを取得しました。")

    def extract_race_data(self, table):
        race_data = []
        rows = table.find_all('tr')
        for row in rows[1:]:  # ヘッダーをスキップ
            cols = row.find_all('td')
            if len(cols) > 0:
                horse_data = {
                    '着順': self.clean_text(cols[0].text),
                    '枠番': self.clean_text(cols[1].text),
                    '馬番': self.clean_text(cols[2].text),
                    '馬名': self.clean_text(cols[3].text),
                    '性齢': self.clean_text(cols[4].text),
                    '斤量': self.clean_text(cols[5].text),
                    '騎手': self.clean_text(cols[6].text),
                    'タイム': self.clean_text(cols[7].text),
                    '着差': self.clean_text(cols[8].text),
                    '人気': self.clean_text(cols[9].text),
                    '単勝': self.clean_text(cols[10].text),
                    '馬体重': self.extract_weight(cols[14].text),
                    '増減': self.extract_weight_change(cols[14].text),
                }
                race_data.append(horse_data)
        return race_data

    def clean_text(self, text):
        return re.sub(r'\s+', '', text.strip())

    def extract_weight(self, text):
        match = re.search(r'(\d+)', text)
        return match.group(1) if match else None

    def extract_weight_change(self, text):
        match = re.search(r'\((.*?)\)', text)
        return match.group(1) if match else None

    def preprocess_data(self):
        # データ型の変換
        numeric_cols = ['着順', '枠番', '馬番', '斤量', '人気', '単勝', '馬体重', '増減']
        for col in numeric_cols:
            self.data[col] = pd.to_numeric(self.data[col], errors='coerce')
        
        # 'タイム'を秒に変換
        self.data['タイム'] = self.data['タイム'].apply(self.time_to_seconds)
        
        # One-hot encoding for '性齢' and '騎手'
        self.data = pd.get_dummies(self.data, columns=['性齢', '騎手'])
        
        # '増減'の符号を数値に変換
        self.data['増減'] = self.data['増減'].apply(self.sign_to_number)
        
        self.data = self.data.dropna()
        print("データの前処理が完了しました。")

    def time_to_seconds(self, time_str):
        parts = time_str.split(':')
        if len(parts) == 2:
            return int(parts[0]) * 60 + float(parts[1])
        return None

    def sign_to_number(self, value):
        if pd.isna(value):
            return 0
        elif value.startswith('+'):
            return float(value[1:])
        elif value.startswith('-'):
            return -float(value[1:])
        else:
            return 0

    def train_model(self):
        X = self.data.drop(['着順', '馬名', '着差'], axis=1)
        y = self.data['着順']
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        
        self.model.fit(X_train, y_train)
        y_pred = self.model.predict(X_test)
        accuracy = accuracy_score(y_test, y_pred)
        print(f"モデルの精度: {accuracy:.2f}")

    def predict(self, horse_data):
        prediction = self.model.predict(horse_data)
        return prediction

    def run(self):
        print("競馬予想アプリへようこそ！")
        base_url = input("の結果ページのベースURLを入力してください: ")
        num_pages = int(input("スクレイピングするページ数を入力してください: "))
        self.scrape_data(base_url, num_pages)
        self.preprocess_data()
        self.train_model()

        while True:
            print("\n1: 予測を行う")
            print("2: 終了")
            choice = input("選択してください (1/2): ")
            
            if choice == '1':
                horse_data = self.get_horse_input()
                prediction = self.predict(horse_data)
                print(f"予測結果: {prediction[0]:.0f}着")
            elif choice == '2':
                print("アプリケーションを終了します。")
                break
            else:
                print("無効な選択です。もう一度お試しください。")

    def get_horse_input(self):
        horse_data = pd.DataFrame({
            '枠番': [int(input("枠番を入力してください: "))],
            '馬番': [int(input("馬番を入力してください: "))],
            '斤量': [float(input("斤量を入力してください: "))],
            '人気': [int(input("人気を入力してください: "))],
            '単勝': [float(input("単勝オッズを入力してください: "))],
            '馬体重': [int(input("馬体重を入力してください: "))],
            '増減': [float(input("増減を入力してください（増加は正、減少は負の数）: "))],
        })

        # One-hot encoding for '性齢' and '騎手'
        性齢 = input("性齢を入力してください (例: 牡3): ")
        騎手 = input("騎手名を入力してください: ")
        for col in self.data.columns:
            if col.startswith('性齢_'):
                horse_data[col] = [1 if col == f'性齢_{性齢}' else 0]
            elif col.startswith('騎手_'):
                horse_data[col] = [1 if col == f'騎手_{騎手}' else 0]

        return horse_data

    # 各プロセスを独立して実行するための関数
    def run_scraping(self, base_url, num_pages):
        self.scrape_data(base_url, num_pages)

    def run_preprocessing(self):
        self.preprocess_data()

    def run_training(self):
        self.train_model()

    def run_prediction(self, horse_data):
        return self.predict(horse_data)

if __name__ == "__main__":
    app = JRAPredictionApp()
    app.run()

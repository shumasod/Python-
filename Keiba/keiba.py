import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score

class JRAPredictionAppTest:
    def __init__(self):
        self.app = JRAPredictionApp()
        self.mock_data = None

    def create_mock_data(self):
        np.random.seed(42)
        n_samples = 1000
        self.mock_data = pd.DataFrame({
            '着順': np.random.randint(1, 20, n_samples),
            '枠番': np.random.randint(1, 9, n_samples),
            '馬番': np.random.randint(1, 20, n_samples),
            '馬名': [f'Horse_{i}' for i in range(n_samples)],
            '性齢': np.random.choice(['牡2', '牡3', '牡4', '牡5', '牝2', '牝3', '牝4', '牝5'], n_samples),
            '斤量': np.random.randint(50, 60, n_samples),
            '騎手': np.random.choice(['A', 'B', 'C', 'D', 'E'], n_samples),
            'タイム': [f'{np.random.randint(1, 3)}:{np.random.randint(0, 60):02d}.{np.random.randint(0, 10)}' for _ in range(n_samples)],
            '着差': [f'{np.random.randint(0, 10)}.{np.random.randint(0, 10)}' for _ in range(n_samples)],
            '人気': np.random.randint(1, 20, n_samples),
            '単勝': np.random.uniform(1.0, 100.0, n_samples),
            '馬体重': np.random.randint(400, 600, n_samples),
            '増減': [f'{np.random.choice(["+", "-"])}{np.random.randint(0, 20)}' for _ in range(n_samples)]
        })

    def test_preprocess_data(self):
        print("テスト: データの前処理")
        self.create_mock_data()
        self.app.data = self.mock_data
        self.app.preprocess_data()
        print(f"前処理後のデータ形状: {self.app.data.shape}")
        print("カラム:", self.app.data.columns.tolist())
        print("前処理テスト完了\n")

    def test_train_model(self):
        print("テスト: モデルの訓練")
        self.app.train_model()
        print("モデル訓練テスト完了\n")

    def test_prediction(self):
        print("テスト: 予測")
        test_horse = pd.DataFrame({
            '枠番': [5],
            '馬番': [10],
            '斤量': [55.0],
            '人気': [3],
            '単勝': [7.5],
            '馬体重': [480],
            '増減': [2.0],
        })
        for col in self.app.data.columns:
            if col not in test_horse.columns:
                test_horse[col] = 0
        prediction = self.app.predict(test_horse)
        print(f"テスト馬の予測結果: {prediction[0]:.0f}着")
        print("予測テスト完了\n")

    def run_all_tests(self):
        self.test_preprocess_data()
        self.test_train_model()
        self.test_prediction()

# JRAPredictionAppクラスの定義（前回のコードから変更なし）
class JRAPredictionApp:
    def __init__(self):
        self.model = RandomForestClassifier()
        self.data = None

    def preprocess_data(self):
        if self.data is None or self.data.empty:
            print("データが存在しません。先にデータを取得してください。")
            return

        numeric_cols = ['着順', '枠番', '馬番', '斤量', '人気', '単勝', '馬体重', '増減']
        for col in numeric_cols:
            self.data[col] = pd.to_numeric(self.data[col], errors='coerce')
        
        self.data['タイム'] = self.data['タイム'].apply(self.time_to_seconds)
        self.data = pd.get_dummies(self.data, columns=['性齢', '騎手'])
        self.data['増減'] = self.data['増減'].apply(self.sign_to_number)
        self.data = self.data.dropna()
        print("データの前処理が完了しました。")

    def time_to_seconds(self, time_str):
        try:
            parts = time_str.split(':')
            if len(parts) == 2:
                return int(parts[0]) * 60 + float(parts[1])
        except ValueError:
            pass
        return None

    def sign_to_number(self, value):
        if pd.isna(value):
            return 0
        elif isinstance(value, str):
            if value.startswith('+'):
                return float(value[1:])
            elif value.startswith('-'):
                return -float(value[1:])
        return float(value)

    def train_model(self):
        if self.data is None or self.data.empty:
            print("データが存在しません。先にデータを取得し、前処理を行ってください。")
            return

        X = self.data.drop(['着順', '馬名', '着差'], axis=1)
        y = self.data['着順']
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        
        self.model.fit(X_train, y_train)
        y_pred = self.model.predict(X_test)
        accuracy = accuracy_score(y_test, y_pred)
        print(f"モデルの精度: {accuracy:.2f}")

    def predict(self, horse_data):
        if self.model is None:
            print("モデルが訓練されていません。先にモデルを訓練してください。")
            return None
        prediction = self.model.predict(horse_data)
        return prediction

if __name__ == "__main__":
    test = JRAPredictionAppTest()
    test.run_all_tests()
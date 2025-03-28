import requests
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder

# 仮想的なAPIからデータを取得する関数
def get_realtime_data():
    api_url = "https://api.example.com/m1-data"
    response = requests.get(api_url)
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception("Failed to fetch data from API")

# データを前処理する関数
def preprocess_data(data):
    df = pd.DataFrame(data)
    
    # カテゴリカル変数をエンコード
    le = LabelEncoder()
    df['comedy_style'] = le.fit_transform(df['comedy_style'])
    
    # 特徴量と目標変数を分離
    X = df[['previous_rank', 'years_active', 'comedy_style', 'average_score']]
    y = df['winner']
    
    return X, y

# モデルを訓練する関数
def train_model(X, y):
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)
    
    accuracy = model.score(X_test, y_test)
    print(f"Model accuracy: {accuracy:.2f}")
    
    return model

# 新しいデータに対して予測を行う関数
def predict_winner(model, new_data):
    prediction = model.predict(new_data)
    probabilities = model.predict_proba(new_data)
    
    return prediction, probabilities

# メイン関数
def main():
    # リアルタイムデータを取得
    data = get_realtime_data()
    
    # データを前処理
    X, y = preprocess_data(data)
    
    # モデルを訓練
    model = train_model(X, y)
    
    # 新しいデータ（現在のM-1グランプリの出場者）を取得
    new_data = get_realtime_data()  # 同じAPIを使用していますが、実際には別のエンドポイントを使用する可能性があります
    new_X, _ = preprocess_data(new_data)
    
    # 優勝者を予測
    prediction, probabilities = predict_winner(model, new_X)
    
    # 結果を表示
    for i, (pred, prob) in enumerate(zip(prediction, probabilities)):
        print(f"Contestant {i+1}: Predicted winner: {pred}, Probability: {prob[1]:.2f}")

if __name__ == "__main__":
    main()
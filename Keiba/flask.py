from flask import Flask, render_template, request, jsonify
import pandas as pd
import numpy as np
from JRAPredictionApp import JRAPredictionApp  # 先ほどのPythonスクリプトをインポート

app = Flask(__name__)
jra_app = JRAPredictionApp()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/predict', methods=['POST'])
def predict():
    data = request.json
    horse_data = pd.DataFrame({
        '枠番': [data['枠番']],
        '馬番': [data['馬番']],
        '斤量': [data['斤量']],
        '人気': [data['人気']],
        '単勝': [data['単勝']],
        '馬体重': [data['馬体重']],
        '増減': [data['増減']],
    })

    # One-hot encoding for '性齢' and '騎手'
    性齢 = data['性齢']
    騎手 = data['騎手']
    for col in jra_app.data.columns:
        if col.startswith('性齢_'):
            horse_data[col] = 1 if col == f'性齢_{性齢}' else 0
        elif col.startswith('騎手_'):
            horse_data[col] = 1 if col == f'騎手_{騎手}' else 0

    prediction = jra_app.predict(horse_data)
    return jsonify({'prediction': int(prediction[0])})

if __name__ == '__main__':
    # 必要なデータをスクレイプしてモデルをトレーニング
    base_url = 'YOUR_BASE_URL_HERE'
    jra_app.scrape_data(base_url, num_pages=5)
    jra_app.preprocess_data()
    jra_app.train_model()
    app.run(debug=True)
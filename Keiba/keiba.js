<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>競馬予想アプリ</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/jquery/3.6.0/jquery.min.js"></script>
    <style>
        body {
            font-family: 'Hiragino Kaku Gothic ProN', 'メイリオ', sans-serif;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f9f9f9;
        }
        
        h1 {
            color: #2c3e50;
            text-align: center;
            margin-bottom: 30px;
            border-bottom: 2px solid #3498db;
            padding-bottom: 10px;
        }
        
        form {
            display: grid;
            gap: 15px;
            background-color: white;
            padding: 25px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
        }
        
        .form-section {
            border: 1px solid #eee;
            padding: 15px;
            border-radius: 6px;
            margin-bottom: 20px;
        }
        
        .form-section h3 {
            margin-top: 0;
            color: #3498db;
            border-bottom: 1px solid #eee;
            padding-bottom: 10px;
            margin-bottom: 15px;
        }
        
        .form-group {
            display: grid;
            grid-template-columns: 150px 1fr;
            align-items: center;
            margin-bottom: 12px;
        }
        
        label {
            font-weight: bold;
            color: #333;
        }
        
        input, select {
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 4px;
            font-size: 14px;
            width: 100%;
        }
        
        input:focus, select:focus {
            border-color: #3498db;
            outline: none;
            box-shadow: 0 0 3px rgba(52, 152, 219, 0.5);
        }
        
        .error-message {
            color: #e74c3c;
            font-size: 12px;
            margin-top: 5px;
            grid-column: 2;
        }
        
        button {
            padding: 12px 25px;
            background-color: #3498db;
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            width: fit-content;
            font-weight: bold;
            font-size: 16px;
            transition: background-color 0.3s;
            margin: 0 auto;
            display: block;
        }
        
        button:hover {
            background-color: #2980b9;
        }
        
        #result {
            margin-top: 30px;
            padding: 20px;
            border-radius: 8px;
            text-align: center;
            font-size: 18px;
            font-weight: bold;
            transition: all 0.3s;
            display: none;
        }
        
        .success {
            background-color: #dff0d8;
            color: #3c763d;
            border: 1px solid #d6e9c6;
        }
        
        .error {
            background-color: #f2dede;
            color: #a94442;
            border: 1px solid #ebccd1;
        }
        
        .loading {
            text-align: center;
            margin-top: 20px;
            display: none;
        }
        
        .spinner {
            border: 4px solid rgba(0, 0, 0, 0.1);
            width: 36px;
            height: 36px;
            border-radius: 50%;
            border-left-color: #3498db;
            animation: spin 1s linear infinite;
            display: inline-block;
        }
        
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        
        .prediction-details {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 15px;
            margin-top: 20px;
            text-align: left;
        }
        
        .prediction-card {
            background-color: white;
            padding: 15px;
            border-radius: 6px;
            box-shadow: 0 1px 5px rgba(0, 0, 0, 0.1);
        }
        
        .prediction-card h4 {
            margin-top: 0;
            color: #3498db;
            border-bottom: 1px solid #eee;
            padding-bottom: 8px;
        }
        
        .highlight {
            font-weight: bold;
            color: #e74c3c;
        }
        
        #previous-results {
            margin-top: 30px;
        }
        
        table {
            width: 100%;
            border-collapse: collapse;
            background-color: white;
            box-shadow: 0 1px 5px rgba(0, 0, 0, 0.1);
        }
        
        th, td {
            padding: 12px 15px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }
        
        th {
            background-color: #f5f5f5;
            font-weight: bold;
            color: #333;
        }
        
        tr:hover {
            background-color: #f9f9f9;
        }
    </style>
</head>
<body>
    <h1>競馬予想アプリ</h1>
    <form id="prediction-form">
        <div class="form-section">
            <h3>レース情報</h3>
            <div class="form-group">
                <label for="race-track">競馬場:</label>
                <select id="race-track" name="race-track" required>
                    <option value="">選択してください</option>
                    <option value="東京">東京</option>
                    <option value="中山">中山</option>
                    <option value="阪神">阪神</option>
                    <option value="京都">京都</option>
                    <option value="福島">福島</option>
                    <option value="新潟">新潟</option>
                    <option value="中京">中京</option>
                    <option value="札幌">札幌</option>
                    <option value="函館">函館</option>
                    <option value="小倉">小倉</option>
                </select>
            </div>
            
            <div class="form-group">
                <label for="race-type">レースの種類:</label>
                <select id="race-type" name="race-type" required>
                    <option value="">選択してください</option>
                    <option value="G1">G1</option>
                    <option value="G2">G2</option>
                    <option value="G3">G3</option>
                    <option value="OP">オープン</option>
                    <option value="L">リステッド</option>
                    <option value="3勝">3勝クラス</option>
                    <option value="2勝">2勝クラス</option>
                    <option value="1勝">1勝クラス</option>
                    <option value="新馬">新馬戦</option>
                    <option value="未勝利">未勝利戦</option>
                </select>
            </div>
            
            <div class="form-group">
                <label for="race-distance">距離:</label>
                <select id="race-distance" name="race-distance" required>
                    <option value="">選択してください</option>
                    <option value="1000">1000m</option>
                    <option value="1200">1200m</option>
                    <option value="1400">1400m</option>
                    <option value="1600">1600m</option>
                    <option value="1800">1800m</option>
                    <option value="2000">2000m</option>
                    <option value="2200">2200m</option>
                    <option value="2400">2400m</option>
                    <option value="2500">2500m</option>
                    <option value="3000">3000m</option>
                    <option value="3200">3200m</option>
                    <option value="3600">3600m</option>
                </select>
            </div>
            
            <div class="form-group">
                <label for="track-type">コース種別:</label>
                <select id="track-type" name="track-type" required>
                    <option value="">選択してください</option>
                    <option value="芝">芝</option>
                    <option value="ダート">ダート</option>
                </select>
            </div>
            
            <div class="form-group">
                <label for="track-condition">馬場状態:</label>
                <select id="track-condition" name="track-condition" required>
                    <option value="">選択してください</option>
                    <option value="良">良</option>
                    <option value="稍重">稍重</option>
                    <option value="重">重</option>
                    <option value="不良">不良</option>
                </select>
            </div>
            
            <div class="form-group">
                <label for="weather">天気:</label>
                <select id="weather" name="weather" required>
                    <option value="">選択してください</option>
                    <option value="晴">晴</option>
                    <option value="曇">曇</option>
                    <option value="小雨">小雨</option>
                    <option value="雨">雨</option>
                    <option value="大雨">大雨</option>
                    <option value="雪">雪</option>
                </select>
            </div>
        </div>
        
        <div class="form-section">
            <h3>馬情報</h3>
            <div class="form-group">
                <label for="horse-name">馬名:</label>
                <input type="text" id="horse-name" name="horse-name" required />
            </div>
            
            <div class="form-group">
                <label for="frame-number">枠番:</label>
                <input type="number" id="frame-number" name="frame-number" min="1" max="8" required />
            </div>
            
            <div class="form-group">
                <label for="horse-number">馬番:</label>
                <input type="number" id="horse-number" name="horse-number" min="1" max="18" required />
            </div>
            
            <div class="form-group">
                <label for="weight">斤量:</label>
                <input type="number" id="weight" name="weight" step="0.1" min="45" max="65" required />
            </div>
            
            <div class="form-group">
                <label for="popularity">人気順位:</label>
                <input type="number" id="popularity" name="popularity" min="1" max="18" required />
            </div>
            
            <div class="form-group">
                <label for="odds">単勝オッズ:</label>
                <input type="number" id="odds" name="odds" step="0.1" min="1.0" required />
            </div>
            
            <div class="form-group">
                <label for="horse-weight">馬体重 (kg):</label>
                <input type="number" id="horse-weight" name="horse-weight" min="300" max="600" required />
            </div>
            
            <div class="form-group">
                <label for="weight-change">馬体重の増減:</label>
                <input type="number" id="weight-change" name="weight-change" step="1" required />
                <div class="error-message" id="weight-change-error"></div>
            </div>
            
            <div class="form-group">
                <label for="gender-age">性齢:</label>
                <select id="gender-age" name="gender-age" required>
                    <option value="">選択してください</option>
                    <optgroup label="牡馬">
                        <option value="牡2">牡2</option>
                        <option value="牡3">牡3</option>
                        <option value="牡4">牡4</option>
                        <option value="牡5">牡5</option>
                        <option value="牡6">牡6</option>
                        <option value="牡7">牡7</option>
                        <option value="牡8">牡8</option>
                        <option value="牡9">牡9以上</option>
                    </optgroup>
                    <optgroup label="牝馬">
                        <option value="牝2">牝2</option>
                        <option value="牝3">牝3</option>
                        <option value="牝4">牝4</option>
                        <option value="牝5">牝5</option>
                        <option value="牝6">牝6</option>
                        <option value="牝7">牝7</option>
                        <option value="牝8">牝8</option>
                        <option value="牝9">牝9以上</option>
                    </optgroup>
                    <optgroup label="セン馬">
                        <option value="セ2">セ2</option>
                        <option value="セ3">セ3</option>
                        <option value="セ4">セ4</option>
                        <option value="セ5">セ5</option>
                        <option value="セ6">セ6</option>
                        <option value="セ7">セ7</option>
                        <option value="セ8">セ8</option>
                        <option value="セ9">セ9以上</option>
                    </optgroup>
                </select>
            </div>
        </div>
        
        <div class="form-section">
            <h3>騎手・調教師情報</h3>
            <div class="form-group">
                <label for="jockey">騎手:</label>
                <select id="jockey" name="jockey" required>
                    <option value="">選択してください</option>
                    <option value="武豊">武豊</option>
                    <option value="福永祐一">福永祐一</option>
                    <option value="川田将雅">川田将雅</option>
                    <option value="ルメール">ルメール</option>
                    <option value="デムーロ">デムーロ</option>
                    <option value="戸崎圭太">戸崎圭太</option>
                    <option value="横山典弘">横山典弘</option>
                    <option value="松山弘平">松山弘平</option>
                    <option value="池添謙一">池添謙一</option>
                    <option value="藤岡佑介">藤岡佑介</option>
                    <option value="津村明秀">津村明秀</option>
                    <option value="その他">その他</option>
                </select>
            </div>
            
            <div class="form-group" id="other-jockey-group" style="display: none;">
                <label for="other-jockey">騎手名:</label>
                <input type="text" id="other-jockey" name="other-jockey" />
            </div>
            
            <div class="form-group">
                <label for="trainer">調教師:</label>
                <select id="trainer" name="trainer" required>
                    <option value="">選択してください</option>
                    <option value="藤原英昭">藤原英昭</option>
                    <option value="須貝尚介">須貝尚介</option>
                    <option value="友道康夫">友道康夫</option>
                    <option value="音無秀孝">音無秀孝</option>
                    <option value="国枝栄">国枝栄</option>
                    <option value="萩原清">萩原清</option>
                    <option value="西村真幸">西村真幸</option>
                    <option value="中内田充正">中内田充正</option>
                    <option value="その他">その他</option>
                </select>
            </div>
            
            <div class="form-group" id="other-trainer-group" style="display: none;">
                <label for="other-trainer">調教師名:</label>
                <input type="text" id="other-trainer" name="other-trainer" />
            </div>
        </div>
        
        <div class="form-section">
            <h3>過去のパフォーマンス</h3>
            <div class="form-group">
                <label for="last-three-results">直近3走の着順:</label>
                <input type="text" id="last-three-results" name="last-three-results" pattern="[0-9０-９]{1,2}-[0-9０-９]{1,2}-[0-9０-９]{1,2}" placeholder="例: 1-3-2" title="半角数字で「着順-着順-着順」の形式で入力してください" />
                <div class="error-message" id="last-results-error"></div>
            </div>
            
            <div class="form-group">
                <label for="previous-wins">通算勝利数:</label>
                <input type="number" id="previous-wins" name="previous-wins" min="0" max="50" />
            </div>
            
            <div class="form-group">
                <label for="previous-times">前走タイム (秒):</label>
                <input type="number" id="previous-times" name="previous-times" step="0.1" min="50" max="220" />
            </div>
        </div>
        
        <button type="submit">予測する</button>
    </form>
    
    <div class="loading">
        <div class="spinner"></div>
        <p>予測中...</p>
    </div>
    
    <div id="result"></div>
    
    <script>
        $(document).ready(function() {
            // 騎手と調教師の「その他」の表示制御
            $('#jockey').on('change', function() {
                if ($(this).val() === 'その他') {
                    $('#other-jockey-group').show();
                    $('#other-jockey').prop('required', true);
                } else {
                    $('#other-jockey-group').hide();
                    $('#other-jockey').prop('required', false);
                }
            });
            
            $('#trainer').on('change', function() {
                if ($(this).val() === 'その他') {
                    $('#other-trainer-group').show();
                    $('#other-trainer').prop('required', true);
                } else {
                    $('#other-trainer-group').hide();
                    $('#other-trainer').prop('required', false);
                }
            });
            
            // 入力値の検証
            $('#last-three-results').on('input', function() {
                const regex = /^[0-9０-９]{1,2}-[0-9０-９]{1,2}-[0-9０-９]{1,2}$/;
                if (this.value && !regex.test(this.value)) {
                    $('#last-results-error').text('「数字-数字-数字」の形式で入力してください');
                } else {
                    $('#last-results-error').text('');
                }
            });
            
            $('#weight-change').on('input', function() {
                const val = parseFloat($(this).val());
                if (val < -20 || val > 20) {
                    $('#weight-change-error').text('増減の範囲は-20kg〜+20kgにしてください');
                } else {
                    $('#weight-change-error').text('');
                }
            });
            
            // フォーム送信処理
            $('#prediction-form').on('submit', function(event) {
                event.preventDefault();
                
                // 入力検証
                if ($('#weight-change-error').text() || $('#last-results-error').text()) {
                    $('#result')
                        .removeClass('success')
                        .addClass('error')
                        .text('入力エラーを修正してください')
                        .show();
                    return;
                }
                
                // ローディング表示
                $('.loading').show();
                $('#result').hide();
                
                try {
                    // 騎手名の処理
                    let jockeyName = $('#jockey').val();
                    if (jockeyName === 'その他') {
                        jockeyName = $('#other-jockey').val();
                    }
                    
                    // 調教師名の処理
                    let trainerName = $('#trainer').val();
                    if (trainerName === 'その他') {
                        trainerName = $('#other-trainer').val();
                    }
                    
                    // フォームデータの収集
                    let formData = {
                        'race': {
                            'track': $('#race-track').val(),
                            'type': $('#race-type').val(),
                            'distance': parseInt($('#race-distance').val()),
                            'track_type': $('#track-type').val(),
                            'track_condition': $('#track-condition').val(),
                            'weather': $('#weather').val()
                        },
                        'horse': {
                            'name': $('#horse-name').val(),
                            'frame_number': parseInt($('#frame-number').val()),
                            'horse_number': parseInt($('#horse-number').val()),
                            'weight': parseFloat($('#weight').val()),
                            'popularity': parseInt($('#popularity').val()),
                            'odds': parseFloat($('#odds').val()),
                            'horse_weight': parseInt($('#horse-weight').val()),
                            'weight_change': parseInt($('#weight-change').val()),
                            'gender_age': $('#gender-age').val()
                        },
                        'connections': {
                            'jockey': jockeyName,
                            'trainer': trainerName
                        },
                        'performance': {
                            'last_three_results': $('#last-three-results').val() || null,
                            'previous_wins': parseInt($('#previous-wins').val() || 0),
                            'previous_time': parseFloat($('#previous-times').val() || 0)
                        }
                    };

                    // 予測APIへのリクエスト
                    $.ajax({
                        url: '/api/predict',
                        type: 'POST',
                        contentType: 'application/json',
                        data: JSON.stringify(formData),
                        success: function(response) {
                            $('.loading').hide();
                            
                            // 予測結果の表示
                            const resultDiv = $('#result');
                            resultDiv.removeClass('error').addClass('success');
                            
                            let resultHTML = `<h3>予測結果</h3>`;
                            resultHTML += `<p>${$('#horse-name').val()}の予想着順: <span class="highlight">${response.prediction}着</span></p>`;
                            
                            // 詳細情報の表示
                            if (response.detail) {
                                resultHTML += `<div class="prediction-details">`;
                                
                                // 勝率
                                resultHTML += `
                                    <div class="prediction-card">
                                        <h4>勝率予測</h4>
                                        <p>1着確率: <strong>${(response.detail.win_probability * 100).toFixed(1)}%</strong></p>
                                        <p>3着内確率: <strong>${(response.detail.place_probability * 100).toFixed(1)}%</strong></p>
                                    </div>
                                `;
                                
                                // 影響要因
                                resultHTML += `
                                    <div class="prediction-card">
                                        <h4>主な影響要因</h4>
                                        <ul>
                                            ${response.detail.factors.map(factor => `<li>${factor}</li>`).join('')}
                                        </ul>
                                    </div>
                                `;
                                
                                // アドバイス
                                resultHTML += `
                                    <div class="prediction-card">
                                        <h4>予想分析</h4>
                                        <p>${response.detail.analysis}</p>
                                    </div>
                                `;
                                
                                resultHTML += `</div>`;
                            }
                            
                            resultDiv.html(resultHTML).show();
                            
                            // 過去の予測結果の保存
                            saveResult(formData, response);
                        },
                        error: function(xhr, status, error) {
                            $('.loading').hide();
                            
                            let errorMessage = '予測に失敗しました。';
                            try {
                                const errorObj = JSON.parse(xhr.responseText);
                                errorMessage += ' ' + (errorObj.message || error);
                            } catch (e) {
                                errorMessage += ' ' + error;
                            }
                            
                            $('#result')
                                .removeClass('success')
                                .addClass('error')
                                .text(errorMessage)
                                .show();
                        }
                    });
                } catch (error) {
                    $('.loading').hide();
                    $('#result')
                        .removeClass('success')
                        .addClass('error')
                        .text('入力データの処理に失敗しました。: ' + error.message)
                        .show();
                }
            });
            
            // 過去の予測結果の保存
            function saveResult(formData, response) {
                try {
                    // localStorageから過去の結果を取得
                    let pastResults = JSON.parse(localStorage.getItem('horseRacingPredictions') || '[]');
                    
                    // 新しい結果を追加
                    pastResults.unshift({
                        timestamp: new Date().toISOString(),
                        horseName: formData.horse.name,
                        raceTrack: formData.race.track,
                        distance: formData.race.distance,
                        trackType: formData.race.track_type,
                        prediction: response.prediction,
                        actual: null // 実績は後で追加
                    });
                    
                    // 最大10件を保存
                    if (pastResults.length > 10) {
                        pastResults = pastResults.slice(0, 10);
                    }
                    
                    // localStorageに保存
                    localStorage.setItem('horseRacingPredictions', JSON.stringify(pastResults));
                } catch (error) {
                    console.error('過去の予測結果の保存に失敗しました:', error);
                }
            }
            
            // モックAPIレスポンス（実際のAPI完成まで使用）
            // サーバーのAPIがない場合の模擬データ
            $.ajaxPrefilter(function(options, originalOptions, jqXHR) {
                if (options.url === '/api/predict') {
                    // AJAXリクエストを中断
                    jqXHR.abort();
                    
                    // 模擬レスポンスを返す（本番ではこの部分は削除し、実際のAPIを使用）
                    const formData = JSON.parse(originalOptions.data);
                    setTimeout(function() {
                        const mockResponse = generateMockResponse(formData);
                        if (typeof originalOptions.success === 'function') {
                            originalOptions.success(mockResponse);
                        }
                    }, 1500); // 処理時間を擬似的に再現
                }
            });
            
            // モックレスポンス生成関数（本番では削除）
            function generateMockResponse(data) {
                // 単純なモデル（人気とオッズを中心に計算）
                const popularity = data.horse.popularity;
                const odds = data.horse.odds;
                const distance = data.race.distance;
                const trackType = data.race.track_type;
                const weightChange = data.horse.weight_change;
                const horseName = data.horse.name;
                
                // 過去成績
                let pastPerformance = 0;
                if (data.performance.last_three_results) {
                    const results = data.performance.last_three_results.split('-').map(Number);
                    pastPerformance = results.reduce((sum

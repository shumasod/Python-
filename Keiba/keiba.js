<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>競馬予想アプリ</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/jquery/3.6.0/jquery.min.js"></script>
    <style>
        body {
            font-family: sans-serif;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
        }
        
        form {
            display: grid;
            gap: 15px;
        }
        
        .form-group {
            display: grid;
            grid-template-columns: 120px 1fr;
            align-items: center;
        }
        
        input {
            padding: 8px;
            border: 1px solid #ccc;
            border-radius: 4px;
        }
        
        button {
            padding: 10px 20px;
            background-color: #4CAF50;
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            width: fit-content;
        }
        
        button:hover {
            background-color: #45a049;
        }
        
        #result {
            margin-top: 20px;
            padding: 10px;
            border-radius: 4px;
        }
        
        .success {
            background-color: #dff0d8;
            color: #3c763d;
        }
        
        .error {
            background-color: #f2dede;
            color: #a94442;
        }
    </style>
</head>
<body>
    <h1>競馬予想アプリ</h1>
    <form id="prediction-form">
        <div class="form-group">
            <label for="枠番">枠番:</label>
            <input type="number" id="枠番" name="枠番" min="1" max="8" required />
        </div>
        
        <div class="form-group">
            <label for="馬番">馬番:</label>
            <input type="number" id="馬番" name="馬番" min="1" max="18" required />
        </div>
        
        <div class="form-group">
            <label for="斤量">斤量:</label>
            <input type="number" id="斤量" name="斤量" step="0.1" min="45" max="65" required />
        </div>
        
        <div class="form-group">
            <label for="人気">人気:</label>
            <input type="number" id="人気" name="人気" min="1" max="18" required />
        </div>
        
        <div class="form-group">
            <label for="単勝">単勝オッズ:</label>
            <input type="number" id="単勝" name="単勝" step="0.1" min="1.0" required />
        </div>
        
        <div class="form-group">
            <label for="馬体重">馬体重:</label>
            <input type="number" id="馬体重" name="馬体重" min="300" max="600" required />
        </div>
        
        <div class="form-group">
            <label for="増減">馬体重の増減:</label>
            <input type="number" id="増減" name="増減" step="0.1" required />
        </div>
        
        <div class="form-group">
            <label for="性齢">性齢:</label>
            <input type="text" id="性齢" name="性齢" pattern="[牡牝セ][2-9]" title="性別(牡/牝/セ)と年齢(2-9)を入力してください" required />
        </div>
        
        <div class="form-group">
            <label for="騎手">騎手名:</label>
            <input type="text" id="騎手" name="騎手" required />
        </div>
        
        <button type="submit">予測</button>
    </form>
    
    <h2 id="result"></h2>
    
    <script>
        $(document).ready(function() {
            $('#prediction-form').on('submit', function(event) {
                event.preventDefault();
                
                try {
                    let formData = {
                        '枠番': parseInt($('#枠番').val()),
                        '馬番': parseInt($('#馬番').val()),
                        '斤量': parseFloat($('#斤量').val()),
                        '人気': parseInt($('#人気').val()),
                        '単勝': parseFloat($('#単勝').val()),
                        '馬体重': parseInt($('#馬体重').val()),
                        '増減': parseFloat($('#増減').val()),
                        '性齢': $('#性齢').val(),
                        '騎手': $('#騎手').val()
                    };

                    $.ajax({
                        url: '/predict',
                        type: 'POST',
                        contentType: 'application/json',
                        data: JSON.stringify(formData),
                        success: function(response) {
                            $('#result')
                                .removeClass('error')
                                .addClass('success')
                                .text(`予測結果: ${response.prediction}着`);
                        },
                        error: function(xhr, status, error) {
                            $('#result')
                                .removeClass('success')
                                .addClass('error')
                                .text('予測に失敗しました。: ' + error);
                        }
                    });
                } catch (error) {
                    $('#result')
                        .removeClass('success')
                        .addClass('error')
                        .text('入力データの処理に失敗しました。: ' + error.message);
                }
            });
        });
    </script>
</body>
</html>

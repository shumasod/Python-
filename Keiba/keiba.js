<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>競馬予想アプリ</title>
    <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
</head>
<body>
    <h1>競馬予想アプリ</h1>
    <form id="prediction-form">
        <label for="枠番">枠番:</label>
        <input type="number" id="枠番" name="枠番" required><br><br>
        
        <label for="馬番">馬番:</label>
        <input type="number" id="馬番" name="馬番" required><br><br>
        
        <label for="斤量">斤量:</label>
        <input type="number" id="斤量" name="斤量" step="0.1" required><br><br>
        
        <label for="人気">人気:</label>
        <input type="number" id="人気" name="人気" required><br><br>
        
        <label for="単勝">単勝オッズ:</label>
        <input type="number" id="単勝" name="単勝" step="0.1" required><br><br>
        
        <label for="馬体重">馬体重:</label>
        <input type="number" id="馬体重" name="馬体重" required><br><br>
        
        <label for="増減">馬体重の増減:</label>
        <input type="number" id="増減" name="増減" step="0.1" required><br><br>
        
        <label for="性齢">性齢:</label>
        <input type="text" id="性齢" name="性齢" required><br><br>
        
        <label for="騎手">騎手名:</label>
        <input type="text" id="騎手" name="騎手" required><br><br>
        
        <button type="submit">予測</button>
    </form>
    
    <h2 id="result"></h2>
    
    <script>
        $(document).ready(function() {
            $('#prediction-form').on('submit', function(event) {
                event.preventDefault();
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
                        $('#result').text(`予測結果: ${response.prediction}着`);
                    },
                    error: function() {
                        $('#result').text('予測に失敗しました。');
                    }
                });
            });
        });
    </script>
</body>
</html>

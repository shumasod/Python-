const PredictionResult = ({ prediction, loading, error }) => {
  // ローディング状態
  if (loading) {
    return (
      <div className="card">
        <div className="flex flex-col items-center justify-center py-12">
          <div className="animate-spin rounded-full h-16 w-16 border-b-4 border-jra-green mb-4"></div>
          <p className="text-gray-600 text-lg font-medium">予測を計算しています...</p>
        </div>
      </div>
    )
  }

  // エラー状態
  if (error) {
    return (
      <div className="card">
        <div className="bg-red-50 border-l-4 border-red-500 p-6">
          <div className="flex items-center space-x-3 mb-3">
            <span className="text-3xl">⚠️</span>
            <h3 className="text-lg font-bold text-red-800">エラーが発生しました</h3>
          </div>
          <p className="text-red-700">{error}</p>
          <p className="text-sm text-red-600 mt-3">
            入力内容を確認して、もう一度お試しください。
          </p>
        </div>
      </div>
    )
  }

  // 予測結果がない状態
  if (!prediction) {
    return (
      <div className="card bg-gray-50">
        <div className="flex flex-col items-center justify-center py-16 text-gray-400">
          <div className="text-7xl mb-4">🏇</div>
          <p className="text-lg font-medium">左側のフォームから予測を実行してください</p>
        </div>
      </div>
    )
  }

  // 予測結果の表示
  const { prediction: rank, confidence } = prediction
  const confidencePercent = (confidence * 100).toFixed(1)

  // 信頼度に応じた色分け
  const getConfidenceColor = () => {
    if (confidence >= 0.8) return 'text-green-600'
    if (confidence >= 0.6) return 'text-yellow-600'
    return 'text-orange-600'
  }

  // 信頼度に応じたメッセージ
  const getConfidenceMessage = () => {
    if (confidence >= 0.8) return '高い信頼度'
    if (confidence >= 0.6) return '中程度の信頼度'
    return '低い信頼度'
  }

  // 着順に応じたメダル
  const getRankMedal = () => {
    if (rank === 1) return '🥇'
    if (rank === 2) return '🥈'
    if (rank === 3) return '🥉'
    return '🏇'
  }

  return (
    <div className="card">
      {/* 予測着順 */}
      <div className="bg-gradient-to-br from-green-50 to-green-100 rounded-lg p-8 mb-6 border-2 border-jra-green-light">
        <div className="text-center">
          <div className="text-6xl mb-4">{getRankMedal()}</div>
          <p className="text-gray-600 text-sm font-semibold mb-2">予測着順</p>
          <div className="text-7xl font-bold text-jra-green mb-2">
            {rank}
            <span className="text-4xl">位</span>
          </div>
          <p className="text-gray-600 text-sm mt-2">
            この馬は<span className="font-bold text-jra-green">{rank}着</span>と予測されます
          </p>
        </div>
      </div>

      {/* 信頼度 */}
      <div className="bg-white rounded-lg p-6 border border-gray-200 mb-6">
        <div className="flex items-center justify-between mb-4">
          <span className="text-gray-700 font-bold">予測の信頼度</span>
          <span className={`text-2xl font-bold ${getConfidenceColor()}`}>
            {confidencePercent}%
          </span>
        </div>

        {/* 信頼度バー */}
        <div className="w-full bg-gray-200 rounded-full h-5 mb-3">
          <div
            className={`h-5 rounded-full transition-all duration-500 ${
              confidence >= 0.8
                ? 'bg-jra-green'
                : confidence >= 0.6
                ? 'bg-yellow-500'
                : 'bg-orange-500'
            }`}
            style={{ width: `${confidencePercent}%` }}
          ></div>
        </div>

        <p className={`text-sm font-bold ${getConfidenceColor()}`}>
          {getConfidenceMessage()}
        </p>
      </div>

      {/* 補足情報 */}
      <div className="bg-green-50 border-l-4 border-jra-green rounded p-4">
        <h3 className="font-bold text-gray-800 mb-3 flex items-center">
          <span className="mr-2">ℹ️</span>
          補足情報
        </h3>
        <ul className="text-sm text-gray-700 space-y-2">
          <li className="flex items-start">
            <span className="text-jra-green mr-2">•</span>
            <span>この予測は機械学習モデルによるものです</span>
          </li>
          <li className="flex items-start">
            <span className="text-jra-green mr-2">•</span>
            <span>実際のレース結果を保証するものではありません</span>
          </li>
          <li className="flex items-start">
            <span className="text-jra-green mr-2">•</span>
            <span>信頼度が高いほど予測の確度が高いことを示します</span>
          </li>
        </ul>
      </div>
    </div>
  )
}

export default PredictionResult

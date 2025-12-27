import { useState, useEffect } from 'react'
import PredictionForm from './components/PredictionForm'
import PredictionResult from './components/PredictionResult'
import Header from './components/Header'
import HealthStatus from './components/HealthStatus'
import { predictHorse, checkHealth } from './api/keiba'

function App() {
  const [prediction, setPrediction] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [healthStatus, setHealthStatus] = useState(null)

  // ヘルスチェック
  useEffect(() => {
    const fetchHealth = async () => {
      try {
        const health = await checkHealth()
        setHealthStatus(health)
      } catch (err) {
        console.error('ヘルスチェックエラー:', err)
      }
    }

    fetchHealth()
    const interval = setInterval(fetchHealth, 30000) // 30秒ごとに更新

    return () => clearInterval(interval)
  }, [])

  const handlePredict = async (horseData) => {
    setLoading(true)
    setError(null)
    setPrediction(null)

    try {
      const result = await predictHorse(horseData)
      setPrediction(result)
    } catch (err) {
      console.error('予測エラー:', err)
      setError(err.message || '予測の実行中にエラーが発生しました')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <Header />

      <main className="container mx-auto px-4 py-8 max-w-7xl">
        {/* ヘルスステータス */}
        <div className="mb-8">
          <HealthStatus status={healthStatus} />
        </div>

        {/* メインコンテンツ */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* 予測フォーム */}
          <div>
            <h2 className="section-title">馬情報入力</h2>
            <PredictionForm
              onSubmit={handlePredict}
              loading={loading}
            />
          </div>

          {/* 予測結果 */}
          <div>
            <h2 className="section-title">予測結果</h2>
            <PredictionResult
              prediction={prediction}
              loading={loading}
              error={error}
            />
          </div>
        </div>

        {/* 使い方 */}
        <div className="mt-12">
          <div className="card bg-green-50/50">
            <h2 className="section-title">使い方</h2>
            <div className="space-y-4 text-gray-700">
              <div className="flex items-start space-x-3">
                <span className="flex-shrink-0 w-8 h-8 bg-jra-green text-white rounded-full flex items-center justify-center font-bold text-sm">1</span>
                <p className="pt-1">左側のフォームに馬の情報を入力してください</p>
              </div>
              <div className="flex items-start space-x-3">
                <span className="flex-shrink-0 w-8 h-8 bg-jra-green text-white rounded-full flex items-center justify-center font-bold text-sm">2</span>
                <p className="pt-1">すべての項目を入力したら「予測を実行」ボタンをクリック</p>
              </div>
              <div className="flex items-start space-x-3">
                <span className="flex-shrink-0 w-8 h-8 bg-jra-green text-white rounded-full flex items-center justify-center font-bold text-sm">3</span>
                <p className="pt-1">右側に予測着順と信頼度が表示されます</p>
              </div>
              <div className="mt-6 pt-4 border-t border-green-200">
                <p className="text-sm text-gray-600">
                  ※ このシステムは機械学習モデルによる予測です。実際の競馬の結果を保証するものではありません。
                </p>
              </div>
            </div>
          </div>
        </div>
      </main>

      {/* フッター */}
      <footer className="bg-jra-green text-white py-10 mt-16">
        <div className="container mx-auto px-4">
          <div className="text-center">
            <p className="text-lg font-semibold mb-2">
              JRA競馬予測システム v1.0.0
            </p>
            <p className="text-green-100 text-sm">
              Machine Learning Powered Horse Racing Prediction
            </p>
            <div className="mt-6 pt-6 border-t border-green-600">
              <p className="text-xs text-green-200">
                © 2024 JRA競馬予測システム. All rights reserved.
              </p>
            </div>
          </div>
        </div>
      </footer>
    </div>
  )
}

export default App

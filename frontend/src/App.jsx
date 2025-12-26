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
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-purple-50">
      <Header />

      <main className="container mx-auto px-4 py-8 max-w-7xl">
        {/* ヘルスステータス */}
        <div className="mb-6">
          <HealthStatus status={healthStatus} />
        </div>

        {/* メインコンテンツ */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* 予測フォーム */}
          <div>
            <PredictionForm
              onSubmit={handlePredict}
              loading={loading}
            />
          </div>

          {/* 予測結果 */}
          <div>
            <PredictionResult
              prediction={prediction}
              loading={loading}
              error={error}
            />
          </div>
        </div>

        {/* 使い方 */}
        <div className="mt-12">
          <div className="card">
            <h2 className="text-2xl font-bold mb-4 text-gray-800">
              使い方
            </h2>
            <div className="space-y-3 text-gray-600">
              <p>
                <span className="font-semibold">1.</span> 左側のフォームに馬の情報を入力してください
              </p>
              <p>
                <span className="font-semibold">2.</span> すべての項目を入力したら「予測を実行」ボタンをクリック
              </p>
              <p>
                <span className="font-semibold">3.</span> 右側に予測着順と信頼度が表示されます
              </p>
              <p className="text-sm text-gray-500 mt-4">
                ※ このシステムは機械学習モデルによる予測です。実際の競馬の結果を保証するものではありません。
              </p>
            </div>
          </div>
        </div>
      </main>

      {/* フッター */}
      <footer className="bg-gray-800 text-white py-8 mt-16">
        <div className="container mx-auto px-4 text-center">
          <p className="text-gray-300">
            JRA競馬予測システム v1.0.0
          </p>
          <p className="text-gray-400 text-sm mt-2">
            Machine Learning Powered Horse Racing Prediction
          </p>
        </div>
      </footer>
    </div>
  )
}

export default App

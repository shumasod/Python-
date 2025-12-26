import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000'

// Axiosインスタンスの作成
const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000, // 30秒
})

// レスポンスインターセプター（エラーハンドリング）
api.interceptors.response.use(
  response => response,
  error => {
    if (error.response) {
      // サーバーエラー
      const message = error.response.data?.error || error.response.data?.message || 'サーバーエラーが発生しました'
      throw new Error(message)
    } else if (error.request) {
      // ネットワークエラー
      throw new Error('サーバーに接続できません。ネットワーク接続を確認してください。')
    } else {
      // その他のエラー
      throw new Error(error.message || '予期せぬエラーが発生しました')
    }
  }
)

/**
 * 馬の着順を予測
 * @param {Object} horseData - 馬のデータ
 * @returns {Promise<Object>} 予測結果
 */
export const predictHorse = async (horseData) => {
  try {
    const response = await api.post('/predict', horseData)
    return response.data
  } catch (error) {
    console.error('予測API エラー:', error)
    throw error
  }
}

/**
 * ヘルスチェック
 * @returns {Promise<Object>} ヘルスステータス
 */
export const checkHealth = async () => {
  try {
    const response = await api.get('/health')
    return response.data
  } catch (error) {
    console.error('ヘルスチェック エラー:', error)
    throw error
  }
}

/**
 * API情報を取得
 * @returns {Promise<Object>} API情報
 */
export const getApiInfo = async () => {
  try {
    const response = await api.get('/api/v1/info')
    return response.data
  } catch (error) {
    console.error('API情報取得 エラー:', error)
    throw error
  }
}

export default api

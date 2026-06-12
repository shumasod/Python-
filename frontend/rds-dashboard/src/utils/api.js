/**
 * API クライアント
 *
 * 設計意図:
 * - axios インスタンスで baseURL とタイムアウトを一元管理
 * - React Query と組み合わせてキャッシュ・再取得を自動化
 * - エラーレスポンスを統一フォーマットで返す
 */

import axios from "axios";

const BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

const apiClient = axios.create({
  baseURL: `${BASE_URL}/api/v1`,
  timeout: 10000,
  headers: {
    "Content-Type": "application/json",
  },
});

// レスポンスインターセプター（エラー処理の統一）
apiClient.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const message =
      error.response?.data?.detail ||
      error.message ||
      "予期しないエラーが発生しました";
    console.error("API Error:", message);
    return Promise.reject(new Error(message));
  }
);

// ============================================================
// API 関数
// ============================================================

/** 全インスタンスの概要を取得 */
export const fetchSummary = () => apiClient.get("/rds/summary");

/** 特定インスタンスの詳細分析を取得 */
export const fetchAnalysis = (instanceId, params = {}) =>
  apiClient.get(`/rds/${instanceId}/analysis`, { params });

/** 特定インスタンスの改善提案を取得 */
export const fetchRecommendations = (instanceId) =>
  apiClient.get(`/rds/${instanceId}/recommendations`);

/** インスタンスを登録 */
export const registerInstance = (payload) =>
  apiClient.post("/rds", payload);

/** メトリクスを手動投入 */
export const submitMetrics = (instanceId, payload) =>
  apiClient.post(`/rds/${instanceId}/metrics`, payload);

/** ヘルスチェック */
export const healthCheck = () => apiClient.get("/health");

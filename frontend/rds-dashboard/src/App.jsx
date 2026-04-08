/**
 * RDS Cost & Performance Analyzer - メインアプリケーション
 *
 * 設計意図:
 * - React Query でサーバー状態のキャッシュ・更新を管理（5分間隔で自動更新）
 * - React Router でダッシュボード / インスタンス詳細を切り替え
 * - レスポンシブグリッドレイアウト
 */

import React from "react";
import { BrowserRouter, Routes, Route, Link, useNavigate } from "react-router-dom";
import {
  QueryClient,
  QueryClientProvider,
  useQuery,
} from "@tanstack/react-query";
import { fetchSummary, fetchAnalysis, fetchRecommendations } from "./utils/api";
import { InstanceCard } from "./components/InstanceCard";
import { ScoreGauge } from "./components/ScoreGauge";
import { CostBreakdownPie } from "./components/CostChart";
import { RecommendationList } from "./components/RecommendationList";

// React Query クライアント（5分間隔で自動更新）
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchInterval: 5 * 60 * 1000,  // 5分
      staleTime: 4 * 60 * 1000,         // 4分
      retry: 2,
    },
  },
});

// ============================================================
// ダッシュボード画面
// ============================================================

function Dashboard() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["rds-summary"],
    queryFn: fetchSummary,
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64 text-gray-400">
        <div className="text-center">
          <div className="text-3xl mb-2">⏳</div>
          <div>データを読み込み中...</div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700">
        <strong>エラー:</strong> {error.message}
      </div>
    );
  }

  if (!data || data.total_instances === 0) {
    return (
      <div className="text-center py-16 text-gray-400">
        <div className="text-4xl mb-4">🗄️</div>
        <p className="text-lg font-medium mb-2">インスタンスが登録されていません</p>
        <p className="text-sm">API 経由でインスタンスを登録してください</p>
        <code className="mt-4 block bg-gray-100 text-gray-700 p-3 rounded text-xs max-w-md mx-auto text-left">
          POST /api/v1/rds
        </code>
      </div>
    );
  }

  return (
    <div>
      {/* サマリーカード */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
        <SummaryCard
          label="登録インスタンス数"
          value={data.total_instances}
          unit="台"
          icon="🗄️"
        />
        <SummaryCard
          label="月次合計コスト（推定）"
          value={`$${data.total_monthly_cost_usd.toFixed(0)}`}
          unit="/月"
          icon="💰"
        />
        <SummaryCard
          label="削減余地（推定）"
          value={`$${data.total_potential_savings_usd.toFixed(0)}`}
          unit="/月"
          icon="📉"
          highlight={data.total_potential_savings_usd > 0}
        />
      </div>

      {/* インスタンスカードグリッド */}
      <h2 className="text-lg font-semibold text-gray-700 mb-3">インスタンス一覧</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {data.instances.map((instance) => (
          <InstanceCard key={instance.instance_id} instance={instance} />
        ))}
      </div>
    </div>
  );
}

function SummaryCard({ label, value, unit, icon, highlight = false }) {
  return (
    <div className={`rounded-xl p-4 shadow-sm ${highlight ? "bg-green-50 border border-green-200" : "bg-white border border-gray-100"}`}>
      <div className="flex items-center gap-2 mb-2">
        <span className="text-xl">{icon}</span>
        <span className="text-xs text-gray-500">{label}</span>
      </div>
      <div className={`text-2xl font-bold ${highlight ? "text-green-600" : "text-gray-800"}`}>
        {value}
        <span className="text-sm font-normal text-gray-400 ml-1">{unit}</span>
      </div>
    </div>
  );
}

// ============================================================
// インスタンス詳細画面
// ============================================================

function InstanceDetail({ instanceId }) {
  const navigate = useNavigate();

  const analysisQuery = useQuery({
    queryKey: ["analysis", instanceId],
    queryFn: () => fetchAnalysis(instanceId),
    enabled: !!instanceId,
  });

  const recsQuery = useQuery({
    queryKey: ["recommendations", instanceId],
    queryFn: () => fetchRecommendations(instanceId),
    enabled: !!instanceId,
  });

  const isLoading = analysisQuery.isLoading;
  const error = analysisQuery.error;
  const data = analysisQuery.data;

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64 text-gray-400">
        分析データを読み込み中...
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700">
        <strong>エラー:</strong> {error.message}
      </div>
    );
  }

  if (!data) return null;

  return (
    <div>
      {/* 戻るボタン */}
      <button
        onClick={() => navigate("/")}
        className="mb-4 text-sm text-blue-500 hover:text-blue-700 flex items-center gap-1"
      >
        ← ダッシュボードに戻る
      </button>

      {/* インスタンスタイトル */}
      <h2 className="text-xl font-bold text-gray-800 mb-1">{instanceId}</h2>
      <p className="text-xs text-gray-400 mb-5">
        分析時刻: {new Date(data.analyzed_at).toLocaleString("ja-JP")}
      </p>

      {/* 警告 */}
      {data.warnings && data.warnings.length > 0 && (
        <div className="mb-4 space-y-1">
          {data.warnings.map((w, i) => (
            <div key={i} className="bg-yellow-50 border border-yellow-200 rounded px-3 py-2 text-sm text-yellow-800">
              ⚠️ {w}
            </div>
          ))}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* スコアゲージ */}
        <div className="bg-white rounded-xl shadow-sm p-4">
          <h3 className="text-sm font-semibold text-gray-600 mb-3">総合スコア</h3>
          <div className="flex justify-around">
            <ScoreGauge
              score={data.performance?.health_score || 0}
              label="パフォーマンス"
              size={140}
            />
            <ScoreGauge
              score={data.cost?.cost_efficiency_score || 0}
              label="コスト効率"
              size={140}
            />
          </div>
        </div>

        {/* コスト内訳 */}
        <div className="bg-white rounded-xl shadow-sm p-4">
          <h3 className="text-sm font-semibold text-gray-600 mb-1">
            コスト内訳（月次推定: ${data.cost?.total_cost_usd?.toFixed(2)}）
          </h3>
          <CostBreakdownPie breakdown={data.cost?.breakdown} />
        </div>

        {/* パフォーマンス指標 */}
        <div className="bg-white rounded-xl shadow-sm p-4">
          <h3 className="text-sm font-semibold text-gray-600 mb-3">パフォーマンス指標</h3>
          <PerformanceMetrics perf={data.performance} />
        </div>

        {/* 改善提案 */}
        <div className="bg-white rounded-xl shadow-sm p-4">
          <h3 className="text-sm font-semibold text-gray-600 mb-3">改善提案</h3>
          {recsQuery.isLoading ? (
            <div className="text-gray-400 text-sm">読み込み中...</div>
          ) : (
            <RecommendationList data={recsQuery.data} />
          )}
        </div>
      </div>
    </div>
  );
}

function PerformanceMetrics({ perf }) {
  if (!perf) return null;

  const metrics = [
    { label: "CPU 使用率", value: `${perf.cpu_avg_pct}%`, warning: perf.cpu_avg_pct > 80 },
    { label: "空きメモリ", value: `${perf.memory_free_gb} GB`, warning: perf.memory_free_gb < 1 },
    { label: "合計 IOPS", value: `${perf.avg_total_iops.toFixed(0)}`, warning: false },
    { label: "DB 接続数", value: `${perf.avg_connections.toFixed(0)}`, warning: false },
  ];

  return (
    <div className="space-y-2">
      {metrics.map((m) => (
        <div key={m.label} className="flex items-center justify-between py-1 border-b border-gray-50">
          <span className="text-xs text-gray-500">{m.label}</span>
          <span className={`text-sm font-semibold ${m.warning ? "text-red-500" : "text-gray-800"}`}>
            {m.value}
          </span>
        </div>
      ))}
      {perf.bottlenecks && perf.bottlenecks.length > 0 && (
        <div className="mt-2">
          <div className="text-xs text-red-500 font-medium mb-1">検知されたボトルネック:</div>
          {perf.bottlenecks.map((b, i) => (
            <div key={i} className="text-xs text-red-400 pl-2">• {b}</div>
          ))}
        </div>
      )}
    </div>
  );
}

// ============================================================
// ルーターラッパー
// ============================================================

function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<Dashboard />} />
      <Route
        path="/instance/:instanceId"
        element={<InstanceDetailWrapper />}
      />
    </Routes>
  );
}

function InstanceDetailWrapper() {
  const { instanceId } = useParams();
  return <InstanceDetail instanceId={instanceId} />;
}

// React Router の useParams を使うためのインポート
import { useParams } from "react-router-dom";

// ============================================================
// メインアプリ
// ============================================================

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <div className="min-h-screen bg-gray-50">
          {/* ナビゲーションバー */}
          <nav className="bg-white shadow-sm border-b border-gray-200 px-4 py-3">
            <div className="max-w-7xl mx-auto flex items-center justify-between">
              <Link to="/" className="flex items-center gap-2 font-bold text-gray-800">
                <span className="text-xl">📊</span>
                <span>RDS Analyzer</span>
              </Link>
              <div className="text-xs text-gray-400">
                ⚠️ コストは推定値です。実際の請求はAWS Consoleでご確認ください。
              </div>
            </div>
          </nav>

          {/* メインコンテンツ */}
          <main className="max-w-7xl mx-auto px-4 py-6">
            <AppRoutes />
          </main>
        </div>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

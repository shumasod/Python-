/**
 * インスタンスサマリーカードコンポーネント
 *
 * 設計意図:
 * - ダッシュボード上での各インスタンスの状態を一覧表示
 * - クリックで詳細画面に遷移
 * - コスト・スコアを一目で把握できるデザイン
 */

import React from "react";
import { useNavigate } from "react-router-dom";
import { ScoreBadge } from "./ScoreGauge";

const ENGINE_ICONS = {
  mysql: "🐬",
  postgresql: "🐘",
  "aurora-mysql": "⚡",
  "aurora-postgresql": "⚡",
};

export function InstanceCard({ instance }) {
  const navigate = useNavigate();
  const icon = ENGINE_ICONS[instance.engine] || "🗄️";

  return (
    <div
      className="bg-white rounded-xl shadow-sm p-4 cursor-pointer hover:shadow-md transition-shadow border border-gray-100"
      onClick={() => navigate(`/instance/${instance.instance_id}`)}
    >
      {/* ヘッダー */}
      <div className="flex items-start justify-between mb-3">
        <div>
          <div className="flex items-center gap-1.5 mb-0.5">
            <span className="text-lg">{icon}</span>
            <span className="font-semibold text-gray-800 text-sm">
              {instance.instance_id}
            </span>
          </div>
          <div className="text-xs text-gray-400">
            {instance.instance_class} · {instance.region}
          </div>
        </div>
        <div className="text-right">
          <div className="font-bold text-gray-800">
            ${instance.monthly_cost_usd.toFixed(0)}
          </div>
          <div className="text-xs text-gray-400">/ 月（推定）</div>
        </div>
      </div>

      {/* スコアバッジ */}
      <div className="flex gap-2 flex-wrap">
        <ScoreBadge score={instance.health_score} label="健全性" />
        <ScoreBadge score={instance.cost_efficiency_score} label="コスト効率" />
      </div>

      {/* 上位推奨アクション */}
      {instance.top_recommendation && (
        <div className="mt-2 text-xs text-blue-600 bg-blue-50 rounded px-2 py-1 truncate">
          💡 {instance.top_recommendation}
        </div>
      )}
    </div>
  );
}

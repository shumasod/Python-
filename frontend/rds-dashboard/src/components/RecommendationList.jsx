/**
 * 改善提案リストコンポーネント
 *
 * 設計意図:
 * - 優先度別にカラーコーディング（赤/橙/黄/灰）
 * - 節約額・改善効果を目立つバッジで表示
 * - アクションステップを折りたたみ表示
 */

import React, { useState } from "react";
import clsx from "clsx";

const PRIORITY_STYLES = {
  critical: {
    border: "border-l-4 border-red-500",
    badge: "bg-red-100 text-red-800",
    label: "🔴 緊急",
  },
  high: {
    border: "border-l-4 border-orange-500",
    badge: "bg-orange-100 text-orange-800",
    label: "🟠 高",
  },
  medium: {
    border: "border-l-4 border-yellow-500",
    badge: "bg-yellow-100 text-yellow-800",
    label: "🟡 中",
  },
  low: {
    border: "border-l-4 border-gray-400",
    badge: "bg-gray-100 text-gray-700",
    label: "⚪ 低",
  },
};

const COMPLEXITY_LABELS = {
  1: "簡単",
  2: "普通",
  3: "やや複雑",
  4: "複雑",
  5: "非常に複雑",
};

/**
 * 個別の改善提案カード
 */
function RecommendationCard({ rec }) {
  const [expanded, setExpanded] = useState(false);
  const style = PRIORITY_STYLES[rec.priority] || PRIORITY_STYLES.low;

  return (
    <div className={clsx("bg-white rounded-lg shadow-sm p-4 mb-3", style.border)}>
      {/* ヘッダー */}
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-1">
            <span className={clsx("text-xs px-2 py-0.5 rounded-full font-semibold", style.badge)}>
              {style.label}
            </span>
            <span className="text-xs text-gray-500">
              実装難易度: {COMPLEXITY_LABELS[rec.implementation_complexity] || rec.implementation_complexity}
            </span>
          </div>
          <h3 className="font-semibold text-gray-800 text-sm leading-tight">
            {rec.title}
          </h3>
        </div>

        {/* 節約額 */}
        {rec.estimated_monthly_savings_usd > 0 && (
          <div className="text-right shrink-0">
            <div className="text-green-600 font-bold text-sm">
              -${rec.estimated_monthly_savings_usd.toFixed(0)}/月
            </div>
            <div className="text-xs text-gray-400">節約見込み</div>
          </div>
        )}
        {rec.estimated_monthly_savings_usd < 0 && (
          <div className="text-right shrink-0">
            <div className="text-orange-500 font-bold text-sm">
              +${Math.abs(rec.estimated_monthly_savings_usd).toFixed(0)}/月
            </div>
            <div className="text-xs text-gray-400">追加コスト</div>
          </div>
        )}
      </div>

      {/* 説明 */}
      <p className="text-xs text-gray-600 mt-2 leading-relaxed">
        {rec.description}
      </p>

      {/* 現在 / 推奨設定 */}
      <div className="mt-2 grid grid-cols-2 gap-2 text-xs">
        <div className="bg-gray-50 rounded p-2">
          <div className="text-gray-400 mb-0.5">現在の設定</div>
          <div className="font-medium text-gray-700">{rec.current_config}</div>
        </div>
        <div className="bg-blue-50 rounded p-2">
          <div className="text-blue-400 mb-0.5">推奨設定</div>
          <div className="font-medium text-blue-700">{rec.recommended_config}</div>
        </div>
      </div>

      {/* アクションステップ（折りたたみ） */}
      {rec.action_steps && rec.action_steps.length > 0 && (
        <div className="mt-2">
          <button
            onClick={() => setExpanded(!expanded)}
            className="text-xs text-blue-500 hover:text-blue-700 font-medium"
          >
            {expanded ? "▲ アクションステップを閉じる" : "▼ アクションステップを確認"}
          </button>
          {expanded && (
            <ol className="mt-2 space-y-1">
              {rec.action_steps.map((step, i) => (
                <li key={i} className="flex gap-2 text-xs text-gray-600">
                  <span className="shrink-0 font-bold text-blue-500">{i + 1}.</span>
                  <span>{step}</span>
                </li>
              ))}
            </ol>
          )}
        </div>
      )}
    </div>
  );
}

/**
 * 改善提案リスト
 */
export function RecommendationList({ data }) {
  if (!data) return null;

  const { recommendations, total_potential_savings_usd } = data;

  if (!recommendations || recommendations.length === 0) {
    return (
      <div className="text-center text-gray-400 py-8">
        改善提案はありません
      </div>
    );
  }

  return (
    <div>
      {/* サマリー */}
      <div className="flex items-center justify-between mb-4 p-3 bg-green-50 rounded-lg">
        <div className="text-sm font-medium text-gray-700">
          {recommendations.length} 件の改善提案
        </div>
        {total_potential_savings_usd > 0 && (
          <div className="text-sm font-bold text-green-600">
            最大 ${total_potential_savings_usd.toFixed(0)}/月 の削減余地
          </div>
        )}
      </div>

      {/* 提案リスト */}
      {recommendations.map((rec) => (
        <RecommendationCard key={rec.id} rec={rec} />
      ))}
    </div>
  );
}

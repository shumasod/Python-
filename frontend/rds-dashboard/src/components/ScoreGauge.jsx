/**
 * スコアゲージコンポーネント
 *
 * 設計意図:
 * - 0〜100 のスコアを視覚的なゲージで表示
 * - スコアに応じて色が変化（赤→黄→緑）
 * - パフォーマンス健全性スコア・コスト効率スコアの両方で使用
 */

import React from "react";

/**
 * スコアから色クラスを返す
 * @param {number} score - 0〜100
 * @returns {string} Tailwind CSS クラス
 */
function getScoreColor(score) {
  if (score >= 80) return "#22c55e";  // green-500
  if (score >= 60) return "#eab308";  // yellow-500
  if (score >= 40) return "#f97316";  // orange-500
  return "#ef4444";                    // red-500
}

function getGradeLabel(score) {
  if (score >= 90) return "A";
  if (score >= 75) return "B";
  if (score >= 60) return "C";
  if (score >= 40) return "D";
  return "F";
}

/**
 * 半円ゲージコンポーネント
 */
export function ScoreGauge({ score = 0, label = "スコア", size = 160 }) {
  const radius = size * 0.4;
  const circumference = Math.PI * radius;  // 半円の周長
  const offset = circumference * (1 - score / 100);
  const color = getScoreColor(score);
  const grade = getGradeLabel(score);
  const cx = size / 2;
  const cy = size / 2;

  return (
    <div className="flex flex-col items-center">
      <svg width={size} height={size * 0.6} viewBox={`0 0 ${size} ${size * 0.6}`}>
        {/* 背景トラック */}
        <path
          d={`M ${size * 0.1},${size * 0.55} A ${radius},${radius} 0 0,1 ${size * 0.9},${size * 0.55}`}
          fill="none"
          stroke="#e5e7eb"
          strokeWidth={size * 0.08}
          strokeLinecap="round"
        />
        {/* スコアの弧 */}
        <path
          d={`M ${size * 0.1},${size * 0.55} A ${radius},${radius} 0 0,1 ${size * 0.9},${size * 0.55}`}
          fill="none"
          stroke={color}
          strokeWidth={size * 0.08}
          strokeLinecap="round"
          strokeDasharray={`${circumference}`}
          strokeDashoffset={offset}
          style={{ transition: "stroke-dashoffset 0.8s ease" }}
        />
        {/* スコア数値 */}
        <text
          x={cx}
          y={size * 0.45}
          textAnchor="middle"
          fontSize={size * 0.22}
          fontWeight="bold"
          fill={color}
        >
          {score}
        </text>
        {/* グレード */}
        <text
          x={cx}
          y={size * 0.58}
          textAnchor="middle"
          fontSize={size * 0.1}
          fill="#6b7280"
        >
          Grade {grade}
        </text>
      </svg>
      <span className="text-sm font-medium text-gray-600 mt-1">{label}</span>
    </div>
  );
}

/**
 * 小さなスコアバッジ
 */
export function ScoreBadge({ score, label }) {
  const color = getScoreColor(score);
  return (
    <div className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-semibold text-white"
      style={{ backgroundColor: color }}>
      {score} {label}
    </div>
  );
}

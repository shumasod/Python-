/**
 * コスト内訳グラフコンポーネント
 *
 * 設計意図:
 * - Recharts の PieChart でコスト内訳を視覚化
 * - BarChart で月次コスト推移を表示
 * - レスポンシブ対応（ResponsiveContainer 使用）
 */

import React from "react";
import {
  PieChart,
  Pie,
  Cell,
  Tooltip,
  Legend,
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
} from "recharts";

const COST_COLORS = {
  compute: "#3b82f6",   // blue
  storage: "#10b981",   // green
  iops: "#f59e0b",      // amber
  transfer: "#8b5cf6",  // purple
  backup: "#ec4899",    // pink
};

const COST_LABELS = {
  compute: "コンピュート",
  storage: "ストレージ",
  iops: "IOPS",
  transfer: "データ転送",
  backup: "バックアップ",
};

/**
 * コスト内訳パイチャート
 */
export function CostBreakdownPie({ breakdown }) {
  if (!breakdown) return null;

  const data = Object.entries(breakdown)
    .filter(([, value]) => value > 0)
    .map(([key, value]) => ({
      name: COST_LABELS[key] || key,
      value: parseFloat(value.toFixed(2)),
      key,
    }));

  const formatTooltip = (value, name) => [`$${value.toFixed(2)}`, name];

  return (
    <ResponsiveContainer width="100%" height={280}>
      <PieChart>
        <Pie
          data={data}
          cx="50%"
          cy="50%"
          outerRadius={90}
          dataKey="value"
          label={({ name, percent }) =>
            `${name} ${(percent * 100).toFixed(0)}%`
          }
          labelLine={false}
        >
          {data.map((entry) => (
            <Cell
              key={entry.key}
              fill={COST_COLORS[entry.key] || "#94a3b8"}
            />
          ))}
        </Pie>
        <Tooltip formatter={formatTooltip} />
        <Legend />
      </PieChart>
    </ResponsiveContainer>
  );
}

/**
 * メトリクス折れ線グラフ（CPU / IOPS）
 */
export function MetricsBarChart({ data, dataKey, color, label, unit }) {
  if (!data || data.length === 0) {
    return (
      <div className="flex items-center justify-center h-40 text-gray-400 text-sm">
        データなし
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={200}>
      <BarChart data={data} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
        <XAxis
          dataKey="time"
          tick={{ fontSize: 11 }}
          tickFormatter={(v) => v.substring(11, 16)}
        />
        <YAxis tick={{ fontSize: 11 }} unit={unit} />
        <Tooltip
          formatter={(value) => [`${value.toFixed(1)}${unit}`, label]}
        />
        <Bar dataKey={dataKey} fill={color} radius={[2, 2, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}

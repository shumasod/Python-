"""
カバリングインデックス分析エンジン

設計意図:
- クエリパターン（WHERE/ORDER BY/SELECT カラム）と既存インデックスを照合し、
  カバリングインデックスが効果を発揮する箇所を検出する
- MySQL/MariaDB と PostgreSQL でインデックス構文が異なるため両方の CREATE 文を生成
  - MySQL/MariaDB: (key_col1, key_col2, ..., select_col1, select_col2)
  - PostgreSQL 11+: (key_col1, key_col2) INCLUDE (select_col1, select_col2)
- rows_examined / rows_returned 比率でフルスキャン度を定量評価

スキャン比率と優先度:
  >= 1000 かつ 実行頻度 >= 100/日 → critical
  >= 100  または 高頻度              → high
  >= 10                              → medium
  < 10                               → 推奨なし（改善余地が小さい）
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from ..models.index import (
    CoveringIndexRecommendation,
    ExistingIndex,
    IndexAnalysisRequest,
    IndexAnalysisResult,
    QueryPattern,
)

logger = logging.getLogger(__name__)

# スキャン比率の閾値
_RATIO_CRITICAL = 1000.0
_RATIO_HIGH = 100.0
_RATIO_MEDIUM = 10.0
_FREQ_HIGH = 1000.0   # 1日あたり実行回数
_FREQ_MEDIUM = 100.0


class CoveringIndexAnalyzer:
    """カバリングインデックス分析エンジン（純粋計算クラス、I/O なし）"""

    def __init__(
        self,
        ratio_critical: float = 1000.0,
        ratio_high: float = 100.0,
        ratio_medium: float = 10.0,
        min_exec_count_per_day: float = 0.0,
    ) -> None:
        self._ratio_critical = ratio_critical
        self._ratio_high = ratio_high
        self._ratio_medium = ratio_medium
        self._min_exec_count_per_day = min_exec_count_per_day
        self._counter = 0

    # ----------------------------------------------------------
    # パブリック API
    # ----------------------------------------------------------

    def analyze(self, request: IndexAnalysisRequest) -> IndexAnalysisResult:
        """
        クエリパターンと既存インデックスを分析してカバリングインデックス推奨を生成する

        Args:
            request: 分析リクエスト（クエリ一覧 + 既存インデックス一覧）

        Returns:
            カバリングインデックス推奨リストを含む分析結果
        """
        self._counter = 0
        recommendations: list[CoveringIndexRecommendation] = []
        covered_count = 0
        needing_count = 0

        for query in request.queries:
            if query.execution_count_per_day < self._min_exec_count_per_day:
                logger.debug(
                    "クエリ '%s' は実行頻度 %.1f/日 が最小閾値 %.1f/日 未満のためスキップ",
                    query.query_id or query.table_name,
                    query.execution_count_per_day,
                    self._min_exec_count_per_day,
                )
                continue

            if self._is_covered(query, request.existing_indexes):
                covered_count += 1
                logger.debug("クエリ '%s' は既存インデックスでカバー済み", query.query_id or query.table_name)
                continue

            rec = self._build_recommendation(query, request.engine)
            if rec:
                recommendations.append(rec)
                needing_count += 1

        # 同一テーブルへの複数推奨をマージ
        recommendations = self._merge_by_table(recommendations)

        return IndexAnalysisResult(
            instance_id=request.instance_id,
            analyzed_at=datetime.now(tz=timezone.utc),
            engine=request.engine,
            total_queries_analyzed=len(request.queries),
            queries_already_covered=covered_count,
            queries_needing_index=needing_count,
            recommendations=recommendations,
            estimated_total_improvement_pct=self._total_improvement(recommendations),
        )

    # ----------------------------------------------------------
    # カバリング判定
    # ----------------------------------------------------------

    def _is_covered(self, query: QueryPattern, indexes: list[ExistingIndex]) -> bool:
        """
        クエリが既存インデックスでカバーされているか判定する

        カバリング条件:
          1. filter_columns が index の key_columns のプレフィックスになっている
          2. クエリが必要とする全カラム (filter + sort + select) が
             index の key_columns + include_columns に含まれている
        """
        needed = set(query.filter_columns + query.sort_columns + query.select_columns)
        if not needed:
            return False  # SELECT * など: 判定不能

        for idx in indexes:
            if idx.table_name != query.table_name:
                continue
            available = set(idx.key_columns + idx.include_columns)
            if needed.issubset(available) and self._is_filter_prefix(
                query.filter_columns, idx.key_columns
            ):
                return True
        return False

    def _is_filter_prefix(self, filter_cols: list[str], key_cols: list[str]) -> bool:
        """filter_cols が key_cols の先頭プレフィックスかどうか"""
        if not filter_cols:
            return True
        return len(filter_cols) <= len(key_cols) and all(
            f == k for f, k in zip(filter_cols, key_cols)
        )

    # ----------------------------------------------------------
    # 推奨生成
    # ----------------------------------------------------------

    def _build_recommendation(
        self, query: QueryPattern, engine: str
    ) -> Optional[CoveringIndexRecommendation]:
        """単一クエリのカバリングインデックス推奨を生成する"""
        if not query.filter_columns:
            return None  # WHERE 句なし: インデックスでフルスキャンを解消できない

        ratio = query.avg_rows_examined / max(query.avg_rows_returned, 1.0)
        if ratio < self._ratio_medium:
            return None  # スキャン比率が小さく改善余地が少ない

        # キーカラム: filter → sort → group (重複除去・順序維持)
        key_cols = _dedup(
            query.filter_columns + query.sort_columns + query.group_columns
        )
        # INCLUDE カラム: SELECT にあり、キーに含まれないもの
        include_cols = [c for c in query.select_columns if c not in key_cols]

        self._counter += 1
        idx_name = f"idx_{query.table_name}_covering_{self._counter:03d}"

        # MySQL/MariaDB は INCLUDE 構文がないため全カラムをキーに含める
        mysql_key_cols = key_cols + include_cols

        improvement_pct = min(95.0, (1.0 - 1.0 / ratio) * 100.0)
        daily_saved = query.avg_rows_examined * query.execution_count_per_day

        return CoveringIndexRecommendation(
            recommendation_id=f"idx_{self._counter:03d}",
            table_name=query.table_name,
            key_columns=key_cols,
            include_columns=include_cols,
            priority=self._priority(ratio, query.execution_count_per_day),
            reason=self._reason(query, ratio),
            affected_query_ids=[query.query_id or f"query_{self._counter}"],
            estimated_scan_ratio=round(ratio, 1),
            estimated_latency_improvement_pct=round(improvement_pct, 1),
            estimated_daily_rows_saved=round(daily_saved, 0),
            create_statement_mysql=self._mysql_create(
                query.table_name, idx_name, mysql_key_cols
            ),
            create_statement_postgresql=self._pg_create(
                query.table_name, idx_name, key_cols, include_cols, engine
            ),
        )

    # ----------------------------------------------------------
    # 推奨マージ (同一テーブル)
    # ----------------------------------------------------------

    def _merge_by_table(
        self, recs: list[CoveringIndexRecommendation]
    ) -> list[CoveringIndexRecommendation]:
        """
        同一テーブルへの推奨をマージする

        マージ条件: filter_columns (= key_columns の先頭) が共通プレフィックスを持つ場合
        マージ結果: キーカラムは長い方を採用、INCLUDE カラムは和集合を取る
        """
        if len(recs) <= 1:
            return recs

        # テーブル名でグループ化
        groups: dict[str, list[CoveringIndexRecommendation]] = {}
        for rec in recs:
            groups.setdefault(rec.table_name, []).append(rec)

        merged: list[CoveringIndexRecommendation] = []
        for table, group in groups.items():
            merged.extend(self._merge_group(table, group))

        return merged

    def _merge_group(
        self, table: str, group: list[CoveringIndexRecommendation]
    ) -> list[CoveringIndexRecommendation]:
        """同一テーブルの推奨グループをマージする"""
        result: list[CoveringIndexRecommendation] = []
        processed = [False] * len(group)

        for i, base in enumerate(group):
            if processed[i]:
                continue
            current = base
            for j, other in enumerate(group[i + 1:], start=i + 1):
                if processed[j]:
                    continue
                common = _common_prefix(current.key_columns, other.key_columns)
                if not common:
                    continue
                current = self._do_merge(table, current, other)
                processed[j] = True
            result.append(current)
            processed[i] = True

        return result

    def _do_merge(
        self,
        table: str,
        a: CoveringIndexRecommendation,
        b: CoveringIndexRecommendation,
    ) -> CoveringIndexRecommendation:
        """2つの推奨をマージする（長いキーを採用、INCLUDEは和集合）"""
        key_cols = a.key_columns if len(a.key_columns) >= len(b.key_columns) else b.key_columns
        include_cols = _dedup(a.include_columns + b.include_columns)
        include_cols = [c for c in include_cols if c not in key_cols]

        _priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        best_priority = min(
            [a.priority, b.priority], key=lambda p: _priority_order.get(p, 9)
        )

        idx_name = f"idx_{table}_covering"
        mysql_key = key_cols + include_cols

        return CoveringIndexRecommendation(
            recommendation_id=a.recommendation_id,
            table_name=table,
            key_columns=key_cols,
            include_columns=include_cols,
            priority=best_priority,
            reason=f"{a.reason} / {b.reason}",
            affected_query_ids=_dedup(a.affected_query_ids + b.affected_query_ids),
            estimated_scan_ratio=max(a.estimated_scan_ratio, b.estimated_scan_ratio),
            estimated_latency_improvement_pct=max(
                a.estimated_latency_improvement_pct, b.estimated_latency_improvement_pct
            ),
            estimated_daily_rows_saved=a.estimated_daily_rows_saved + b.estimated_daily_rows_saved,
            create_statement_mysql=self._mysql_create(table, idx_name, mysql_key),
            create_statement_postgresql=self._pg_create(table, idx_name, key_cols, include_cols, "postgresql"),
        )

    # ----------------------------------------------------------
    # 優先度・理由文
    # ----------------------------------------------------------

    def _priority(self, ratio: float, daily_exec: float) -> str:
        if ratio >= self._ratio_critical and daily_exec >= _FREQ_MEDIUM:
            return "critical"
        if ratio >= self._ratio_high or (ratio >= self._ratio_medium and daily_exec >= _FREQ_HIGH):
            return "high"
        if ratio >= self._ratio_medium or daily_exec >= _FREQ_MEDIUM:
            return "medium"
        return "low"

    def _reason(self, query: QueryPattern, ratio: float) -> str:
        parts = [
            f"`{query.table_name}` で平均 {ratio:.0f}:1 のスキャンが発生 "
            f"(検査 {query.avg_rows_examined:.0f} 行 / 返却 {query.avg_rows_returned:.0f} 行)",
        ]
        if query.avg_latency_ms > 0:
            parts.append(f"平均レイテンシ {query.avg_latency_ms:.1f} ms")
        if query.execution_count_per_day > 0:
            parts.append(f"1日 {query.execution_count_per_day:.0f} 回実行")
        return " / ".join(parts)

    # ----------------------------------------------------------
    # CREATE INDEX 文生成
    # ----------------------------------------------------------

    def _mysql_create(self, table: str, name: str, columns: list[str]) -> str:
        cols = ", ".join(f"`{c}`" for c in columns)
        return f"CREATE INDEX `{name}` ON `{table}` ({cols});"

    def _pg_create(
        self,
        table: str,
        name: str,
        key_cols: list[str],
        include_cols: list[str],
        engine: str,
    ) -> str:
        keys = ", ".join(f'"{c}"' for c in key_cols)
        stmt = f'CREATE INDEX "{name}" ON "{table}" ({keys})'
        # INCLUDE 句は PostgreSQL 11+ のみ対応
        if include_cols and "postgresql" in engine:
            incs = ", ".join(f'"{c}"' for c in include_cols)
            stmt += f" INCLUDE ({incs})"
        return stmt + ";"

    # ----------------------------------------------------------
    # 集計ヘルパー
    # ----------------------------------------------------------

    def _total_improvement(self, recs: list[CoveringIndexRecommendation]) -> float:
        if not recs:
            return 0.0
        return round(
            sum(r.estimated_latency_improvement_pct for r in recs) / len(recs), 1
        )


# ----------------------------------------------------------
# モジュールレベルヘルパー
# ----------------------------------------------------------

def _dedup(lst: list[str]) -> list[str]:
    """順序を維持しつつ重複を除去する"""
    return list(dict.fromkeys(lst))


def _common_prefix(a: list[str], b: list[str]) -> list[str]:
    """2つのリストの共通プレフィックスを返す"""
    return [x for x, y in zip(a, b) if x == y]

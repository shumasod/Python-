"""
スロークエリログパーサー

MySQL の slow query log テキストと PostgreSQL の pg_stat_statements 出力を
CoveringIndexAnalyzer の入力形式 (QueryPattern) に変換するユーティリティ。

使用例:
    from rds_analyzer.analyzers.slow_query_parser import SlowQueryParser
    patterns = SlowQueryParser.from_mysql_slow_log(log_text)
    # → list[QueryPattern]
"""

from __future__ import annotations

import re
from typing import Optional

from ..models.index import QueryPattern


class SlowQueryParser:
    """スロークエリログを QueryPattern リストに変換するパーサー"""

    # MySQL slow query log の1エントリを抽出する正規表現
    _MYSQL_ENTRY_RE = re.compile(
        r"# Query_time:\s*([\d.]+)\s+Lock_time:\s*[\d.]+\s+"
        r"Rows_sent:\s*(\d+)\s+Rows_examined:\s*(\d+)\n"
        r"(?:use \S+;\n)?"
        r"(?:SET timestamp=\d+;\n)?"
        r"(.*?);",
        re.DOTALL,
    )

    # SQL から FROM テーブル名を抽出
    _FROM_TABLE_RE = re.compile(
        r"\bFROM\s+`?(\w+)`?(?:\s+(?:AS\s+)?\w+)?",
        re.IGNORECASE,
    )
    # WHERE 条件のカラム名を抽出 (簡易)
    _WHERE_COL_RE = re.compile(
        r"\bWHERE\b.*?\b(\w+)\s*(?:=|!=|<|>|<=|>=|LIKE|IN|BETWEEN)",
        re.IGNORECASE,
    )
    # ORDER BY カラム
    _ORDER_COL_RE = re.compile(r"\bORDER\s+BY\s+([\w\s,`]+?)(?:\bLIMIT\b|$)", re.IGNORECASE)
    # SELECT カラム
    _SELECT_COL_RE = re.compile(r"\bSELECT\s+(.*?)\s+FROM\b", re.IGNORECASE | re.DOTALL)

    @classmethod
    def from_mysql_slow_log(cls, log_text: str) -> list[QueryPattern]:
        """
        MySQL slow query log テキストを QueryPattern リストに変換する。

        Args:
            log_text: slow query log の内容 (複数エントリ可)

        Returns:
            QueryPattern のリスト
        """
        patterns: list[QueryPattern] = []
        for i, m in enumerate(cls._MYSQL_ENTRY_RE.finditer(log_text)):
            latency_ms = float(m.group(1)) * 1000
            rows_returned = max(1.0, float(m.group(2)))
            rows_examined = float(m.group(3))
            query_text = m.group(4).strip()

            table = cls._extract_table(query_text)
            if not table:
                continue

            patterns.append(QueryPattern(
                query_id=f"slow_{i:04d}",
                table_name=table,
                filter_columns=cls._extract_where_cols(query_text),
                sort_columns=cls._extract_order_cols(query_text),
                select_columns=cls._extract_select_cols(query_text),
                avg_rows_examined=rows_examined,
                avg_rows_returned=rows_returned,
                avg_latency_ms=latency_ms,
                query_text=query_text,
            ))

        return patterns

    @classmethod
    def from_pg_stat_statements(cls, rows: list[dict]) -> list[QueryPattern]:
        """
        pg_stat_statements のクエリ行リストを QueryPattern に変換する。

        Args:
            rows: [{"query": str, "calls": int, "mean_exec_time": float,
                    "rows": int}, ...] 形式の辞書リスト

        Returns:
            QueryPattern のリスト
        """
        patterns: list[QueryPattern] = []
        for i, row in enumerate(rows):
            query_text = row.get("query", "")
            calls = max(1, int(row.get("calls", 1)))
            avg_rows = max(1.0, float(row.get("rows", 1)) / calls)
            latency_ms = float(row.get("mean_exec_time", 0))

            table = cls._extract_table(query_text)
            if not table:
                continue

            patterns.append(QueryPattern(
                query_id=f"pg_{i:04d}",
                table_name=table,
                filter_columns=cls._extract_where_cols(query_text),
                sort_columns=cls._extract_order_cols(query_text),
                select_columns=cls._extract_select_cols(query_text),
                avg_rows_examined=avg_rows * 10,  # PostgreSQL では行検査数は推定
                avg_rows_returned=avg_rows,
                avg_latency_ms=latency_ms,
                execution_count_per_day=calls / 30.0,  # 30日で正規化
                query_text=query_text,
            ))

        return patterns

    # ----------------------------------------------------------
    # プライベートヘルパー
    # ----------------------------------------------------------

    @classmethod
    def _extract_table(cls, sql: str) -> Optional[str]:
        m = cls._FROM_TABLE_RE.search(sql)
        return m.group(1) if m else None

    @classmethod
    def _extract_where_cols(cls, sql: str) -> list[str]:
        cols = cls._WHERE_COL_RE.findall(sql)
        return list(dict.fromkeys(c.strip("`") for c in cols))

    @classmethod
    def _extract_order_cols(cls, sql: str) -> list[str]:
        m = cls._ORDER_COL_RE.search(sql)
        if not m:
            return []
        raw = m.group(1)
        cols = [c.strip().strip("`").split()[0] for c in raw.split(",") if c.strip()]
        return [c for c in cols if c and c.upper() not in ("ASC", "DESC")]

    @classmethod
    def _extract_select_cols(cls, sql: str) -> list[str]:
        m = cls._SELECT_COL_RE.search(sql)
        if not m:
            return []
        raw = m.group(1).strip()
        if raw == "*":
            return []
        cols = []
        for part in raw.split(","):
            col = part.strip().strip("`").split(".")[-1].split()[-1]
            if col and not col.startswith("("):
                cols.append(col)
        return cols

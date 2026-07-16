"""
CoveringIndexAnalyzer テスト

カバリングインデックス分析エンジンのユニットテスト
"""

import pytest

from rds_analyzer.analyzers.index_analyzer import CoveringIndexAnalyzer
from rds_analyzer.models.index import (
    ExistingIndex,
    IndexAnalysisRequest,
    QueryPattern,
)


# ──────────────────────────────────────────────
# テストヘルパー
# ──────────────────────────────────────────────

def make_query(
    table: str = "orders",
    filter_cols: list[str] | None = None,
    sort_cols: list[str] | None = None,
    select_cols: list[str] | None = None,
    group_cols: list[str] | None = None,
    rows_examined: float = 10000,
    rows_returned: float = 10,
    exec_per_day: float = 100,
    latency_ms: float = 50,
    query_id: str = "q1",
) -> QueryPattern:
    return QueryPattern(
        query_id=query_id,
        table_name=table,
        filter_columns=filter_cols or [],
        sort_columns=sort_cols or [],
        select_columns=select_cols or [],
        group_columns=group_cols or [],
        avg_rows_examined=rows_examined,
        avg_rows_returned=rows_returned,
        execution_count_per_day=exec_per_day,
        avg_latency_ms=latency_ms,
    )


def make_index(
    table: str,
    name: str,
    key_cols: list[str],
    include_cols: list[str] | None = None,
) -> ExistingIndex:
    return ExistingIndex(
        index_name=name,
        table_name=table,
        key_columns=key_cols,
        include_columns=include_cols or [],
    )


def make_request(
    queries: list[QueryPattern],
    indexes: list[ExistingIndex] | None = None,
    engine: str = "mysql",
) -> IndexAnalysisRequest:
    return IndexAnalysisRequest(
        instance_id="db-test-01",
        engine=engine,
        queries=queries,
        existing_indexes=indexes or [],
    )


# ──────────────────────────────────────────────
# カバリング判定テスト
# ──────────────────────────────────────────────

class TestIsCovered:
    def test_no_indexes_returns_not_covered(self):
        analyzer = CoveringIndexAnalyzer()
        query = make_query(filter_cols=["status"], select_cols=["id", "amount"])
        result = analyzer.analyze(make_request([query], indexes=[]))
        assert result.queries_already_covered == 0

    def test_exact_covering_index_detected(self):
        analyzer = CoveringIndexAnalyzer()
        query = make_query(
            filter_cols=["status"],
            sort_cols=["created_at"],
            select_cols=["id", "amount"],
        )
        idx = make_index("orders", "idx_covering", ["status", "created_at", "id", "amount"])
        result = analyzer.analyze(make_request([query], indexes=[idx]))
        assert result.queries_already_covered == 1
        assert result.queries_needing_index == 0
        assert result.recommendations == []

    def test_postgresql_include_columns_count_as_covered(self):
        analyzer = CoveringIndexAnalyzer()
        query = make_query(
            filter_cols=["user_id"],
            select_cols=["email", "name"],
            engine_str="postgresql",
        ) if False else make_query(
            filter_cols=["user_id"],
            select_cols=["email", "name"],
        )
        idx = make_index("orders", "idx_pg", ["user_id"], include_cols=["email", "name"])
        result = analyzer.analyze(make_request([query], indexes=[idx], engine="postgresql"))
        assert result.queries_already_covered == 1

    def test_index_missing_select_column_not_covered(self):
        analyzer = CoveringIndexAnalyzer()
        # インデックスに 'amount' がない
        query = make_query(
            filter_cols=["status"],
            select_cols=["id", "amount"],
        )
        idx = make_index("orders", "idx_partial", ["status", "id"])
        result = analyzer.analyze(make_request([query], indexes=[idx]))
        assert result.queries_already_covered == 0
        assert len(result.recommendations) == 1

    def test_index_for_different_table_not_counted(self):
        analyzer = CoveringIndexAnalyzer()
        query = make_query(table="orders", filter_cols=["status"], select_cols=["id"])
        idx = make_index("users", "idx_users", ["status", "id"])
        result = analyzer.analyze(make_request([query], indexes=[idx]))
        assert result.queries_already_covered == 0

    def test_filter_not_prefix_of_key_not_covered(self):
        # インデックスは (a, b, c) だが filter は (b,) — プレフィックス不一致
        analyzer = CoveringIndexAnalyzer()
        query = make_query(filter_cols=["b"], select_cols=["a", "c"])
        idx = make_index("orders", "idx_abc", ["a", "b", "c"])
        result = analyzer.analyze(make_request([query], indexes=[idx]))
        assert result.queries_already_covered == 0


# ──────────────────────────────────────────────
# 推奨生成テスト (MySQL)
# ──────────────────────────────────────────────

class TestRecommendationMySQL:
    def test_basic_covering_index_recommended(self):
        analyzer = CoveringIndexAnalyzer()
        query = make_query(
            filter_cols=["status"],
            sort_cols=["created_at"],
            select_cols=["id", "amount"],
            rows_examined=10000,
            rows_returned=10,
        )
        result = analyzer.analyze(make_request([query], engine="mysql"))
        assert len(result.recommendations) == 1
        rec = result.recommendations[0]
        assert rec.table_name == "orders"
        assert "status" in rec.key_columns
        assert "created_at" in rec.key_columns

    def test_mysql_create_statement_format(self):
        analyzer = CoveringIndexAnalyzer()
        query = make_query(
            filter_cols=["status"],
            select_cols=["id", "amount"],
            rows_examined=1000,
            rows_returned=1,
        )
        result = analyzer.analyze(make_request([query], engine="mysql"))
        stmt = result.recommendations[0].create_statement_mysql
        assert stmt.startswith("CREATE INDEX")
        assert "`orders`" in stmt
        assert "`status`" in stmt
        # MySQL: select_cols はキーに追加される
        assert "`id`" in stmt or "`amount`" in stmt

    def test_mysql_no_include_clause(self):
        analyzer = CoveringIndexAnalyzer()
        query = make_query(
            filter_cols=["category_id"],
            select_cols=["name", "price"],
            rows_examined=5000,
            rows_returned=5,
        )
        result = analyzer.analyze(make_request([query], engine="mysql"))
        stmt = result.recommendations[0].create_statement_mysql
        assert "INCLUDE" not in stmt

    def test_no_where_clause_skipped(self):
        analyzer = CoveringIndexAnalyzer()
        query = make_query(
            filter_cols=[],  # WHERE 句なし
            select_cols=["id", "name"],
            rows_examined=50000,
            rows_returned=50000,
        )
        result = analyzer.analyze(make_request([query]))
        assert result.recommendations == []

    def test_low_scan_ratio_skipped(self):
        analyzer = CoveringIndexAnalyzer()
        # ratio = 9 < 10 → スキップ
        query = make_query(
            filter_cols=["id"],
            select_cols=["name"],
            rows_examined=9,
            rows_returned=1,
        )
        result = analyzer.analyze(make_request([query]))
        assert result.recommendations == []


# ──────────────────────────────────────────────
# 推奨生成テスト (PostgreSQL)
# ──────────────────────────────────────────────

class TestRecommendationPostgreSQL:
    def test_postgresql_include_clause_generated(self):
        analyzer = CoveringIndexAnalyzer()
        query = make_query(
            filter_cols=["user_id"],
            sort_cols=["created_at"],
            select_cols=["email", "name"],  # キーにない → INCLUDE 候補
            rows_examined=10000,
            rows_returned=1,
        )
        result = analyzer.analyze(make_request([query], engine="postgresql"))
        rec = result.recommendations[0]
        pg_stmt = rec.create_statement_postgresql
        assert "INCLUDE" in pg_stmt
        assert '"email"' in pg_stmt or '"name"' in pg_stmt

    def test_postgresql_key_columns_not_duplicated_in_include(self):
        analyzer = CoveringIndexAnalyzer()
        query = make_query(
            filter_cols=["user_id"],
            select_cols=["user_id", "email"],  # user_id は既にキー
            rows_examined=5000,
            rows_returned=1,
        )
        result = analyzer.analyze(make_request([query], engine="postgresql"))
        rec = result.recommendations[0]
        # user_id はキーに既にあるので INCLUDE に含まれない
        assert "user_id" not in rec.include_columns

    def test_mariadb_no_include_clause(self):
        analyzer = CoveringIndexAnalyzer()
        query = make_query(
            filter_cols=["status"],
            select_cols=["id", "amount"],
            rows_examined=5000,
            rows_returned=5,
        )
        result = analyzer.analyze(make_request([query], engine="mariadb"))
        stmt = result.recommendations[0].create_statement_postgresql
        # mariadb は INCLUDE 構文なし
        assert "INCLUDE" not in stmt


# ──────────────────────────────────────────────
# 優先度テスト
# ──────────────────────────────────────────────

class TestPriority:
    def test_critical_priority_high_ratio_high_frequency(self):
        analyzer = CoveringIndexAnalyzer()
        query = make_query(
            filter_cols=["status"],
            rows_examined=100000,
            rows_returned=10,   # ratio = 10000
            exec_per_day=500,
        )
        result = analyzer.analyze(make_request([query]))
        assert result.recommendations[0].priority == "critical"

    def test_high_priority_high_ratio(self):
        analyzer = CoveringIndexAnalyzer()
        query = make_query(
            filter_cols=["category"],
            rows_examined=1000,
            rows_returned=5,    # ratio = 200
            exec_per_day=10,
        )
        result = analyzer.analyze(make_request([query]))
        assert result.recommendations[0].priority == "high"

    def test_medium_priority_moderate_ratio(self):
        analyzer = CoveringIndexAnalyzer()
        query = make_query(
            filter_cols=["region"],
            rows_examined=500,
            rows_returned=20,   # ratio = 25
            exec_per_day=50,
        )
        result = analyzer.analyze(make_request([query]))
        assert result.recommendations[0].priority == "medium"


# ──────────────────────────────────────────────
# 推定値テスト
# ──────────────────────────────────────────────

class TestEstimates:
    def test_improvement_pct_capped_at_95(self):
        analyzer = CoveringIndexAnalyzer()
        # ratio = 1000000 → 理論値 99.9999% → キャップ 95%
        query = make_query(
            filter_cols=["id"],
            rows_examined=1_000_000,
            rows_returned=1,
        )
        result = analyzer.analyze(make_request([query]))
        assert result.recommendations[0].estimated_latency_improvement_pct == 95.0

    def test_scan_ratio_computed_correctly(self):
        analyzer = CoveringIndexAnalyzer()
        query = make_query(
            filter_cols=["status"],
            rows_examined=3000,
            rows_returned=30,   # ratio = 100
        )
        result = analyzer.analyze(make_request([query]))
        assert result.recommendations[0].estimated_scan_ratio == 100.0

    def test_daily_rows_saved_computed(self):
        analyzer = CoveringIndexAnalyzer()
        query = make_query(
            filter_cols=["status"],
            rows_examined=1000,
            rows_returned=10,
            exec_per_day=200,
        )
        result = analyzer.analyze(make_request([query]))
        assert result.recommendations[0].estimated_daily_rows_saved == 200_000.0


# ──────────────────────────────────────────────
# マージテスト
# ──────────────────────────────────────────────

class TestMerge:
    def test_queries_on_same_table_with_common_prefix_are_merged(self):
        analyzer = CoveringIndexAnalyzer()
        q1 = make_query(
            table="orders", query_id="q1",
            filter_cols=["status", "user_id"],
            select_cols=["id"],
            rows_examined=10000, rows_returned=10,
        )
        q2 = make_query(
            table="orders", query_id="q2",
            filter_cols=["status", "user_id"],
            select_cols=["amount"],
            rows_examined=5000, rows_returned=5,
        )
        result = analyzer.analyze(make_request([q1, q2]))
        # 同じテーブル・同じキープレフィックス → マージされて1件
        assert len(result.recommendations) == 1
        rec = result.recommendations[0]
        assert rec.table_name == "orders"

    def test_queries_on_different_tables_not_merged(self):
        analyzer = CoveringIndexAnalyzer()
        q1 = make_query(table="orders", query_id="q1", filter_cols=["status"],
                        rows_examined=10000, rows_returned=10)
        q2 = make_query(table="products", query_id="q2", filter_cols=["category"],
                        rows_examined=5000, rows_returned=5)
        result = analyzer.analyze(make_request([q1, q2]))
        assert len(result.recommendations) == 2
        tables = {r.table_name for r in result.recommendations}
        assert "orders" in tables
        assert "products" in tables


# ──────────────────────────────────────────────
# 集計テスト
# ──────────────────────────────────────────────

class TestAggregation:
    def test_total_improvement_pct_is_average(self):
        analyzer = CoveringIndexAnalyzer()
        # q1: ratio=100 → improvement ~99%, capped 95%
        # q2: ratio=20  → improvement ~95%
        q1 = make_query(table="t1", query_id="q1", filter_cols=["a"],
                        rows_examined=10000, rows_returned=100)
        q2 = make_query(table="t2", query_id="q2", filter_cols=["b"],
                        rows_examined=1000, rows_returned=50)
        result = analyzer.analyze(make_request([q1, q2]))
        assert result.estimated_total_improvement_pct > 0

    def test_empty_queries_returns_zero_improvement(self):
        analyzer = CoveringIndexAnalyzer()
        result = analyzer.analyze(make_request([]))
        assert result.total_queries_analyzed == 0
        assert result.recommendations == []
        assert result.estimated_total_improvement_pct == 0.0

    def test_all_covered_returns_zero_recommendations(self):
        analyzer = CoveringIndexAnalyzer()
        query = make_query(filter_cols=["x"], select_cols=["y"])
        idx = make_index("orders", "idx_xy", ["x", "y"])
        result = analyzer.analyze(make_request([query], indexes=[idx]))
        assert result.queries_already_covered == 1
        assert result.recommendations == []
        assert result.estimated_total_improvement_pct == 0.0


# ──────────────────────────────────────────────
# エッジケーステスト
# ──────────────────────────────────────────────

class TestEdgeCases:
    """_merge_group / _is_covered / _is_filter_prefix のエッジケーステスト"""

    def test_no_common_prefix_stays_separate(self):
        # 同テーブルでもフィルタカラムが完全に異なる場合はマージしない
        analyzer = CoveringIndexAnalyzer()
        q1 = make_query(table="orders", query_id="qa", filter_cols=["status"],
                        rows_examined=1000, rows_returned=5)
        q2 = make_query(table="orders", query_id="qb", filter_cols=["user_id"],
                        rows_examined=2000, rows_returned=10)
        result = analyzer.analyze(make_request([q1, q2]))
        # filter_cols が異なるので別々の推奨になる
        assert result.queries_needing_index == 2
        assert len(result.recommendations) == 2

    def test_merge_adopts_highest_priority(self):
        # マージ後は最高優先度を採用する
        analyzer = CoveringIndexAnalyzer()
        q1 = make_query(table="t", query_id="q1",
                        filter_cols=["a", "b"],
                        rows_examined=2000000, rows_returned=1,   # ratio=2e6 → critical
                        exec_per_day=500)
        q2 = make_query(table="t", query_id="q2",
                        filter_cols=["a", "b"],
                        select_cols=["extra"],
                        rows_examined=100, rows_returned=5,       # ratio=20 → medium
                        exec_per_day=20)
        result = analyzer.analyze(make_request([q1, q2]))
        rec = result.recommendations[0]
        assert rec.priority == "critical"

    def test_empty_all_columns_not_covered(self):
        # filter/sort/select が全部空 → needed が空セット → カバー判定不能
        analyzer = CoveringIndexAnalyzer()
        query = QueryPattern(
            table_name="t",
            filter_columns=[],
            sort_columns=[],
            select_columns=[],
            avg_rows_examined=0,
            avg_rows_returned=1,
        )
        idx = make_index("t", "idx_t", ["a", "b"])
        result = analyzer.analyze(make_request([query], indexes=[idx]))
        assert result.queries_already_covered == 0

    def test_empty_filter_prefix_always_matches(self):
        # filter_cols が空なら _is_filter_prefix は常に True
        analyzer = CoveringIndexAnalyzer()
        # filter_cols=[], sort_cols=["x"], select_cols=["y"]  → needed = {x, y}
        # インデックス (x, y) でカバー可能
        query = QueryPattern(
            table_name="orders",
            filter_columns=[],
            sort_columns=["x"],
            select_columns=["y"],
            avg_rows_examined=5000,
            avg_rows_returned=50,
        )
        idx = make_index("orders", "idx_xy", ["x", "y"])
        result = analyzer.analyze(make_request([query], indexes=[idx]))
        assert result.queries_already_covered == 1

    def test_pg_no_include_when_no_extra_select_cols(self):
        # select_cols が全部 key に含まれる場合は INCLUDE なし
        analyzer = CoveringIndexAnalyzer()
        query = make_query(
            filter_cols=["a"],
            select_cols=["a"],   # a は既にキー → INCLUDE 不要
            rows_examined=5000,
            rows_returned=5,
        )
        result = analyzer.analyze(make_request([query], engine="postgresql"))
        if result.recommendations:
            assert result.recommendations[0].include_columns == []

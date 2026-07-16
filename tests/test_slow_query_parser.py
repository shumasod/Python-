"""SlowQueryParser テスト"""
import pytest
from rds_analyzer.analyzers.slow_query_parser import SlowQueryParser


MYSQL_SLOW_LOG = """
# Query_time: 2.345000  Lock_time: 0.000100 Rows_sent: 5 Rows_examined: 50000
SET timestamp=1700000000;
SELECT id, amount FROM orders WHERE status = 'pending' ORDER BY created_at;

# Query_time: 0.123000  Lock_time: 0.000050 Rows_sent: 1 Rows_examined: 10000
SET timestamp=1700000001;
SELECT name FROM users WHERE email = 'a@b.com';
"""


class TestMysqlSlowLogParsing:
    def test_parses_two_entries(self):
        result = SlowQueryParser.from_mysql_slow_log(MYSQL_SLOW_LOG)
        assert len(result) == 2

    def test_extracts_table_name(self):
        result = SlowQueryParser.from_mysql_slow_log(MYSQL_SLOW_LOG)
        assert result[0].table_name == "orders"
        assert result[1].table_name == "users"

    def test_extracts_filter_columns(self):
        result = SlowQueryParser.from_mysql_slow_log(MYSQL_SLOW_LOG)
        assert "status" in result[0].filter_columns
        assert "email" in result[1].filter_columns

    def test_extracts_sort_columns(self):
        result = SlowQueryParser.from_mysql_slow_log(MYSQL_SLOW_LOG)
        assert "created_at" in result[0].sort_columns

    def test_extracts_select_columns(self):
        result = SlowQueryParser.from_mysql_slow_log(MYSQL_SLOW_LOG)
        assert "id" in result[0].select_columns or "amount" in result[0].select_columns

    def test_rows_examined_correct(self):
        result = SlowQueryParser.from_mysql_slow_log(MYSQL_SLOW_LOG)
        assert result[0].avg_rows_examined == 50000.0
        assert result[0].avg_rows_returned == 5.0

    def test_latency_converted_to_ms(self):
        result = SlowQueryParser.from_mysql_slow_log(MYSQL_SLOW_LOG)
        assert abs(result[0].avg_latency_ms - 2345.0) < 1.0

    def test_query_id_assigned(self):
        result = SlowQueryParser.from_mysql_slow_log(MYSQL_SLOW_LOG)
        assert result[0].query_id.startswith("slow_")

    def test_empty_log_returns_empty_list(self):
        result = SlowQueryParser.from_mysql_slow_log("")
        assert result == []


class TestPgStatStatementsParsing:
    def test_parses_rows(self):
        rows = [
            {"query": "SELECT id, name FROM users WHERE email = $1", "calls": 1000, "mean_exec_time": 50.0, "rows": 1000},
            {"query": "SELECT * FROM products WHERE category = $1 ORDER BY price", "calls": 500, "mean_exec_time": 120.0, "rows": 2500},
        ]
        result = SlowQueryParser.from_pg_stat_statements(rows)
        assert len(result) == 2

    def test_extracts_table(self):
        rows = [{"query": "SELECT id FROM orders WHERE status = $1", "calls": 100, "mean_exec_time": 30.0, "rows": 100}]
        result = SlowQueryParser.from_pg_stat_statements(rows)
        assert result[0].table_name == "orders"

    def test_daily_exec_count_normalized(self):
        rows = [{"query": "SELECT id FROM t WHERE a = $1", "calls": 3000, "mean_exec_time": 10.0, "rows": 3000}]
        result = SlowQueryParser.from_pg_stat_statements(rows)
        assert abs(result[0].execution_count_per_day - 100.0) < 1.0

    def test_empty_rows_returns_empty(self):
        assert SlowQueryParser.from_pg_stat_statements([]) == []

    def test_no_from_clause_skipped(self):
        rows = [{"query": "SET search_path = public", "calls": 1, "mean_exec_time": 0.1, "rows": 0}]
        result = SlowQueryParser.from_pg_stat_statements(rows)
        assert result == []

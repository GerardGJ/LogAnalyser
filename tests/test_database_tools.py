import pytest
import polars as pl

import src.tools.database_tools as database_tools
from src.engines.duckdb_engine import DuckDBEngine

SAMPLE_LOGS = pl.DataFrame({
    "timestamp": ["2026-08-04 10:00:00", "2026-08-04 10:01:00"],
    "level": ["INFO", "ERROR"],
    "app": ["sleep_app", "sleep_app"],
    "source_file": ["main.py", "main.py"],
    "line_number": [10, 42],
    "message": ["Server started", "Database connection lost"],
})


@pytest.fixture
def populated_tools_engine(monkeypatch, tmp_path):
    """Points the module-level `engine` used by the tools at a throwaway,
    pre-populated DuckDB file for the duration of the test.

    The tools open a fresh `with engine:` connection per call (by design, see
    CLAUDE.md), so an in-memory ":memory:" database would be wiped between
    calls; a temp file persists data across those reconnects instead.
    """
    test_engine = DuckDBEngine(database_path=str(tmp_path / "test.db"))
    with test_engine:
        test_engine.insert(SAMPLE_LOGS)
    monkeypatch.setattr(database_tools, "engine", test_engine)
    return test_engine


class TestRejectUnsafeQuery:
    @pytest.mark.parametrize(
        "query",
        [
            "SELECT * FROM logs",
            "  select level, count(*) from logs group by level",
            "WITH t AS (SELECT * FROM logs) SELECT * FROM t",
            "SHOW TABLES",
            "DESCRIBE logs",
            "EXPLAIN SELECT * FROM logs",
        ],
    )
    def test_allows_read_only_queries(self, query):
        database_tools._reject_unsafe_query(query)  # should not raise

    @pytest.mark.parametrize(
        "query",
        [
            "INSERT INTO logs VALUES (1, 2, 3)",
            "UPDATE logs SET level = 'INFO'",
            "DELETE FROM logs",
            "DROP TABLE logs",
            "CREATE TABLE evil (x INT)",
            "ALTER TABLE logs ADD COLUMN x INT",
            "ATTACH 'other.db' AS other",
            "PRAGMA memory_limit='1GB'",
        ],
    )
    def test_rejects_non_read_only_leading_keyword(self, query):
        with pytest.raises(ValueError, match="read-only"):
            database_tools._reject_unsafe_query(query)

    def test_rejects_stacked_statement(self):
        with pytest.raises(ValueError):
            database_tools._reject_unsafe_query("SELECT * FROM logs; DROP TABLE logs;")

    def test_rejects_comment_smuggling(self):
        with pytest.raises(ValueError):
            database_tools._reject_unsafe_query("SELECT * FROM logs -- ; DROP TABLE logs")

    def test_rejects_dml_keyword_after_valid_leading_keyword(self):
        with pytest.raises(ValueError, match="Unsafe SQL query"):
            database_tools._reject_unsafe_query(
                "WITH deleted AS (DELETE FROM logs RETURNING *) SELECT * FROM deleted"
            )

    def test_rejects_empty_query(self):
        with pytest.raises(ValueError, match="empty"):
            database_tools._reject_unsafe_query("   ")


class TestSqlDbQueryTool:
    def test_executes_select_and_returns_rows(self, populated_tools_engine):
        result = database_tools.sql_db_query.func("SELECT * FROM logs ORDER BY line_number")
        assert "Server started" in result
        assert "Database connection lost" in result

    def test_empty_result_message(self, populated_tools_engine):
        result = database_tools.sql_db_query.func("SELECT * FROM logs WHERE level = 'DEBUG'")
        assert result == "Query executed successfully. Result is empty."

    def test_blocks_drop_table_and_leaves_data_intact(self, populated_tools_engine):
        result = database_tools.sql_db_query.func("DROP TABLE logs")
        assert "Error executing query" in result

        # The table must still exist and be queryable after the rejected DROP.
        follow_up = database_tools.sql_db_query.func("SELECT COUNT(*) FROM logs")
        assert "Error" not in follow_up

    def test_blocks_stacked_select_and_drop(self, populated_tools_engine):
        result = database_tools.sql_db_query.func("SELECT * FROM logs; DROP TABLE logs;")
        assert "Error executing query" in result
        follow_up = database_tools.sql_db_query.func("SELECT COUNT(*) FROM logs")
        assert "Error" not in follow_up

    def test_pii_in_results_is_scrubbed(self, monkeypatch, tmp_path):
        pii_logs = pl.DataFrame({
            "timestamp": ["2026-08-04 10:02:00"],
            "level": ["INFO"],
            "app": ["sleep_app"],
            "source_file": ["main.py"],
            "line_number": [99],
            "message": ["contact admin@example.com"],
        })
        test_engine = DuckDBEngine(database_path=str(tmp_path / "pii.db"))
        with test_engine:
            test_engine.insert(pii_logs)
        monkeypatch.setattr(database_tools, "engine", test_engine)

        result = database_tools.sql_db_query.func("SELECT * FROM logs WHERE line_number = 99")
        assert "admin@example.com" not in result
        assert "[REDACTED_EMAIL]" in result


class TestSqlDbListTablesTool:
    def test_lists_logs_table(self, populated_tools_engine):
        result = database_tools.sql_db_list_tables.func()
        assert "logs" in result


class TestSqlDbSchemaTool:
    def test_returns_schema_and_sample_rows(self, populated_tools_engine):
        result = database_tools.sql_db_schema.func("logs")
        assert "message" in result
        assert "Sample rows" in result

    def test_handles_unknown_table(self, populated_tools_engine):
        result = database_tools.sql_db_schema.func("does_not_exist")
        assert "Error" in result


class TestSqlDbQueryCheckerTool:
    def test_cleans_markdown_fences_from_model_response(self, monkeypatch):
        class FakeModel:
            def invoke(self, prompt):
                class Resp:
                    content = "```sql\nSELECT * FROM logs\n```"
                return Resp()

        monkeypatch.setattr(database_tools, "get_agent_model", lambda name: FakeModel())
        result = database_tools.sql_db_query_checker.func("SELECT * FROM logs")
        assert result == "SELECT * FROM logs"

    def test_passes_through_clean_query_unchanged(self, monkeypatch):
        class FakeModel:
            def invoke(self, prompt):
                class Resp:
                    content = "SELECT level FROM logs"
                return Resp()

        monkeypatch.setattr(database_tools, "get_agent_model", lambda name: FakeModel())
        result = database_tools.sql_db_query_checker.func("SELECT level FROM logs")
        assert result == "SELECT level FROM logs"

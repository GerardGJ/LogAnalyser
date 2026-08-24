import pytest
import polars as pl

from src.engines.base_engine import EngineConnectionError
from src.engines.duckdb_engine import DuckDBEngine


SAMPLE_LOGS = pl.DataFrame({
    "timestamp": ["2026-08-04 10:00:00", "2026-08-04 10:01:00", "2026-08-04 10:02:00"],
    "level": ["INFO", "ERROR", "ERROR"],
    "app": ["sleep_app", "sleep_app", "sleep_app"],
    "source_file": ["main.py", "main.py", "train.py"],
    "line_number": [10, 42, 105],
    "message": ["Server started", "Database connection lost", "Pipeline failed"],
})


@pytest.fixture
def engine():
    """A fresh, unconnected in-memory DuckDB engine."""
    return DuckDBEngine(database_path=":memory:")


@pytest.fixture
def populated_engine():
    """Sets up an in-memory DuckDB instance pre-populated with sample log data."""
    engine = DuckDBEngine(database_path=":memory:")
    with engine:
        engine.insert(SAMPLE_LOGS)
        yield engine


# --- Connection lifecycle ---


class TestConnectionLifecycle:
    def test_not_connected_by_default(self, engine):
        assert engine.is_connected is False

    def test_connect_sets_connected_flag(self, engine):
        engine.connect()
        try:
            assert engine.is_connected is True
        finally:
            engine.disconnect()

    def test_disconnect_clears_connected_flag(self, engine):
        engine.connect()
        engine.disconnect()
        assert engine.is_connected is False

    def test_disconnect_without_connect_is_a_noop(self, engine):
        # Edge case: disconnecting a never-connected engine should not raise.
        engine.disconnect()
        assert engine.is_connected is False

    def test_double_connect_is_idempotent(self, engine):
        # Edge case: calling connect() twice should not error or leak connections.
        engine.connect()
        first_conn = engine._conn
        engine.connect()
        try:
            assert engine._conn is first_conn
        finally:
            engine.disconnect()

    def test_context_manager_connects_and_disconnects(self, engine):
        assert engine.is_connected is False
        with engine as ctx:
            assert ctx is engine
            assert engine.is_connected is True
        assert engine.is_connected is False

    def test_context_manager_disconnects_on_exception(self, engine):
        # Edge case: an error inside the `with` block must not leak the connection.
        with pytest.raises(ValueError):
            with engine:
                assert engine.is_connected is True
                raise ValueError("boom")
        assert engine.is_connected is False

    @pytest.mark.parametrize(
        "method,args",
        [
            ("execute_query", ("SELECT 1",)),
            ("get_schema", ()),
            ("insert", (SAMPLE_LOGS,)),
            ("get_by_id", ("1",)),
            ("delete_record", ("1",)),
            ("delete_filter", ("level = 'INFO'",)),
        ],
    )
    def test_operations_require_connection(self, engine, method, args):
        # Edge case: every public template method must refuse to run while disconnected.
        with pytest.raises(EngineConnectionError):
            getattr(engine, method)(*args)


# --- Schema inspection ---


class TestSchemaInspection:
    def test_get_schema_for_known_table(self, populated_engine):
        schema = populated_engine.get_schema("logs")

        assert set(schema["column_name"]) == {
            "timestamp", "level", "app", "source_file", "line_number", "message",
        }

    def test_get_schema_without_table_name_lists_all_tables(self, populated_engine):
        schema = populated_engine.get_schema()

        assert "table_name" in schema.columns
        assert "logs" in schema["table_name"].to_list()

    def test_get_schema_for_unknown_table_raises(self, populated_engine):
        # Edge case: DESCRIBE on a nonexistent table should surface as an error, not silently empty.
        with pytest.raises(Exception):
            populated_engine.get_schema("does_not_exist")


# --- Parameterized queries ---


class TestParameterizedQueries:
    def test_execute_query_with_params(self, populated_engine):
        result = populated_engine.execute_query(
            "SELECT * FROM logs WHERE level = ?", params=("ERROR",)
        )
        assert len(result) == 2

    def test_get_by_id_returns_matching_row(self, populated_engine):
        result = populated_engine.get_by_id("0")
        assert len(result) == 1
        assert result["app"][0] == "sleep_app"

    def test_get_by_id_missing_id_returns_empty(self, populated_engine):
        # Edge case: an id with no matching row should return an empty result, not raise.
        result = populated_engine.get_by_id("9999")
        assert result.is_empty()

    def test_get_by_id_non_numeric_id_returns_empty(self, populated_engine):
        # Edge case: rowid casts to VARCHAR, so a non-numeric id just fails to match.
        result = populated_engine.get_by_id("not-a-rowid")
        assert result.is_empty()

    def test_delete_record_removes_only_target_row(self, populated_engine):
        before = populated_engine.execute_query("SELECT COUNT(*) AS n FROM logs")["n"][0]
        populated_engine.delete_record("0")
        after = populated_engine.execute_query("SELECT COUNT(*) AS n FROM logs")["n"][0]
        assert after == before - 1

    def test_delete_record_missing_id_is_a_noop(self, populated_engine):
        # Edge case: deleting a nonexistent id should not raise or affect row count.
        before = populated_engine.execute_query("SELECT COUNT(*) AS n FROM logs")["n"][0]
        populated_engine.delete_record("9999")
        after = populated_engine.execute_query("SELECT COUNT(*) AS n FROM logs")["n"][0]
        assert after == before


# --- Inserts ---


class TestInsert:
    def test_insert_dataframe_creates_logs_table(self, engine):
        with engine:
            engine.insert(SAMPLE_LOGS)
            result = engine.execute_query("SELECT COUNT(*) AS n FROM logs")
        assert result["n"][0] == 3

    def test_insert_empty_dataframe(self, engine):
        # Edge case: inserting a zero-row (but schema-bearing) DataFrame should not error.
        empty = SAMPLE_LOGS.clear()
        with engine:
            engine.insert(empty)
            result = engine.execute_query("SELECT COUNT(*) AS n FROM logs")
        assert result["n"][0] == 0

    def test_insert_is_idempotent_for_existing_table(self, engine):
        # Edge case: CREATE TABLE IF NOT EXISTS means a second insert must not duplicate rows.
        with engine:
            engine.insert(SAMPLE_LOGS)
            engine.insert(SAMPLE_LOGS)
            result = engine.execute_query("SELECT COUNT(*) AS n FROM logs")
        assert result["n"][0] == 3

    def test_insert_unsupported_type_raises(self, engine):
        with engine:
            with pytest.raises(ValueError):
                engine.insert(12345)

    def test_insert_csv_file(self, engine, tmp_path):
        csv_path = tmp_path / "logs.csv"
        SAMPLE_LOGS.write_csv(csv_path)

        with engine:
            engine.insert(csv_path)
            result = engine.execute_query("SELECT COUNT(*) AS n FROM logs")
        assert result["n"][0] == 3

    def test_insert_json_file(self, engine, tmp_path):
        json_path = tmp_path / "logs.json"
        SAMPLE_LOGS.write_json(json_path)

        with engine:
            engine.insert(json_path)
            result = engine.execute_query("SELECT COUNT(*) AS n FROM logs")
        assert result["n"][0] == 3

    def test_insert_parquet_file(self, engine, tmp_path):
        parquet_path = tmp_path / "logs.parquet"
        SAMPLE_LOGS.write_parquet(parquet_path)

        with engine:
            engine.insert(parquet_path)
            result = engine.execute_query("SELECT COUNT(*) AS n FROM logs")
        assert result["n"][0] == 3

    def test_insert_unsupported_extension_raises(self, engine, tmp_path):
        # Edge case: an unrecognized extension (e.g. raw .log text) must be rejected,
        # not silently treated as CSV.
        log_path = tmp_path / "pipeline.log"
        log_path.write_text("2026-08-04 10:00:00 [INFO] sleep_app (main.py:1): hello\n")

        with engine:
            with pytest.raises(ValueError):
                engine.insert(log_path)

    def test_insert_missing_file_raises(self, engine, tmp_path):
        missing_path = tmp_path / "does_not_exist.csv"

        with engine:
            with pytest.raises(FileNotFoundError):
                engine.insert(missing_path)

    def test_insert_file_path_with_quote_is_escaped(self, engine, tmp_path):
        # Edge case: a filename containing a single quote must not break out of the
        # interpolated SQL string.
        quirky_dir = tmp_path / "o'brien"
        quirky_dir.mkdir()
        csv_path = quirky_dir / "logs.csv"
        SAMPLE_LOGS.write_csv(csv_path)

        with engine:
            engine.insert(csv_path)
            result = engine.execute_query("SELECT COUNT(*) AS n FROM logs")
        assert result["n"][0] == 3


# --- PII-scrubbed query results ---


class TestPiiScrubbing:
    @pytest.fixture
    def engine_with_pii(self):
        pii_logs = pl.DataFrame({
            "timestamp": ["2026-08-04 10:00:00"],
            "level": ["ERROR"],
            "app": ["sleep_app"],
            "source_file": ["main.py"],
            "line_number": [1],
            "message": [
                "Failed request from 10.0.0.5 for user jane.doe@example.com "
                "with api_key=sk_live_abcdef1234567890"
            ],
        })
        engine = DuckDBEngine(database_path=":memory:")
        with engine:
            engine.insert(pii_logs)
            yield engine

    def test_query_results_scrub_email_and_ip(self, engine_with_pii):
        result = engine_with_pii.execute_query("SELECT message FROM logs")
        message = result["message"][0]

        assert "jane.doe@example.com" not in message
        assert "10.0.0.5" not in message
        assert "[REDACTED_EMAIL]" in message
        assert "[REDACTED_IP]" in message

    def test_query_results_scrub_api_key(self, engine_with_pii):
        result = engine_with_pii.execute_query("SELECT message FROM logs")
        message = result["message"][0]

        assert "sk_live_abcdef1234567890" not in message
        assert "[REDACTED_API_KEY]" in message

    def test_scrubbing_does_not_touch_non_string_columns(self, engine_with_pii):
        # Edge case: numeric columns must pass through scrub_dataframe untouched.
        result = engine_with_pii.execute_query("SELECT line_number FROM logs")
        assert result["line_number"][0] == 1


# --- delete_filter validation ---


class TestDeleteFilter:
    def test_valid_filter_deletes_matching_rows(self, populated_engine):
        populated_engine.delete_filter("level = 'ERROR'")
        result = populated_engine.execute_query("SELECT COUNT(*) AS n FROM logs")
        assert result["n"][0] == 1

    def test_filter_matching_no_rows_is_a_noop(self, populated_engine):
        # Edge case: a well-formed filter with no matches should not raise or delete anything.
        populated_engine.delete_filter("level = 'FATAL'")
        result = populated_engine.execute_query("SELECT COUNT(*) AS n FROM logs")
        assert result["n"][0] == 3

    def test_empty_filter_raises(self, populated_engine):
        with pytest.raises(ValueError):
            populated_engine.delete_filter("")

    def test_whitespace_only_filter_raises(self, populated_engine):
        with pytest.raises(ValueError):
            populated_engine.delete_filter("   ")

    @pytest.mark.parametrize(
        "malicious_filter",
        [
            "1=1; DROP TABLE logs",
            "1=1 -- comment",
            "1=1 /* comment */ OR 1=1",
            "1=1); DROP TABLE logs; --",
            "1=1; ATTACH 'evil.db' AS evil",
            "1=1; PRAGMA table_info(logs)",
            "level = 'INFO' UNION SELECT * FROM logs; INSERT INTO logs VALUES (1)",
        ],
    )
    def test_unsafe_filter_is_rejected(self, populated_engine, malicious_filter):
        with pytest.raises(ValueError):
            populated_engine.delete_filter(malicious_filter)

        # The rejected filter must not have mutated the table.
        result = populated_engine.execute_query("SELECT COUNT(*) AS n FROM logs")
        assert result["n"][0] == 3

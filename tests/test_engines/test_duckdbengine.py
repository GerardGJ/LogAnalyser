import pytest
import polars as pl
from src.engines.duckdb_engine import DuckDBEngine


@pytest.fixture
def populated_engine():
    """Sets up an in-memory DuckDB instance pre-populated with sample log data."""
    # Create sample log records as a Polars DataFrame
    sample_logs = pl.DataFrame({
        "timestamp": ["2026-08-04 10:00:00", "2026-08-04 10:01:00", "2026-08-04 10:02:00"],
        "level": ["INFO", "ERROR", "ERROR"],
        "app": ["sleep_app", "sleep_app", "sleep_app"],
        "source_file": ["main.py", "main.py", "train.py"],
        "line_number": [10, 42, 105],
        "message": ["Server started", "Database connection lost", "Pipeline failed"]
    })

    # Initialize in-memory engine and populate table
    engine = DuckDBEngine(database_path=":memory:")
    with engine:
        engine.insert(sample_logs)
        yield engine  # Yield control to the test function


def test_query_database(populated_engine):
    query = "SELECT COUNT(*) AS error_count FROM logs WHERE level = 'ERROR'"
    
    result = populated_engine.execute_query(query)

    # 1. Assert result is not empty
    assert len(result) > 0

    # 2. Assert the specific error count returned in the first row/column
    assert result["error_count"][0] == 2
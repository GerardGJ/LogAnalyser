from pathlib import Path
from typing import Any, Union
import duckdb
import polars as pl

from src.engines.relational_engine import RelationalEngine


class DuckDBEngine(RelationalEngine):
    """
    DuckDB-backed analytical database engine for executing SQL queries
    directly over in-memory tables, Parquet files, or raw log data frames.
    """

    def __init__(self, database_path: str = ":memory:") -> None:
        super().__init__()
        self.database_path = database_path
        self._conn: duckdb.DuckDBPyConnection | None = None

    def connect(self) -> None:
        """Establishes a connection to the DuckDB database."""
        if not self._is_connected:
            self._conn = duckdb.connect(database=self.database_path)
            self._is_connected = True

    def disconnect(self) -> None:
        """Closes the active DuckDB connection."""
        if self._is_connected and self._conn:
            self._conn.close()
            self._conn = None
            self._is_connected = False

    # --- RelationalEngine Hooks ---

    def _execute_query(
        self, query: str, params: tuple | None = None
    ) -> pl.DataFrame:
        """
        Executes a SQL query against DuckDB and returns the result set
        as a Polars DataFrame.
        """
        if params:
            result = self._conn.execute(query, params)
        else:
            result = self._conn.execute(query)

        # Convert DuckDB result set directly to a Polars DataFrame
        return result.pl()

    def _get_schema(self, table_name: str | None = None) -> pl.DataFrame:
        """
        Retrieves table metadata and column types using DuckDB's standard
        information schema or DESCRIBE statement.
        """
        if table_name:
            query = f"DESCRIBE {table_name};"
        else:
            query = """
                SELECT table_name, column_name, data_type 
                FROM information_schema.columns 
                ORDER BY table_name, ordinal_position;
            """
        return self._execute_query(query)

    # --- BaseEngine Hooks ---

    def _insert(self, data: Union[pl.DataFrame, str, Path]) -> None:
        """
        Registers or inserts a Polars DataFrame or log file path into DuckDB.
        If a Polars DataFrame is passed, it registers it into the active DuckDB connection.
        """
        if isinstance(data, pl.DataFrame):
            # Registers the Polars DataFrame in memory under 'logs'
            logs_df = data  # noqa: F841
            self._conn.execute("CREATE TABLE IF NOT EXISTS logs AS SELECT * FROM logs_df")
        elif isinstance(data, (str, Path)):
            # Direct SQL query over file paths (CSV/Parquet/JSON)
            self._conn.execute(
                f"CREATE TABLE IF NOT EXISTS logs AS SELECT * FROM read_csv_auto('{data}')"
            )
        else:
            raise ValueError(f"Unsupported data type for insertion: {type(data)}")

    def _get_by_id(self, record_id: str) -> pl.DataFrame:
        """Fetches a log record by its identifier (e.g., trace_id or rowid)."""
        query = "SELECT * FROM logs WHERE trace_id = ?"
        return self._execute_query(query, params=(record_id,))

    def _delete_record(self, record_id: str) -> None:
        """Deletes a record matching a specific trace_id."""
        query = "DELETE FROM logs WHERE trace_id = ?"
        self._execute_query(query, params=(record_id,))

    def _delete_filter(self, filter: str) -> None:
        """Deletes records matching a raw SQL WHERE condition."""
        query = f"DELETE FROM logs WHERE {filter}"
        self._execute_query(query)

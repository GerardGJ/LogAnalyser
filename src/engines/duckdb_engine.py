import re
from pathlib import Path
from typing import Any, Union
import duckdb
import polars as pl

from src.engines.relational_engine import RelationalEngine
from src.security.pii_scrubber import scrub_dataframe

# Maps a supported file extension to the DuckDB table function used to read it.
# Ingestion is restricted to this allowlist so arbitrary files can't be read
# through an unexpected DuckDB reader.
_FILE_READERS = {
    ".csv": "read_csv_auto",
    ".json": "read_json_auto",
    ".jsonl": "read_json_auto",
    ".parquet": "read_parquet",
}

# Denylist of tokens that would let a `delete_filter()` caller escape the
# intended WHERE-clause context (statement chaining, comments, DDL/DML).
_UNSAFE_FILTER_PATTERN = re.compile(
    r";"
    r"|--"
    r"|/\*"
    r"|\b(ATTACH|DETACH|PRAGMA|INSTALL|LOAD|COPY|INSERT|UPDATE|DROP|CREATE|ALTER|EXEC|EXECUTE|CALL)\b",
    re.IGNORECASE,
)


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
        scrubbed_result = scrub_dataframe(result.pl())
        return scrubbed_result

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
            self._insert_file(Path(data))
        else:
            raise ValueError(f"Unsupported data type for insertion: {type(data)}")

    def _insert_file(self, path: Path) -> None:
        """
        Loads a CSV, JSON/JSONL, or Parquet file into the `logs` table using
        DuckDB's native readers, chosen from an extension allowlist rather
        than trusting the caller-provided format.
        """
        if not path.is_file():
            raise FileNotFoundError(f"Log file not found: {path}")

        reader = _FILE_READERS.get(path.suffix.lower())
        if reader is None:
            supported = ", ".join(sorted(_FILE_READERS))
            raise ValueError(
                f"Unsupported file extension '{path.suffix}' for ingestion. "
                f"Supported formats: {supported}"
            )

        # DuckDB table functions don't accept bound parameters for filenames,
        # so the resolved path is quote-escaped before interpolation.
        resolved = str(path.resolve()).replace("'", "''")
        self._conn.execute(
            f"CREATE TABLE IF NOT EXISTS logs AS SELECT * FROM {reader}('{resolved}')"
        )

    def _get_by_id(self, record_id: str) -> pl.DataFrame:
        """Fetches a log record by DuckDB's internal rowid."""
        query = "SELECT * FROM logs WHERE CAST(rowid AS VARCHAR) = ?"
        return self._execute_query(query, params=(record_id,))

    def _delete_record(self, record_id: str) -> None:
        """Deletes a log record by DuckDB's internal rowid."""
        query = "DELETE FROM logs WHERE CAST(rowid AS VARCHAR) = ?"
        self._execute_query(query, params=(record_id,))

    def _delete_filter(self, filter: str) -> None:
        """Deletes records matching a restricted, single-condition SQL WHERE clause."""
        if not filter or not filter.strip():
            raise ValueError("delete_filter() requires a non-empty WHERE condition.")
        if _UNSAFE_FILTER_PATTERN.search(filter):
            raise ValueError(f"Unsafe SQL filter rejected: {filter!r}")

        query = f"DELETE FROM logs WHERE {filter}"
        self._execute_query(query)

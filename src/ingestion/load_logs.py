from pathlib import Path
from typing import Union
from src.engines.duckdb_engine import DuckDBEngine
from src.utils.log_loader import load_logs
from config.settings import DUCKDB_PATH, LOGS_PATH

def ingest_log_file(log_file_path: Union[str,Path], db_path: str = "logdatabase.db") -> int:
    """Reads a log file, converts it to Polars DataFrame, and writes to DuckDB."""
    path = Path(log_file_path)
    if not path.exists():
        raise FileNotFoundError(f"Log file not found: {path}")

    df = load_logs(str(path))

    with DuckDBEngine(database_path=db_path) as engine:
        engine.insert(df)

    return len(df)

if __name__ == "__main__":
    rows_inserted = ingest_log_file(LOGS_PATH, DUCKDB_PATH)
    print(f"Successfully loaded {rows_inserted} records into database.")
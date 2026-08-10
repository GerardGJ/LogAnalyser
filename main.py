from src.engines.duckdb_engine import DuckDBEngine
from config.settings import DUCKDB_PATH


def main():
    with DuckDBEngine(DUCKDB_PATH) as engine:
        schema = engine.get_schema("logs")

        rows = engine.execute_query("SELECT * FROM logs LIMIT 3")
    print(f"/*\n 3 rows from logs table:\n"
        + "\t".join(schema["column_name"])
        + "\n"
        + "\n".join("\t".join(str(x) for x in row) for row in rows.iter_rows())
        + "\n*/"
    )



if __name__ == "__main__":
    main()

import re
from pathlib import Path
from typing import Union
import polars as pl

# Regex pattern matching standard log headers:
# e.g., "2026-08-03 10:06:20 [INFO] sleep_app (train.py:156): "
LOG_PATTERN = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s+"
    r"\[(?P<level>[A-Z]+)\]\s+"
    r"(?P<app>\w+)\s+"
    r"\((?P<source_file>[^:]+):(?P<line_number>\d+)\):\s+"
    r"(?P<message>.*)$"
)


def parse_log_text(log_content: str) -> pl.DataFrame:
    """Parses raw log content string into a structured Polars DataFrame."""
    records = []
    lines = log_content.splitlines()

    for line in lines:
        if not line.strip():
            continue

        match = LOG_PATTERN.match(line)
        if match:
            record = match.groupdict()
            record["line_number"] = int(record["line_number"])
            records.append(record)
        else:
            # Handle multi-line log entries (e.g., Python Tracebacks) by appending to previous message
            if records:
                records[-1]["message"] += f"\n{line}"

    if not records:
        schema = {
            "timestamp": pl.Datetime,
            "level": pl.String,
            "app": pl.String,
            "source_file": pl.String,
            "line_number": pl.Int64,
            "message": pl.String,
        }
        return pl.DataFrame(schema=schema)

    df = pl.DataFrame(records)
    
    # Cast timestamp string to proper Polars Datetime type
    return df.with_columns(
        pl.col("timestamp").str.strptime(pl.Datetime, "%Y-%m-%d %H:%M:%S")
    )


def load_logs(source: Union[str, Path]) -> pl.DataFrame:
    """Loads and parses log data from a file path or direct string content."""
    path = Path(source) if isinstance(source, str) and not source.count("\n") else None

    print(path)
    
    if path and path.is_file():
        content = path.read_text(encoding="utf-8")
    else:
        content = str(source)

    return parse_log_text(content)


if __name__ == "__main__":
    # Quick sanity check with provided example string
    sample_log = """2026-08-03 16:01:47 [ERROR] sleep_app (main.py:76): Pipeline execution failed: OrdinalEncoder.__init__() takes 1 positional argument but 2 were given
Traceback (most recent call last):
  File "C:\\Users\\Gerard\\Desktop\\SleepHabits\\backend\\main.py", line 73, in train
    results = train_pipeline(n_trials=payload.n_trials)
TypeError: OrdinalEncoder.__init__() takes 1 positional argument but 2 were given"""

    from config.settings import LOGS_PATH
    
    df = load_logs(str(LOGS_PATH))
    print(df)
    print("Schema:", df.schema)
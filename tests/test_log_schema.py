from datetime import datetime

from src.models.log_schema import LogEntry, LogLevel
from src.utils.log_loader import parse_log_text


def test_log_entry_uses_parsed_file_schema():
    entry = LogEntry(
        timestamp=datetime(2026, 8, 3, 16, 1, 47),
        level=LogLevel.ERROR,
        app="sleep_app",
        source_file="main.py",
        line_number=76,
        message="Pipeline execution failed",
    )

    assert entry.app == "sleep_app"
    assert entry.source_file == "main.py"
    assert entry.line_number == 76


def test_parse_log_text_returns_canonical_parsed_schema():
    raw_log = (
        "2026-08-03 16:01:47 [ERROR] sleep_app (main.py:76): Pipeline execution failed\n"
        "Traceback (most recent call last):\n"
        "TypeError: bad input"
    )

    df = parse_log_text(raw_log)

    assert df.columns == [
        "timestamp",
        "level",
        "app",
        "source_file",
        "line_number",
        "message",
    ]
    assert df["app"][0] == "sleep_app"
    assert df["source_file"][0] == "main.py"
    assert df["line_number"][0] == 76
    assert "TypeError: bad input" in df["message"][0]

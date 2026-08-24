import pytest

from src.tools.diagnostics_tools import parse_stack_trace, sample_and_truncate_logs


class TestParseStackTrace:
    def test_extracts_python_traceback(self):
        log = (
            "2026-08-04 10:15:03 ERROR database - Failed to acquire connection\n"
            "Traceback (most recent call last):\n"
            '  File "src/pipeline/train.py", line 105, in execute_pipeline\n'
            "    db.connect()\n"
            "duckdb.IOException: Could not set lock on file\n"
        )
        result = parse_stack_trace.func(log)
        assert "EXTRACTED STACK TRACE" in result
        assert "Traceback (most recent call last):" in result
        assert "duckdb.IOException" in result

    def test_extracts_multiple_tracebacks(self):
        log = (
            "Traceback (most recent call last):\n"
            "  File \"a.py\", line 1, in <module>\n"
            "ValueError: first failure\n"
            "\n\n"
            "Traceback (most recent call last):\n"
            "  File \"b.py\", line 2, in <module>\n"
            "KeyError: second failure\n"
        )
        result = parse_stack_trace.func(log)
        assert "ValueError: first failure" in result
        assert "KeyError: second failure" in result

    def test_traceback_at_end_of_string_without_trailing_blank_line(self):
        # Edge case: no trailing "\n\n" after the traceback (matches on \Z instead).
        log = 'Traceback (most recent call last):\n  File "x.py", line 1\nRuntimeError: boom'
        result = parse_stack_trace.func(log)
        assert "RuntimeError: boom" in result

    def test_falls_back_to_failure_keyword_lines_when_no_traceback(self):
        log = (
            "2026-08-04 10:00:00 INFO server - Request received\n"
            "2026-08-04 10:00:01 ERROR database - Connection refused\n"
            "2026-08-04 10:00:02 CRITICAL scheduler - Job queue FAILED to start\n"
        )
        result = parse_stack_trace.func(log)
        assert "Extracted Failure Lines" in result
        assert "Connection refused" in result
        assert "Job queue FAILED to start" in result
        assert "Request received" not in result

    def test_no_traceback_and_no_failure_keywords_returns_no_match_message(self):
        log = "2026-08-04 10:00:00 INFO server - Request received\n2026-08-04 10:00:01 INFO server - Request completed"
        result = parse_stack_trace.func(log)
        assert result == "No explicit stack trace or exception block detected in log data."

    def test_empty_log_returns_no_match_message(self):
        result = parse_stack_trace.func("")
        assert result == "No explicit stack trace or exception block detected in log data."

    def test_fallback_keyword_matching_is_case_insensitive(self):
        # Log lines from the project's canonical schema use upper-case levels
        # ("ERROR", "FATAL"), not the mixed-case "Error" a naive check might expect.
        log = "2026-08-04 10:00:01 [ERROR] sleep_app (main.py:76): connection refused"
        result = parse_stack_trace.func(log)
        assert "Extracted Failure Lines" in result
        assert "connection refused" in result

    def test_line_with_no_failure_keywords_is_excluded_from_fallback(self):
        log = (
            "2026-08-04 10:00:00 [INFO] sleep_app (main.py:10): server started\n"
            "2026-08-04 10:00:01 [ERROR] sleep_app (main.py:76): connection refused\n"
        )
        result = parse_stack_trace.func(log)
        assert "server started" not in result
        assert "connection refused" in result


class TestSampleAndTruncateLogs:
    def test_short_log_returned_unchanged(self):
        log = "\n".join(f"line{i}" for i in range(1, 11))
        assert sample_and_truncate_logs.func(log, max_lines=50) == log

    def test_log_exactly_at_max_lines_returned_unchanged(self):
        log = "\n".join(f"line{i}" for i in range(1, 51))
        assert sample_and_truncate_logs.func(log, max_lines=50) == log

    def test_truncates_long_log_and_preserves_head_and_tail(self):
        log = "\n".join(f"line{i}" for i in range(1, 101))
        result = sample_and_truncate_logs.func(log, max_lines=50)
        assert "TRUNCATED" in result
        assert "RECENT CRASH CONTEXT" in result
        assert "line1\n" in result
        assert "line100" in result
        # Middle of the log (no error keywords present) should be summarized away.
        assert "line50" not in result

    def test_prioritizes_error_lines_in_the_sampled_middle(self):
        middle = [f"line{i}" for i in range(1, 61)]
        middle[30] = "ERROR something broke"
        log = "\n".join([f"head{i}" for i in range(1, 16)] + middle + [f"tail{i}" for i in range(1, 21)])
        result = sample_and_truncate_logs.func(log, max_lines=50)
        assert "ERROR something broke" in result

    def test_no_head_tail_overlap_or_negative_count_on_short_input(self):
        # Edge case: total lines below head(15) + tail(20) would previously make the
        # head/tail slices overlap and duplicate lines, and drive the truncated count negative.
        log = "\n".join(f"line{i}" for i in range(1, 31))
        result = sample_and_truncate_logs.func(log, max_lines=5)
        assert "TRUNCATED -" not in result
        # line15 (last head line) and line16 (first tail line) must each appear once.
        assert result.count("line15") == 1
        assert result.count("line16") == 1

    def test_single_line_log_over_threshold(self):
        # Edge case: max_lines=0 forces the truncation path even for a single line.
        result = sample_and_truncate_logs.func("only line", max_lines=0)
        assert "only line" in result

    def test_empty_log_input(self):
        result = sample_and_truncate_logs.func("", max_lines=0)
        # strip().split("\n") on an empty string yields a single empty-string line.
        assert result is not None

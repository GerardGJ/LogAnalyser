import re
from typing import List, Dict, Any
import polars as pl
from langchain.tools import tool


@tool
def parse_stack_trace(raw_log: str) -> str:
    """
    Extracts and structures exception types, error messages, and call stack frames 
    from a raw log message or traceback block.
    """
    # Regex for standard Python/Java tracebacks
    traceback_pattern = r"(Traceback \(most recent call last\):[\s\S]*?)(?=\n\n|\Z)"
    matches = re.findall(traceback_pattern, raw_log)
    
    if matches:
        return "\n--- EXTRACTED STACK TRACE ---\n" + "\n".join(matches)
    
    # Fallback to general exception keywords
    exception_lines = [
        line for line in raw_log.split("\n") 
        if any(kw in line for kw in ["Error", "Exception", "CRITICAL", "FAILED", "Traceback"])
    ]
    
    if exception_lines:
        return "Extracted Failure Lines:\n" + "\n".join(exception_lines)
    
    return "No explicit stack trace or exception block detected in log data."


@tool
def sample_and_truncate_logs(log_data: str, max_lines: int = 50) -> str:
    """
    Samples representative log rows and truncates long text blocks to prevent exceeding 
    the model context window while preserving critical failure contexts.
    """
    lines = log_data.strip().split("\n")
    if len(lines) <= max_lines:
        return log_data

    # Strategy: Keep first 15 lines (init/context), middle sampled error lines, and last 20 lines (crash)
    head = lines[:15]
    tail = lines[-20:]
    
    middle_candidates = lines[15:-20]
    # Filter middle lines for errors or warnings
    error_middle = [l for l in middle_candidates if any(k in l for k in ["ERROR", "WARN", "FAIL"])]
    sampled_middle = error_middle[:15] if error_middle else middle_candidates[:15]

    truncated_result = (
        "\n".join(head)
        + f"\n\n... [TRUNCATED {len(lines) - (len(head) + len(tail) + len(sampled_middle))} LINES] ...\n\n"
        + "\n".join(sampled_middle)
        + "\n\n... [RECENT CRASH CONTEXT] ...\n"
        + "\n".join(tail)
    )
    return truncated_result
from dotenv import load_dotenv
from langchain.agents import create_agent

from src.security.pii_scrubber import scrub_text
from src.tools.diagnostics_tools import parse_stack_trace, sample_and_truncate_logs
from src.utils.config_loader import get_agent_model

load_dotenv()

DIAGNOSTIC_TOOLS = [parse_stack_trace, sample_and_truncate_logs]

DIAGNOSTIC_SYSTEM_PROMPT = """
You are a Diagnostic and Root-Cause Analysis Agent specialized in inspecting system logs, 
stack traces, and execution failures.

Your objective:
1. Examine the provided log messages, error outputs, or query results.
2. If the log data is large, use `sample_and_truncate_logs` to isolate relevant failure frames.
3. Use `parse_stack_trace` to extract exception hierarchies, error frames, and call stacks.
4. Perform a structured Root-Cause Analysis (RCA).

Output your final analysis using this exact format:
- **Primary Issue**: Concise summary of what failed.
- **Root Cause**: Specific underlying technical trigger (e.g., NullPointer, Database Connection Timeout, Out of Memory).
- **Affected Components/Files**: List specific functions, files, or line numbers identified in the stack trace.
- **Recommended Remediation**: Direct, actionable steps to resolve or patch the issue.
"""


def get_diagnostic_agent():
    """Factory function to instantiate the Diagnostic Agent."""
    model = get_agent_model("diagnostic_agent")
    return create_agent(
        model=model,
        tools=DIAGNOSTIC_TOOLS,
        system_prompt=DIAGNOSTIC_SYSTEM_PROMPT,
    )


def diagnose_log_failure(log_payload: str) -> str:
    """
    Public entry point for running root-cause analysis on a log snippet or error message.
    """
    agent = get_diagnostic_agent()

    scrubbed_payload = scrub_text(log_payload)
    prompt = f"Analyze the following log payload and identify the root cause of failure:\n\n{scrubbed_payload}"

    try:
        result = agent.invoke({"messages": [("user", prompt)]})
        final_message = result["messages"][-1].content
        return scrub_text(final_message)
    except Exception as e:
        return f"Diagnostic analysis failed due to error: {e}"


if __name__ == "__main__":
    # Test execution with a mock log snippet
    mock_log = """
    2026-08-04 10:15:01 INFO server - Request received on /api/v1/train
    2026-08-04 10:15:03 ERROR database - Failed to acquire connection from pool
    Traceback (most recent call last):
      File "src/pipeline/train.py", line 105, in execute_pipeline
        db.connect()
      File "src/engines/duckdb_engine.py", line 22, in connect
        self._conn = duckdb.connect(database=self.database_path)
    duckdb.IOException: Could not set lock on file "logdatabase.db": Resource temporarily unavailable
    """
    
    print("--- Running Diagnostic Agent Test ---")
    analysis = diagnose_log_failure(mock_log)
    print(analysis)
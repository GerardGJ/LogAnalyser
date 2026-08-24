# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A POC multi-agent system (LangChain/LangGraph + DuckDB) that answers natural-language questions about parsed application log files. Only a subset of the intended architecture is implemented — see "Actual vs. documented architecture" below before trusting `README.md`.

## Commands

```bash
uv sync                    # install/sync dependencies
uv run pytest              # run the test suite (pythonpath=".", testpaths="tests" per pyproject.toml)
uv run pytest tests/test_engines/test_duckdbengine.py::test_query_database  # run a single test
uv run python main.py      # run the prototype CLI (currently sends one hard-coded query)
uv run python -m src.utils.log_loader  # sanity-check the log parser against config.settings.LOGS_PATH
```

No lint/format/typecheck tooling is configured in `pyproject.toml`.

Copy `.env.example` to `.env` before running anything that touches an LLM (`OPENAI_API_KEY` is required by `init_chat_model`).

## Actual vs. documented architecture

`README.md` describes the target design (5-agent LangGraph pipeline: Security → Router → SQL/Diagnostic → Synthesizer). `TODO.md` is a maintained, accurate audit of what's actually built vs. planned — **read `TODO.md` before README when you need to know current state**, and update it when you close or open gaps.

Currently implemented:
- **SQL agent** (`src/agents/sql_agent.py`) — text-to-SQL over DuckDB via `langchain.agents.create_agent`, with an explicit N-retry wrapper (`query_log_agent_with_retry`) that re-prompts the model with the prior exception on failure.
- **Diagnostic agent** (`src/agents/diagnostic_agent.py`) — root-cause analysis over stack traces/log snippets, with tools for stack-trace extraction and context-window-safe log sampling (`src/tools/diagnostics_tools.py`). Model is config-driven (`get_agent_model("diagnostic_agent")`, same pattern as the SQL agent), and `diagnose_log_failure()` scrubs PII on both the incoming log payload and the outgoing analysis.
- **Router agent** (`src/agents/router_agent.py`) — `route_query(question) -> Literal["sql", "diagnostic", "unsupported"]`. Deliberately not an LLM agent: deterministic word-boundary keyword regexes, per the POC decision to defer an LLM router. Not yet called from anywhere (no graph exists yet — see Phase 3 in `TODO.md`).
- **DuckDB engine** (`src/engines/`) and **PII scrubber** (`src/security/pii_scrubber.py`).

Not implemented (exists only as empty file, missing entirely, or stubbed in README): `security_agent.py` (empty), `synthesizer_agent.py`, `src/graph/state.py` / `workflow.py` (LangGraph orchestration is not wired up — agents are called directly), RBAC, Presidio/NER-based PII, non-DuckDB engine adapters.

## Architecture notes that span multiple files

**Engine abstraction stack**: `BaseEngine` (`src/engines/base_engine.py`) → `RelationalEngine` (`src/engines/relational_engine.py`) → `DuckDBEngine` (`src/engines/duckdb_engine.py`). `BaseEngine` uses a `@require_connection` decorator on public template methods (`insert`, `delete_record`, `get_by_id`, ...) that dispatch to `_insert`/`_delete_record`/etc. hooks abstract subclasses must implement; it also provides `__enter__`/`__exit__` so engines are used as context managers (`with engine: ...`). When adding a new engine, implement the `_*` hooks, not the public methods.

**PII scrubbing runs inside the engine, not just at the agent boundary**: `DuckDBEngine._execute_query` calls `scrub_dataframe()` on every query result before returning it (`src/engines/duckdb_engine.py:49`), and `query_log_agent_with_retry` also calls `scrub_text()` on the user's prompt before it reaches the agent (`src/agents/sql_agent.py:66`). `diagnose_log_failure` follows the same input/output pattern, scrubbing both the incoming log payload and the agent's final analysis (`src/agents/diagnostic_agent.py`). Any new query/agent path should preserve both scrub points rather than relying on one.

**Log schema is the parsed-file schema**: `LogEntry` (`src/models/log_schema.py`) and `src/utils/log_loader.py`'s `LOG_PATTERN` use `timestamp, level, app, source_file, line_number, message` — matched against lines like `2026-08-03 16:01:47 [ERROR] sleep_app (main.py:76): <message>`. Multi-line entries (e.g. Python tracebacks) are folded into the previous record's `message` field by the parser, not treated as separate rows. This is the canonical schema across `LogEntry`, `log_loader.py`, engine lookups, and README — an earlier `trace_id`/`service` variant was fully retired (see `TODO.md` 0.3).

**Per-agent model config**: `config/agents.yaml` maps agent name → `{model, temperature}`, read via `src/utils/config_loader.py:get_agent_model(agent_name)`, which calls `langchain.chat_models.init_chat_model`. `database_tools.py`'s `sql_db_query_checker` tool uses the `query_checker` entry to run a second, cheaper model as a SQL linting pass before execution — a distinct model from the agent that generated the query.

**DuckDB tools always open a fresh `with engine:` block per call** (`src/tools/database_tools.py`) rather than sharing a long-lived connection — connect/disconnect happens per tool invocation.

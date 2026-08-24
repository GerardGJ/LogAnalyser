# Production Log Analyzer - Implementation TODO

This document tracks the current implementation state against the project objective in `README.md`: a secure, multi-agent conversational system for querying and diagnosing production logs through an engine-agnostic query layer.

Last audit: 2026-08-23

---

## Current State Snapshot

| Area | Status | Notes |
| :--- | :--- | :--- |
| Project scaffold | Complete | Core folders exist: `src/`, `config/`, `data/`, `tests/`. |
| Dependency management | Complete | Project uses `pyproject.toml`/`uv.lock`; README install/test commands now document the `uv` workflow and pytest import paths are configured in `pyproject.toml`. |
| Log schema | Complete | `LogEntry`, `log_loader.py`, engine tests, and README all use the canonical parsed-file schema (`timestamp`, `level`, `app`, `source_file`, `line_number`, `message`); no `trace_id`/`service` fields remain. |
| DuckDB engine | Partial | `BaseEngine`, `RelationalEngine`, and `DuckDBEngine` exist, but file ingestion is CSV-only, raw SQL string interpolation remains in places, and tests are not currently runnable. |
| PII scrubbing | Partial | Regex scrubber exists for emails, IPv4, API keys, and JWTs; no Presidio/NER integration, RBAC, or full unit coverage yet. |
| SQL agent | Partial | LangChain agent factory exists, but it depends on live model initialization, uses hard-coded model names, and has a broken `__main__` call. |
| Diagnostic agent | Partial | Agent factory and stack trace tools exist, but no deterministic tests or graph integration exist. |
| Security agent | Not started | `src/agents/security_agent.py` exists but is empty. |
| Router/planner agent | Not started | `src/agents/router_agent.py` is missing. |
| Synthesizer agent | Not started | `src/agents/synthesizer_agent.py` is missing. |
| LangGraph workflow | Not started | `src/graph/` only contains `__init__.py`; no state or workflow definitions. |
| CLI | Prototype only | `main.py` sends one hard-coded Spanish query to the SQL retry function; no interactive loop or data/bootstrap flow. |
| Tests | Partial | `uv run pytest` passes for the current single engine test; `tests/test_pii.py` and `tests/test_graph.py` are still empty. |

---

## Phase 0: Baseline Alignment & Testability (Immediate)
*Objective: make the current codebase runnable, testable, and aligned with the README before adding more agent behavior.*

- [x] **0.1 Fix package/test import configuration**
  - [x] Update packaging or pytest configuration so `uv run pytest` can import `src` from the repository root.
  - [x] Confirm the suite collects without import errors.
  - [x] Add a short developer command section to the README once the canonical test command is stable.

- [x] **0.2 Align dependency documentation**
  - [x] Decide whether `uv`/`pyproject.toml` is the canonical dependency flow.
  - [x] Update README instructions that currently reference `requirements.txt` and `.env.example`, because those files are absent.
  - [x] Add or regenerate `.env.example` if environment-based setup is expected.

- [x] **0.3 Align the canonical log schema**
  - [x] Decide whether the POC schema is the README schema (`timestamp`, `level`, `trace_id`, `service`, `message`) or the parsed file schema (`timestamp`, `level`, `app`, `source_file`, `line_number`, `message`). Decision: canonical schema is the parsed file schema.
  - [x] Update `src/utils/log_loader.py`, `src/models/log_schema.py`, engine tests, and README/TODO references to use one canonical contract. `LogEntry` now defines `app`/`source_file`/`line_number` (no `trace_id`/`service`), `DuckDBEngine._get_by_id`/`_delete_record` query by rowid instead of the now-nonexistent `trace_id` column, README's "Standard Log Schema" table matches, and `tests/test_log_schema.py` asserts the canonical field set.
  - [x] Add migration/normalization logic if raw source logs must preserve `source_file` and `line_number` while exposing `service`/`trace_id` to agents. Not applicable — the decision above keeps `source_file`/`line_number` as the canonical fields exposed to agents, so no `service`/`trace_id` normalization layer is needed.

- [x] **0.4 Remove prototype breakages**
  - [x] Fix `src/agents/sql_agent.py` `__main__` block, which calls undefined `run_sql_agent`.
  - [x] Move hard-coded model names (`gpt-5.5`, `openai:gpt-5.5`) into configuration.
  - [x] Avoid initializing LLM clients at import time in modules used by tools/tests.

---

## Phase 1: Data Engine & Ingestion Foundation (High Priority)
*Objective: provide a reliable, engine-agnostic local database layer for log data before full multi-agent orchestration.*

- [x] **1.1 Create project directory and source layout**
  - [x] Initialize repository structure (`src/`, `config/`, `data/`, `tests/`).
  - [x] Add `pyproject.toml` and `uv.lock` for dependency management.
  - [x] Add initial `config/settings.py`.

- [x] **1.2 Standardize schema and raw log ingestion**
  - [x] Define a Pydantic `LogEntry` model.
  - [x] Implement text log parsing in `src/utils/log_loader.py`.
  - [x] Resolve schema mismatch between `LogEntry`, README, tests, and parsed `pipeline.log` fields. `pipeline.log` emits `WARNING` (not `WARN`), which `LogLevel` rejected — `LogLevel.WARN` renamed to `LogLevel.WARNING` in `src/models/log_schema.py`, and README's schema table updated to match.
  - [x] Support README-promised JSON/CSV/Parquet ingestion, or narrow the documentation to supported formats. Decision: narrowed docs — README now states `log_loader.py` only parses the standard text-log format today, and calls out JSON/CSV/Parquet file ingestion as planned (tracked under 1.3/5.1) rather than implemented; also fixed the "Getting Started" step 5 command, which referenced a nonexistent `--input` flag and sample file.
  - [x] Remove debug output from `load_logs()`. No debug output exists inside `load_logs()`/`parse_log_text()` themselves; the only `print()` calls live under `if __name__ == "__main__":`, which `CLAUDE.md` documents as the intentional `uv run python -m src.utils.log_loader` sanity-check command — left as-is.

- [x] **1.3 Build database abstraction layer**
  - [x] Create `BaseEngine` with connection lifecycle enforcement.
  - [x] Create `RelationalEngine` with `execute_query()` and `get_schema()`.
  - [x] Implement `DuckDBEngine` for in-memory/on-disk DuckDB.
  - [x] Rename or document engine module names consistently (`base_engine.py` vs README's `base.py`). Decision: kept the file name `base_engine.py` and fixed README's Project Structure section to match (it also previously omitted `relational_engine.py`, now listed).
  - [x] Add safe file ingestion support for CSV, JSON, and Parquet. `DuckDBEngine._insert_file` now dispatches on an extension allowlist (`.csv`→`read_csv_auto`, `.json`/`.jsonl`→`read_json_auto`, `.parquet`→`read_parquet`) instead of always assuming CSV, raises `FileNotFoundError`/`ValueError` for missing files or unrecognized extensions, and quote-escapes the resolved path before interpolation.
  - [x] Validate or restrict raw SQL filters in `delete_filter()`. Added a denylist (`_UNSAFE_FILTER_PATTERN` in `src/engines/duckdb_engine.py`) rejecting statement-chaining (`;`), comments (`--`, `/*`), and DDL/DML/PRAGMA/ATTACH keywords before the filter is interpolated into the `DELETE ... WHERE` clause; empty/whitespace-only filters are also rejected.
  - [x] Add tests for connection lifecycle, schema inspection, parameterized queries, inserts, and PII-scrubbed query results. `tests/test_engines/test_duckdbengine.py` expanded from 1 to 46 tests across these areas plus edge cases: idempotent connect/disconnect, context-manager cleanup on exception, every template method rejecting disconnected use, unknown-table schema lookups, missing/non-numeric ids, no-op deletes, empty-DataFrame and repeated inserts, CSV/JSON/Parquet file ingestion (including a quote-containing path) and unsupported/missing files, PII scrubbing of query results, and the `delete_filter()` denylist across empty and SQL-injection-shaped inputs.

---

## Phase 2: Core Agent Logic & Tooling (Medium-High Priority)
*Objective: implement and unit-test individual tools and agents before wiring them into LangGraph.*

- [~] **2.1 Security and PII redaction pipeline**
  - [x] Implement regex-based `scrub_text()` and `scrub_dataframe()`.
  - [ ] Add unit tests for email, IPv4, JWT, bearer token, API key, and DataFrame redaction cases.
  - [ ] Decide whether Presidio/NER is in scope for the POC; if yes, add dependency/configuration and tests.
  - [ ] Implement `SecurityAgent` in `src/agents/security_agent.py`.
  - [ ] Add RBAC/scope model and deny/allow behavior for restricted log fields or services.
  - [ ] Ensure outgoing synthesized responses are scrubbed before display.

- [~] **2.2 Text-to-SQL generation and self-correction agent**
  - [x] Build SQL agent factory with schema inspection, query checking, execution tools, and retry wrapper.
  - [x] Implement database tools for listing tables, fetching schema, running queries, and checking SQL.
  - [ ] Defer model creation until runtime so imports/tests do not require API credentials.
  - [ ] Use configured model/provider values from settings or environment.
  - [ ] Add guardrails that reject DDL/DML before query execution, not only through prompt instructions.
  - [ ] Add deterministic tests using fake/mocked LLM responses.
  - [ ] Add integration test against a populated DuckDB fixture once pytest collection is fixed.

- [~] **2.3 Log diagnostic and stack-trace sampling agent**
  - [x] Implement `parse_stack_trace` tool.
  - [x] Implement `sample_and_truncate_logs` tool.
  - [x] Build `DiagnosticAgent` factory and public `diagnose_log_failure()` entry point.
  - [ ] Add deterministic unit tests for Python traceback extraction, failure-line fallback, truncation behavior, and no-error logs.
  - [ ] Scrub diagnostic input/output for PII.
  - [ ] Make model/provider configurable and lazy-loaded.

- [ ] **2.4 Router / planner agent**
  - [ ] Create `src/agents/router_agent.py`.
  - [ ] Classify queries into at least `sql`, `diagnostic`, and `unsupported/clarify` routes.
  - [ ] Prefer deterministic keyword/structured rules for the POC, with optional LLM fallback later.
  - [ ] Add tests for metrics queries, root-cause queries, trace lookups, and ambiguous inputs.

- [ ] **2.5 Synthesizer agent**
  - [ ] Create `src/agents/synthesizer_agent.py`.
  - [ ] Merge SQL results, diagnostic summaries, execution metadata, and warnings into concise Markdown.
  - [ ] Add final PII scrub pass.
  - [ ] Add tests for empty results, tabular results, diagnostic-only results, mixed results, and errors.

---

## Phase 3: LangGraph Workflow & Orchestration (Medium Priority)
*Objective: connect isolated agents into a deterministic state graph matching the README architecture.*

- [ ] **3.1 Shared state definition**
  - [ ] Create `src/graph/state.py`.
  - [ ] Define `AgentState` fields for raw query, sanitized query, user role/scope, route, SQL query, SQL results, diagnostic input, diagnostic output, errors, metadata, and final response.
  - [ ] Include a consistent error shape for failed security, routing, SQL, and diagnostic steps.

- [ ] **3.2 Graph node wrappers**
  - [ ] Implement security node.
  - [ ] Implement router node.
  - [ ] Implement SQL node.
  - [ ] Implement diagnostic node.
  - [ ] Implement synthesizer node.

- [ ] **3.3 Graph assembly and conditional edges**
  - [ ] Create `src/graph/workflow.py`.
  - [ ] Wire `SecurityNode -> RouterNode -> (SQLNode | DiagnosticNode) -> SynthesizerNode`.
  - [ ] Add fallback paths for rejected permissions, unsupported intent, query execution errors, and empty results.
  - [ ] Add graph-level tests using mocked agents and a sample DuckDB fixture.

---

## Phase 4: User Entry Point & Integration (Medium Priority)
*Objective: expose the graph through a usable CLI/API and validate end-to-end behavior.*

- [~] **4.1 Interactive CLI**
  - [x] Add a prototype `main.py`.
  - [ ] Replace the hard-coded query with an interactive prompt loop.
  - [ ] Add command-line options for database path, log file path, user role, and route/debug output.
  - [ ] Load or verify sample logs before accepting questions.
  - [ ] Handle graceful exit, keyboard interrupt, and empty input.

- [ ] **4.2 Data bootstrap command**
  - [ ] Add a CLI/module command to parse `data/raw_logs/pipeline.log` and load it into DuckDB.
  - [ ] Make table name configurable while defaulting to `logs`.
  - [ ] Add idempotent reload behavior for local development.

- [ ] **4.3 End-to-end scenarios**
  - [ ] Metrics scenario: "count errors by app".
  - [ ] Trace scenario: "show events from source_file X" or equivalent canonical identifier.
  - [ ] Diagnostic scenario: "why did the pipeline fail?"
  - [ ] Security scenario: prompt/logs containing secrets are scrubbed before model context and final output.
  - [ ] Permission scenario: restricted query is denied or narrowed by `SecurityAgent`.

---

## Phase 5: Production Hardening & Extensions (Lower Priority)
*Objective: prepare the project for larger log volumes, additional engines, and operational use.*

- [ ] **5.1 Engine adapters**
  - [ ] Define adapter contract for production engines beyond DuckDB.
  - [ ] Add ClickHouse adapter or keep it documented as future work.
  - [ ] Add OpenSearch/Elasticsearch adapter or keep it documented as future work.
  - [ ] Add dialect-specific SQL/query generation tests.

- [ ] **5.2 Observability and auditability**
  - [ ] Add structured application logging.
  - [ ] Track query text, route, timing, row count, and scrub status in execution metadata.
  - [ ] Avoid logging raw PII or secrets.

- [ ] **5.3 Context management**
  - [ ] Add deterministic top-K sampling by severity, recency, trace/session, and exception signature.
  - [ ] Add token/character budgets for SQL result previews and diagnostic log payloads.
  - [ ] Add tests for large logs and multi-line stack traces.

- [ ] **5.4 Streaming and alert workflows**
  - [ ] Add real-time log tailing only after core batch query flow is stable.
  - [ ] Add automated alert root-cause report generation.
  - [ ] Add saved incident report output if needed.

---

## Verification Baseline

- [x] Repository audit performed against README architecture.
- [x] Source files inspected for implemented agents, tools, engines, graph, and tests.
- [x] Current test command attempted: `uv run pytest`.
- [x] Test suite passing for currently implemented tests.

Current pytest result:

```text
collected 3 items
tests/test_engines/test_duckdbengine.py .
tests/test_log_schema.py ..
3 passed
```

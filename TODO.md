# Production Log Analyzer - Implementation TODO

This document tracks the current implementation state against the project objective in `README.md`: a secure, multi-agent conversational system for querying and diagnosing production logs through an engine-agnostic query layer.

**Workflow decision (2026-08-24):** this is a solo, personal-project POC — a full `SecurityAgent`/RBAC node is deferred until the Router → SQL/Diagnostic → Synthesizer pipeline is working end-to-end. Regex PII scrubbing (`scrub_text`/`scrub_dataframe`) already runs at the engine and prompt boundaries and stays in place; what's deferred is the *agent* wrapper and RBAC/permission-scoping, which need a real multi-user/role concept the POC doesn't have yet. Revisit once the graph works and there's an actual driver (multi-user access, real secrets in logs). Until then the graph is `RouterNode -> (SQLNode | DiagnosticNode) -> SynthesizerNode`, with `security_agent.py` left as a stub.

Last audit: 2026-08-24

---

## Current State Snapshot

| Area | Status | Notes |
| :--- | :--- | :--- |
| Project scaffold | Complete | Core folders exist: `src/`, `config/`, `data/`, `tests/`. |
| Dependency management | Complete | Project uses `pyproject.toml`/`uv.lock`; README install/test commands now document the `uv` workflow and pytest import paths are configured in `pyproject.toml`. |
| Log schema | Complete | `LogEntry`, `log_loader.py`, engine tests, and README all use the canonical parsed-file schema (`timestamp`, `level`, `app`, `source_file`, `line_number`, `message`); no `trace_id`/`service` fields remain. |
| DuckDB engine | Partial | `BaseEngine`, `RelationalEngine`, and `DuckDBEngine` exist, but file ingestion is CSV-only, raw SQL string interpolation remains in places, and tests are not currently runnable. |
| PII scrubbing | Partial | Regex scrubber exists for emails, IPv4, API keys, and JWTs, now with unit coverage (`tests/test_pii.py`); no Presidio/NER integration or RBAC yet. |
| SQL agent | Complete | LangChain agent factory, database tools, DDL/DML guardrail, and deterministic tests all in place (`tests/test_sql_agent.py`, `tests/test_database_tools.py`); model config is lazy and `config/agents.yaml`-driven. |
| Diagnostic agent | Partial | Agent factory, stack trace tools, PII scrubbing, config-driven model, and deterministic tests are all in place (`tests/test_diagnostics_tools.py`, `tests/test_diagnostic_agent.py`); no graph integration exists yet (Phase 3). |
| Security agent | Deferred | `src/agents/security_agent.py` intentionally left empty until Router/Synthesizer are working — see workflow decision above. Regex PII scrubbing at the engine/prompt boundary is unaffected and stays active. |
| Router/planner agent | Complete | `src/agents/router_agent.py` deterministically classifies into a `list["sql" \| "diagnostic"]` route set (empty = unsupported) via keyword regexes, so mixed-intent questions can fan out to both agents; not yet wired into a graph (Phase 3). |
| Synthesizer agent | Complete | `src/agents/synthesizer_agent.py` deterministically merges whatever routes ran (SQL results, diagnostic summary, warnings) into Markdown with a final PII scrub pass; not yet wired into a graph (Phase 3). |
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

- [~] **2.1 PII redaction pipeline** *(regex scrubbing only — kept in scope; agent/RBAC below are deferred, see workflow decision)*
  - [x] Implement regex-based `scrub_text()` and `scrub_dataframe()`.
  - [x] Add unit tests for email, IPv4, JWT, bearer token, API key, and DataFrame redaction cases. `tests/test_pii.py` now has 17 tests across `scrub_text`/`scrub_dataframe`, including multi-PII strings, target-column selection, auto-detected string columns, and empty DataFrames. Found and fixed a real bug while writing these: `scrub_dataframe`'s API-key replacement used the Python `re`-style backreference `\1`, but polars' `str.replace_all` runs on the Rust `regex` crate, which needs `$1`/`${1}` — the DataFrame path was emitting literal `\1=[REDACTED_API_KEY]` instead of redacting. Added a separate `REDACTED_KEY_POLARS` pattern for that call site; `scrub_text` (Python `re.sub`) was unaffected and already correct.
  - [ ] Ensure outgoing synthesized responses are scrubbed before display (once 2.5 exists).

- [ ] **2.1a `SecurityAgent` and RBAC (Deferred — build after 2.4/2.5 land)**
  - [ ] Decide whether Presidio/NER is in scope for the POC; if yes, add dependency/configuration and tests.
  - [ ] Implement `SecurityAgent` in `src/agents/security_agent.py`.
  - [ ] Add RBAC/scope model and deny/allow behavior for restricted log fields or services.
  - Reason to defer: no multi-user/role concept exists yet in this solo POC; building RBAC now would be speculative. Revisit once the Router → SQL/Diagnostic → Synthesizer graph works, or when a real driver (multi-user access, real secrets in logs) appears.

- [x] **2.2 Text-to-SQL generation and self-correction agent**
  - [x] Build SQL agent factory with schema inspection, query checking, execution tools, and retry wrapper.
  - [x] Implement database tools for listing tables, fetching schema, running queries, and checking SQL.
  - [x] Defer model creation until runtime so imports/tests do not require API credentials. `get_agent_model()` is only invoked inside `get_sql_agent()`/`sql_db_query_checker()`, never at module import time.
  - [x] Use configured model/provider values from settings or environment. Both the SQL agent and the query checker read model/provider/temperature from `config/agents.yaml` via `get_agent_model`; no hard-coded model names remain in `sql_agent.py`/`database_tools.py`.
  - [x] Add guardrails that reject DDL/DML before query execution, not only through prompt instructions. `src/tools/database_tools.py` now has `_reject_unsafe_query()`, called from `sql_db_query` before anything reaches `DuckDBEngine`: rejects any query whose leading keyword isn't `SELECT`/`WITH`/`SHOW`/`DESCRIBE`/`EXPLAIN`, and separately rejects statement-chaining (`;`), comments, and DDL/DML/admin keywords (`INSERT`, `UPDATE`, `DELETE`, `DROP`, `CREATE`, `ALTER`, `ATTACH`, `PRAGMA`, etc.) anywhere in the string, including inside a CTE. The guardrail is intentionally scoped to this tool rather than `DuckDBEngine._execute_query` generally, since that method is also used internally for legitimate `DELETE`s (`_delete_record`).
  - [x] Add deterministic tests using fake/mocked LLM responses. `tests/test_sql_agent.py` exercises `query_log_agent_with_retry()` against a scripted fake agent (first-try success, prompt scrubbing, retry-then-succeed, retries-exhausted, agent built once and reused); `tests/test_database_tools.py` covers `_reject_unsafe_query()` and mocks `get_agent_model` for `sql_db_query_checker`.
  - [x] Add integration test against a populated DuckDB fixture once pytest collection is fixed. `tests/test_database_tools.py`'s `populated_tools_engine` fixture points the tools' module-level `engine` at a temp-file-backed DuckDB (not `:memory:`, since the tools reconnect per call — see `CLAUDE.md`) and verifies `sql_db_query`/`sql_db_list_tables`/`sql_db_schema` end-to-end, including that a blocked `DROP TABLE`/stacked statement leaves the table intact and that query results are PII-scrubbed.

- [x] **2.3 Log diagnostic and stack-trace sampling agent**
  - [x] Implement `parse_stack_trace` tool.
  - [x] Implement `sample_and_truncate_logs` tool.
  - [x] Build `DiagnosticAgent` factory and public `diagnose_log_failure()` entry point.
  - [x] Add deterministic unit tests for Python traceback extraction, failure-line fallback, truncation behavior, and no-error logs. `tests/test_diagnostics_tools.py` (19 tests) and `tests/test_diagnostic_agent.py` (5 tests, mocked agent). Writing the edge cases surfaced two real bugs, both fixed in `src/tools/diagnostics_tools.py`: (1) `sample_and_truncate_logs`'s head(15)/tail(20) slices overlapped and duplicated lines, and drove the "TRUNCATED N LINES" count negative, whenever the input had fewer than 35 lines but more than `max_lines` — sizes are now clamped to the available line count. (2) `parse_stack_trace`'s fallback keyword filter only matched mixed-case substrings (`"Error"`, `"Exception"`), which never matched the project's canonical `LogLevel` values (`ERROR`, `FATAL`, upper-case) — matching is now case-insensitive and includes `fatal`.
  - [x] Scrub diagnostic input/output for PII. `diagnose_log_failure()` now runs `scrub_text()` on the incoming `log_payload` before it's put in the prompt, and again on the agent's final response before returning it — mirroring the two-scrub-point pattern already used by the SQL agent (see `CLAUDE.md`).
  - [x] Make model/provider configurable and lazy-loaded. `get_diagnostic_agent()` now calls `get_agent_model("diagnostic_agent")` (reads `config/agents.yaml`) instead of the hard-coded `init_chat_model("openai:gpt-5.5")`; model creation was already lazy (only inside the factory function, never at import time) and remains so.

- [x] **2.4 Router / planner agent**
  - [x] Create `src/agents/router_agent.py`.
  - [x] Classify queries into at least `sql`, `diagnostic`, and `unsupported/clarify` routes. `route_query()` returns `list[Literal["sql", "diagnostic"]]`, with an empty list meaning unsupported — this was widened from a single route to a route *set* so a mixed-intent question can fan out to both agents (see design discussion below and 2.5's Synthesizer, which merges whatever routes actually ran).
  - [x] Prefer deterministic keyword/structured rules for the POC, with optional LLM fallback later. Implemented as two word-boundary regexes (no model, no `config/agents.yaml` entry needed) — diagnostic phrases (`why`, `root cause`, `crash`, `fail(ed|ure)`, `broke(n)`, `exception`, `traceback`, `diagnose`, `debug`) and SQL phrases (`how many`, `count`, `top N`, `group by`, `source_file`, etc.) are checked independently and returned diagnostic-before-sql for a stable order. LLM fallback is intentionally left for later.
  - [x] Add tests for metrics queries, root-cause queries, trace lookups, and ambiguous inputs. `tests/test_router_agent.py` (26 tests) also covers case-insensitivity, word-boundary false positives (`"failover"` must not match `"fail"`), and mixed-intent questions returning both routes.

- [x] **2.5 Synthesizer agent**
  - [x] Create `src/agents/synthesizer_agent.py`.
  - [x] Merge SQL results, diagnostic summaries, execution metadata, and warnings into concise Markdown. `synthesize_response(question, sql_result=None, diagnostic_result=None, errors=None)` is deterministic template assembly (not an LLM call, matching the router's design), rendering `## Root Cause Analysis` and `## Query Results` sections only for routes that actually produced a result (diagnostic-before-sql order, matching `route_query()`), a `## Warnings` section when `errors` is non-empty, and a "No results available" fallback when neither result was provided (the unsupported-route case).
  - [x] Add final PII scrub pass. `scrub_text()` runs over the fully assembled Markdown (heading, results, warnings) before it's returned — the last of the scrub points documented in `CLAUDE.md`.
  - [x] Add tests for empty results, tabular results, diagnostic-only results, mixed results, and errors. `tests/test_synthesizer_agent.py` (14 tests) covers all of these plus PII scrubbing across the question/sql/diagnostic inputs and the empty/whitespace-only question fallback heading.
  - Note: this stays standalone until Phase 3 wires it into the graph as the join point for the router's fan-out (see 3.2/3.3 below).

---

## Phase 3: LangGraph Workflow & Orchestration (Medium Priority)
*Objective: connect isolated agents into a deterministic state graph matching the README architecture.*

- [ ] **3.1 Shared state definition**
  - [ ] Create `src/graph/state.py`.
  - [ ] Define `AgentState` fields for raw query, **`routes: list[str]`** (plural — `route_query()` now returns a route set, not a single route, so both SQL and diagnostic branches can run for a mixed-intent question), SQL query, SQL results, diagnostic input, diagnostic output, errors, metadata, and final response. (Omit user role/scope fields until 2.1a lands.)
  - [ ] Include a consistent error shape for failed routing, SQL, and diagnostic steps.

- [ ] **3.2 Graph node wrappers**
  - [ ] Implement router node.
  - [ ] Implement SQL node.
  - [ ] Implement diagnostic node.
  - [ ] Implement synthesizer node — this is the fan-in/join point: it must wait for whichever of SQL/diagnostic actually ran (per `routes`) before calling `synthesize_response()`, not assume exactly one ran.
  - [ ] (Deferred) Implement security node once `SecurityAgent` (2.1a) exists.

- [ ] **3.3 Graph assembly and conditional edges**
  - [ ] Create `src/graph/workflow.py`.
  - [ ] Wire `RouterNode -> (SQLNode and/or DiagnosticNode, fanned out per `routes`) -> SynthesizerNode`. This needs LangGraph's conditional-edge-returns-a-list support (fan-out) plus a join before the synthesizer, not a simple either/or branch.
  - [ ] Add fallback paths for unsupported intent (empty `routes`), query execution errors, and empty results.
  - [ ] Add graph-level tests using mocked agents and a sample DuckDB fixture, including a mixed-intent case that exercises both branches feeding one synthesizer call.
  - [ ] (Deferred) Prepend `SecurityNode` once 2.1a lands; add rejected-permission fallback path then.

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
  - [ ] Scrubbing scenario: prompt/logs containing secrets are scrubbed before model context and final output (regex scrubber only — already active, not gated on 2.1a).
  - [ ] (Deferred) Permission scenario: restricted query is denied or narrowed by `SecurityAgent`, once 2.1a lands.

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
158 passed
```

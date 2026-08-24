# Production Log Analyzer — Multi-Agent System

An intelligent, multi-agent conversational AI system designed to query, diagnose, and analyze production execution logs using natural language. Built with a modular, engine-agnostic architecture, the system enables operations and engineering teams to extract real-time operational metrics, investigate root-cause failures, and query structured and unstructured log telemetry securely.

---

## Table of Contents
1. [Objective](#objective)
2. [Key Features](#key-features)
3. [System Architecture & Workflow](#system-architecture--workflow)
4. [Multi-Agent Design & Responsibilities](#multi-agent-design--responsibilities)
5. [Database Engine & Abstraction Layer](#database-engine--abstraction-layer)
6. [PII Masking & Security Framework](#pii-masking--security-framework)
7. [Project Structure](#project-structure)
8. [Getting Started](#getting-started)
9. [Developer Commands](#developer-commands)
10. [Configuration & Environment Variables](#configuration--environment-variables)
11. [Roadmap](#roadmap)

---

## Objective

Modern microservice architectures generate massive volumes of log data across disparate storage systems. Investigating incidents, computing error metrics, and tracing failures across distributed systems often requires specialized query knowledge (e.g., SQL, KQL, Elasticsearch DSL) and manual log parsing.

The **Production Log Analyzer** solves this challenge by providing:
* **Natural Language Telemetry Interface:** Converts plain English user queries into optimized, execution-engine queries (e.g., Text-to-SQL).
* **Multi-Agent Collaborative Intelligence:** Decouples complex analytical workflows—such as SQL query generation, error stack-trace diagnosis, and response synthesis—into specialized, deterministic AI agents.
* **Engine-Agnostic Query Layer:** Currently parses the standard application text-log format (see [Standard Log Schema](#standard-log-schema)) for Proof-of-Concept (POC) environments; JSON/CSV/Parquet ingestion and pluggable support for enterprise log databases (ClickHouse, PostgreSQL, Databricks, Snowflake, OpenSearch) are planned but not yet implemented (see `TODO.md`).
* **PII Masking:** Automated regex-based PII scrubbing at both ingestion and query execution, ensuring sensitive payload data never leaves the security perimeter before reaching the LLM.

> **Note on scope:** this is a solo, personal-project POC. A dedicated `SecurityAgent`/RBAC node is intentionally deferred until the Router → SQL/Diagnostic → Synthesizer pipeline works end-to-end — see [Roadmap](#roadmap) and `TODO.md` for the reasoning. Regex PII scrubbing is already implemented and active; RBAC/permission-scoping is not.

---

## Key Features

* **Multi-Agent Orchestration:** Powered by graph-based workflows (`LangGraph`), ensuring predictable state transitions and deterministic query handling.
* **Context-Aware Log Sampling:** Avoids context window limits by leveraging SQL for aggregations and using deterministic top-K sampling for stack-trace diagnosis.
* **Automated SQL Self-Correction:** The Text-to-SQL agent automatically inspects schema definitions and self-corrects syntax errors if database execution fails.
* **PII Masking:** Regex-based scrubbing removes API keys, JWTs, emails, and IP addresses before LLM invocation. A Named Entity Recognition (NER) pipeline (via Microsoft Presidio) and a dedicated `SecurityAgent`/RBAC layer are planned but deferred — see [Roadmap](#roadmap).

---

## System Architecture & Workflow

The architecture follows a graph-based multi-agent orchestration design pattern. User prompts pass through a multi-stage execution pipeline where agents interact with database abstractions, PII scrubbers, and context management modules.

**Current target for this POC** (a `SecurityAgent`/RBAC node is deferred — see the note below the diagram):

```
                                  ┌───────────────────────────┐
                                  │   User Interface / API    │
                                  └─────────────┬─────────────┘
                                                │
                                                ▼
                                  ┌───────────────────────────┐
                                  │  1. Router / Planner      │
                                  └─────────────┬─────────────┘
                                                │
                        ┌───────────────────────┴───────────────────────┐
                        │                                               │
                        ▼                                               ▼
          ┌───────────────────────────┐                   ┌───────────────────────────┐
          │  2. Text-to-SQL Agent     │                   │  3. Log Diagnostic Agent  │
          │  (Metrics & Aggregations) │                   │  (Unstructured Traces)    │
          └─────────────┬─────────────┘                   └─────────────┬─────────────┘
                        │                                               │
                        └───────────────────────┬───────────────────────┘
                                                │
                                                ▼
                                  ┌───────────────────────────┐
                                  │ 4. Synthesizer Agent      │
                                  └─────────────┬─────────────┘
                                                │
                                                ▼
                                  ┌───────────────────────────┐
                                  │  Final Formatted Output   │
                                  └───────────────────────────┘
```

> A `Security & RBAC Agent` may be prepended to this graph later (see [Roadmap](#roadmap)). Until then, PII scrubbing runs inline at the engine and prompt boundaries (see [PII Masking & Security Framework](#pii-masking--security-framework)) rather than as its own graph node.

### Execution Flow Sequence

1. **Intent Planning & Routing (Agent 1):** The Router analyzes the query intent. It routes analytical/metric queries (e.g., *"What is the error rate by app today?"*) to the Text-to-SQL Agent, and deep diagnostic questions (e.g., *"Why is authentication failing?"*) to the Log Diagnostic Agent. The user's prompt is scrubbed for PII before it reaches any model, regardless of route.
2. **Execution & Telemetry Fetching (Agents 2 & 3):**
   * **Text-to-SQL Agent** inspects the target database schema, drafts a SQL query, executes it against the database abstraction layer, and validates the output tabular dataset. Query results are scrubbed for PII before being returned.
   * **Log Diagnostic Agent** queries representative sample logs (e.g., top 15-20 failed trace stack traces) to analyze underlying error patterns without exceeding context window constraints.
3. **Response Synthesis & Formatting (Agent 4):** The Synthesizer compiles query results, execution metadata, and root-cause summaries into a clean, markdown-formatted response while enforcing outgoing PII compliance.

---

## Multi-Agent Design & Responsibilities

The system divides operational responsibilities across four dedicated agents, with a fifth (`SecurityAgent`) planned but deferred:

| Agent | Core Responsibility | Input | Output | Primary Tools / Technologies |
| :--- | :--- | :--- | :--- | :--- |
| **1. Router / Planner Agent** | Classifies incoming intent and chooses the optimal execution strategy (SQL Aggregation vs. Stack Trace Diagnosis). | Scrubbed Prompt | Routing Target (`sql` \| `diagnostic`) | LangGraph Conditional Routing, Intent Classifier |
| **2. Text-to-SQL Agent** | Generates dialect-appropriate SQL queries, executes them against the database abstraction layer, and self-corrects syntax errors. | Natural Language Question + Schema | Structured Tabular Data / Aggregations | Database Dialect Engine, Schema Inspector, Query Validator |
| **3. Log Diagnostic Agent** | Performs semantic inspection and root-cause identification on unstructured log messages, stack traces, and exception frames. | Sampled Log Traces (JSON/Text) | Analytical Root-Cause Summary | Stack Trace Parser, Context Truncator, Exception Profiler |
| **4. Synthesizer Agent** | Merges structured tables, diagnostic summaries, and execution stats into a coherent, markdown-formatted response. | SQL Outputs + Diagnostic Summaries | Final Natural Language Answer | Markdown Formatter, Response Auditor |
| *(Deferred)* **Security & RBAC Agent** | Would validate user role permissions and sanitize incoming natural language prompts to scrub sensitive credentials or PII as its own graph node. | Raw User Prompt + User Token | Scrubbed Prompt + Access Scope | Microsoft Presidio, Custom Regex, Auth Scopes |

PII scrubbing itself is not deferred — `scrub_text()`/`scrub_dataframe()` already run inline at the prompt and query-result boundaries (see below); what's deferred is wrapping that logic in its own agent node plus RBAC/permission-scoping, since this solo POC has no multi-user/role model yet to scope against.

---

## Standard Log Schema

The POC standardizes parsed text log ingestion around the schema emitted by `src/utils/log_loader.py`:

| Column Name | Data Type | Description |
| :--- | :--- | :--- |
| `timestamp` | `TIMESTAMP` | ISO-8601 UTC timestamp of log event generation. |
| `level` | `VARCHAR` | Log severity classification (`INFO`, `WARNING`, `ERROR`, `FATAL`, `DEBUG`). |
| `app` | `VARCHAR` | Application or component name parsed from the log header. |
| `source_file` | `VARCHAR` | Source file parsed from the log header. |
| `line_number` | `INTEGER` | Source line number parsed from the log header. |
| `message` | `TEXT` | Log event payload, containing text descriptions, error messages, or stack traces. |

---

## Database Engine & Abstraction Layer

To maintain engine independence, the system utilizes an abstract database interface (`BaseEngine`). Local development and POC environments default to **DuckDB** operating over log data parsed from the standard text-log format described above. File-based ingestion of raw JSON/CSV/Parquet sources is planned but not yet implemented (see `TODO.md` 1.3/5.1).

```
                      ┌───────────────────────────────┐
                      │    BaseEngine (Abstract)      │
                      └───────────────┬───────────────┘
                                      │
         ┌────────────────────────────┼────────────────────────────┐
         │                            │                            │
         ▼                            ▼                            ▼
┌─────────────────┐          ┌─────────────────┐          ┌─────────────────┐
│ DuckDBEngine    │          │ PostgresEngine  │          │ ClickHouseEngine│
│ (Local POC)     │          │ (Relational)    │          │ (Production)    │
└─────────────────┘          └─────────────────┘          └─────────────────┘
```

* **POC Environment:** `DuckDBEngine` executes high-performance SQL queries over in-memory or on-disk raw log files without requiring separate database server deployment.
* **Production Environment:** Implementations can swap the engine driver to `ClickHouseEngine`, `PostgresEngine`, or `SnowflakeEngine` via configuration without altering agent logic.

---

## PII Masking & Security Framework

To prevent sensitive operational data from leaking to external LLM providers, the system implements regex-based scrubbing (`src/security/pii_scrubber.py`) at two points, independent of any agent orchestration:

1. **Prompt Scrubbing:** `scrub_text()` sanitizes the user's natural-language prompt before it reaches the SQL agent.
2. **Query Result Scrubbing:** `scrub_dataframe()` runs inside `DuckDBEngine._execute_query`, scrubbing every query result before it's returned — API keys, JWTs, emails, and IPv4 addresses are redacted.

RBAC, a dedicated `SecurityAgent` node, and Presidio/NER-based detection are **planned but deferred** (see [Roadmap](#roadmap)) — this is a solo POC with no multi-user/role model to scope permissions against yet.

---

## Project Structure

```
production-log-analyzer/
│
├── README.md                     # Project documentation & setup instructions
├── .env.example                  # Environment variable configuration template
├── pyproject.toml                # Project metadata, dependencies, and tool config
├── uv.lock                       # Locked dependency versions for reproducible installs
│
├── config/                       # Application configurations
│   ├── settings.py               # Dynamic settings & environment loader
│   ├── logging_config.py         # System logging configuration
│   └── pii_rules.json            # PII masking pattern definitions
│
├── data/                         # Local storage for POC log files & databases
│   ├── raw_logs/                 # Raw input log files (JSON, CSV, Log)
│   └── duckdb/                   # Local DuckDB database instances
│
├── src/                          # Application source code
│   ├── __init__.py
│   │
│   ├── agents/                   # Multi-agent implementations
│   │   ├── __init__.py
│   │   ├── security_agent.py     # RBAC & prompt sanitization logic
│   │   ├── router_agent.py       # Intent classification & workflow router
│   │   ├── sql_agent.py          # Text-to-SQL generation & self-correction
│   │   ├── diagnostic_agent.py   # Unstructured log & stack trace analyzer
│   │   └── synthesizer_agent.py  # Response compilation & formatting
│   │
│   ├── models/                  # Pydantic data models & data structures
│   │   ├──__init__.py
│   │   └── log_schema.py        # LogEntry Pydantic model
│   │
│   ├── graph/                    # LangGraph orchestration state machine
│   │   ├── __init__.py
│   │   ├── state.py              # Shared AgentState dictionary definitions
│   │   └── workflow.py           # Graph edge/node definitions & execution graph
│   │
│   ├── engines/                  # Database abstraction layer
│   │   ├── __init__.py
│   │   ├── base_engine.py        # Abstract BaseEngine interface class
│   │   ├── relational_engine.py  # Abstract RelationalEngine (SQL-oriented) interface class
│   │   ├── duckdb_engine.py      # DuckDB implementation for local files
│   │   └── postgres_engine.py    # PostgreSQL/TimescaleDB engine implementation
│   │
│   ├── security/                 # Security, RBAC & PII processing modules
│   │   ├── __init__.py
│   │   ├── pii_scrubber.py       # Presidio & regex scrubbing engines
│   │   └── rbac.py               # Role & scope validation rules
│   │
│   └── utils/                    # Common helper functions
│       ├── __init__.py
│       ├── log_loader.py         # Raw log loader & parser for DuckDB
│       └── context_manager.py    # Text truncation & sampling tools
│
├── tests/                        # Test suite
│   ├── test_agents/              # Unit tests for individual agents
│   ├── test_engines/             # Database execution tests
│   ├── test_graph.py             # End-to-end orchestration tests
│   └── test_pii.py               # PII masking verification tests
│
└── main.py                       # CLI / Entry point application launch script
```

---

## Getting Started

### Prerequisites

* **Python:** `>= 3.13`
* **Package Manager:** `uv`

### Installation

1. **Clone the Repository:**
   ```bash
   git clone https://github.com/your-org/production-log-analyzer.git
   cd production-log-analyzer
   ```

2. **Install Dependencies:**
   ```bash
   uv sync
   ```

3. **Environment Setup:**
   Copy the example configuration file and set your local API credentials:
   ```bash
   cp .env.example .env
   ```

4. **Run Tests:**
   ```bash
   uv run pytest
   ```

5. **Sanity-check the Log Parser (POC):**
   ```bash
   uv run python -m src.utils.log_loader
   ```
   Parses the file at `config.settings.LOGS_PATH` (defaults to `data/raw_logs/pipeline.log`) and prints the resulting schema.

6. **Run the Interactive CLI Chatbot:**
   ```bash
   uv run python main.py
   ```

---

## Developer Commands

The project currently uses `uv` with `pyproject.toml` and `uv.lock` as the canonical local development workflow.

```bash
# Install or sync dependencies
uv sync

# Run the test suite
uv run pytest

# Equivalent pytest invocation
uv run python -m pytest

# Run the current CLI prototype
uv run python main.py
```

---

## Configuration & Environment Variables

Configure key application settings inside the `.env` file:

```env
# LLM Provider Configuration
OPENAI_API_KEY=your_openai_api_key_here
LLM_MODEL=gpt-4o

# Database Execution Settings
DB_ENGINE=duckdb
DUCKDB_PATH=data/duckdb/logdatabase.db
LOGS_PATH=data/raw_logs/pipeline.log

# Security & PII Settings
ENABLE_PII_SCRUBBING=true
LOG_LEVEL=INFO
```

---

## Roadmap

- [x] Basic PII scrubbing framework for emails, IPs, and API keys.
- [x] DuckDB database engine for local log file query handling.
- [ ] Router / Planner agent (`src/agents/router_agent.py`).
- [ ] Synthesizer agent (`src/agents/synthesizer_agent.py`).
- [ ] Multi-agent orchestration pipeline using LangGraph (`Router -> SQL/Diagnostic -> Synthesizer`).
- [ ] **Deferred:** `SecurityAgent` + RBAC node. Intentionally sequenced after the graph above works end-to-end — this is a solo personal-project POC with no multi-user/role model yet, so RBAC would be speculative today. Revisit once the graph is stable or a real driver appears (multi-user access, real secrets in logs). See `TODO.md` for the full reasoning.
- [ ] Presidio/NER-based PII detection (in addition to today's regex scrubbing).
- [ ] Implement ClickHouse and Elasticsearch engine adapters.
- [ ] Add streaming response support for real-time log tailing.
- [ ] Implement automated alert root-cause diagnostic reports.

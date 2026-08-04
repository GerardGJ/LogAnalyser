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
9. [Configuration & Environment Variables](#configuration--environment-variables)
10. [Roadmap](#roadmap)

---

## Objective

Modern microservice architectures generate massive volumes of log data across disparate storage systems. Investigating incidents, computing error metrics, and tracing failures across distributed systems often requires specialized query knowledge (e.g., SQL, KQL, Elasticsearch DSL) and manual log parsing.

The **Production Log Analyzer** solves this challenge by providing:
* **Natural Language Telemetry Interface:** Converts plain English user queries into optimized, execution-engine queries (e.g., Text-to-SQL).
* **Multi-Agent Collaborative Intelligence:** Decouples complex analytical workflows—such as security checks, SQL query generation, error stack-trace diagnosis, and synthesis—into specialized, deterministic AI agents.
* **Engine-Agnostic Query Layer:** Operates seamlessly over local log formats (JSON, CSV, Parquet) for Proof-of-Concept (POC) environments, with pluggable support for enterprise log databases (ClickHouse, PostgreSQL, Databricks, Snowflake, OpenSearch).
* **Privacy & Security Guardrails:** Enforces Role-Based Access Control (RBAC) and automated PII masking at both ingestion and query execution, ensuring sensitive payload data never leaves the security perimeter.

---

## Key Features

* **Multi-Agent Orchestration:** Powered by graph-based workflows (`LangGraph`), ensuring predictable state transitions and deterministic query handling.
* **Context-Aware Log Sampling:** Avoids context window limits by leveraging SQL for aggregations and using deterministic top-K sampling for stack-trace diagnosis.
* **Automated SQL Self-Correction:** The Text-to-SQL agent automatically inspects schema definitions and self-corrects syntax errors if database execution fails.
* **Two-Tier PII Masking:** Built-in regex and Named Entity Recognition (NER) pipeline (via Microsoft Presidio) to scrub API keys, JWTs, emails, and IP addresses before LLM invocation.

---

## System Architecture & Workflow

The architecture follows a graph-based multi-agent orchestration design pattern. User prompts pass through a multi-stage execution pipeline where agents interact with database abstractions, PII scrubbers, and context management modules.

```
                                  ┌───────────────────────────┐
                                  │   User Interface / API    │
                                  └─────────────┬─────────────┘
                                                │
                                                ▼
                                  ┌───────────────────────────┐
                                  │ 1. Security & RBAC Agent  │
                                  └─────────────┬─────────────┘
                                                │
                                                ▼
                                  ┌───────────────────────────┐
                                  │  2. Router / Planner      │
                                  └─────────────┬─────────────┘
                                                │
                        ┌───────────────────────┴───────────────────────┐
                        │                                               │
                        ▼                                               ▼
          ┌───────────────────────────┐                   ┌───────────────────────────┐
          │  3. Text-to-SQL Agent     │                   │  4. Log Diagnostic Agent  │
          │  (Metrics & Aggregations) │                   │  (Unstructured Traces)    │
          └─────────────┬─────────────┘                   └─────────────┬─────────────┘
                        │                                               │
                        └───────────────────────┬───────────────────────┘
                                                │
                                                ▼
                                  ┌───────────────────────────┐
                                  │ 5. Synthesizer Agent      │
                                  └─────────────┬─────────────┘
                                                │
                                                ▼
                                  ┌───────────────────────────┐
                                  │  Final Formatted Output   │
                                  └───────────────────────────┘
```

### Execution Flow Sequence

1. **Authentication & Sanitization (Agent 1):** The user's query and security scope (JWT/Role) enter the Security Agent. PII is scrubbed, and user permissions are validated.
2. **Intent Planning & Routing (Agent 2):** The Router analyzes the query intent. It routes analytical/metric queries (e.g., *"What is the error rate by service today?"*) to the Text-to-SQL Agent, and deep diagnostic questions (e.g., *"Why is authentication failing?"*) to the Log Diagnostic Agent.
3. **Execution & Telemetry Fetching (Agents 3 & 4):**
   * **Text-to-SQL Agent** inspects the target database schema, drafts a SQL query, executes it against the database abstraction layer, and validates the output tabular dataset.
   * **Log Diagnostic Agent** queries representative sample logs (e.g., top 15-20 failed trace stack traces) to analyze underlying error patterns without exceeding context window constraints.
4. **Response Synthesis & Formatting (Agent 5):** The Synthesizer compiles query results, execution metadata, and root-cause summaries into a clean, markdown-formatted response while enforcing outgoing PII compliance.

---

## Multi-Agent Design & Responsibilities

The system divides operational responsibilities across five dedicated agents:

| Agent | Core Responsibility | Input | Output | Primary Tools / Technologies |
| :--- | :--- | :--- | :--- | :--- |
| **1. Security & RBAC Agent** | Validates user role permissions and sanitizes incoming natural language prompts to scrub sensitive credentials or PII. | Raw User Prompt + User Token | Scrubbed Prompt + Access Scope | Microsoft Presidio, Custom Regex, Auth Scopes |
| **2. Router / Planner Agent** | Classifies incoming intent and chooses the optimal execution strategy (SQL Aggregation vs. Stack Trace Diagnosis). | Scrubbed Prompt | Routing Target (`sql` \| `diagnostic`) | LangGraph Conditional Routing, Intent Classifier |
| **3. Text-to-SQL Agent** | Generates dialect-appropriate SQL queries, executes them against the database abstraction layer, and self-corrects syntax errors. | Natural Language Question + Schema | Structured Tabular Data / Aggregations | Database Dialect Engine, Schema Inspector, Query Validator |
| **4. Log Diagnostic Agent** | Performs semantic inspection and root-cause identification on unstructured log messages, stack traces, and exception frames. | Sampled Log Traces (JSON/Text) | Analytical Root-Cause Summary | Stack Trace Parser, Context Truncator, Exception Profiler |
| **5. Synthesizer Agent** | Merges structured tables, diagnostic summaries, and execution stats into a coherent, markdown-formatted response. | SQL Outputs + Diagnostic Summaries | Final Natural Language Answer | Markdown Formatter, Response Auditor |

---

## Standard Log Schema

For maximum inter-compatibility across engines, the POC standardizes log ingestion around a 5-field schema baseline:

| Column Name | Data Type | Description |
| :--- | :--- | :--- |
| `timestamp` | `TIMESTAMP` | ISO-8601 UTC timestamp of log event generation. |
| `level` | `VARCHAR` | Log severity classification (`INFO`, `WARN`, `ERROR`, `FATAL`, `DEBUG`). |
| `trace_id` | `VARCHAR` | Unique request correlation identifier across distributed microservices. |
| `service` | `VARCHAR` | Name of the microservice or component emitting the log event. |
| `message` | `TEXT` | Log event payload, containing text descriptions, error messages, or stack traces. |

---

## Database Engine & Abstraction Layer

To maintain engine independence, the system utilizes an abstract database interface (`BaseEngine`). Local development and POC environments default to **DuckDB** or **SQLite** operating directly over raw log files (JSON, CSV, Parquet).

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

To prevent sensitive operational data from leaking to external LLM providers, the system implements a dual-stage PII pipeline:

1. **Ingestion In-Flight Redaction:** Regex maskers automatically replace key patterns before database ingestion:
   * **API Keys & Tokens:** `[REDACTED_SECRET]`
   * **IPv4 / IPv6 Addresses:** `192.168.x.x`
   * **Email Addresses:** `[REDACTED_EMAIL]`
2. **Context Guardrails:** The Security Agent scans user questions and limits context window injection size, enforcing explicit `LIMIT` parameters on all generated SQL queries.

---

## Project Structure

```
production-log-analyzer/
│
├── README.md                     # Project documentation & setup instructions
├── requirements.txt              # Python dependency specifications
├── .env.example                  # Environment variable configuration template
├── pyproject.toml                # Build system and linting setup
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
│   │   ├── base.py               # Abstract BaseEngine interface class
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

* **Python:** `>= 3.10`
* **Virtual Environment:** `venv` or `conda`

### Installation

1. **Clone the Repository:**
   ```bash
   git clone https://github.com/your-org/production-log-analyzer.git
   cd production-log-analyzer
   ```

2. **Set Up Virtual Environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Environment Setup:**
   Copy the example configuration file and set your API credentials:
   ```bash
   cp .env.example .env
   ```

5. **Load Sample Logs into Local Engine (POC):**
   ```bash
   python -m src.utils.log_loader --input data/raw_logs/sample_production.json
   ```

6. **Run the Interactive CLI Chatbot:**
   ```bash
   python main.py
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
DUCKDB_PATH=data/duckdb/logs.duckdb

# Security & PII Settings
ENABLE_PII_SCRUBBING=true
LOG_LEVEL=INFO
```

---

## Roadmap

- [ ] Multi-agent orchestration pipeline using LangGraph.
- [ ] DuckDB database engine for local log file query handling.
- [ ] Basic PII scrubbing framework for emails, IPs, and API keys.
- [ ] Implement ClickHouse and Elasticsearch engine adapters.
- [ ] Add streaming response support for real-time log tailing.
- [ ] Implement automated alert root-cause diagnostic reports.
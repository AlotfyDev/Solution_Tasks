
# Task Toolkit — نظام إدارة مهام البرمجيات

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![GitHub](https://img.shields.io/badge/github-AlotfyDev%2FSolution--Tasks-181717?logo=github)](https://github.com/AlotfyDev/Solution_Tasks)
[![MCP](https://img.shields.io/badge/MCP-Enabled-6C47FF)](https://modelcontextprotocol.io)

---

**English** · [Arabic](#ملخص-بالعربية)

---

## ملخص بالعربية

**Task Toolkit** هو نظام إدارة مهام متكامل يعمل على تتبع وتنظيم مهام التطوير والاختبار في مشاريع البرمجيات. يعتمد النظام على schemas JSON للتحقق من صحة البيانات، وقاعدة بيانات SQLite للتخزين، وواجهات CLI و MCP للتفاعل مع البيئات التطويرية والمساعدات الذكية.

يقدم النظام نظامين أساسيين للمهام: مهام **التطبيق** (AA) ومهام **الاختبار** (TD)، مع إمكانية الربط بينهما لتتبع التغطية الاختبارية. كما يدير مستندات المواصفات بصيغة Markdown ويستخرج منها المهام تلقائياً.

---

## Overview

**Task Toolkit** is a modular task management system designed for software projects that demand rigorous traceability between implementation work and test coverage. It originated within a cross-language C++17 trading system to track post-audit remediation (AA — After Audit) and test design (TD) tasks, but its schema-driven architecture makes it adaptable to any software project.

The system validates every task against a JSON Schema (Draft 07) before accepting it, stores all data in SQLite with WAL mode and full audit history, and exposes its functionality through both a traditional CLI and an MCP (Model Context Protocol) server that integrates directly with AI-assisted IDEs like Cline, Kilocode, and VS Code Copilot.

---

## Why This Matters

| Aspect | Impact |
|--------|--------|
| **Traceability** | Every task links to its source spec document, acceptance criteria, and related test tasks |
| **Audit Trail** | All status changes, creations, and deletions recorded with timestamps |
| **AI Integration** | MCP server enables LLMs to create, update, query, and link tasks autonomously |
| **Standardization** | JSON Schema validation ensures consistent task structure across the team |
| **Gap Analysis** | Automated detection of implementation tasks without test coverage |
| **Portability** | SQLite with WAL mode — zero infrastructure, one file |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        CLI (task)                           │
│   validate │ insert │ get │ list │ update │ delete │ link   │
│   import │ export │ batch-* │ load-docs │ catalog │ port    │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                   MCP Server (task-mcp)                     │
│   Transport: stdio (local) │ SSE (network, port 8000)      │
│   28 tools │ 5 resources │ 3 schemas │ 4 relationship types│
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                    Application Layer                        │
│   ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│   │ TaskStore │  │ Validator│  │History   │  │ Report   │  │
│   │ (CRUD)   │  │(JSON S.) │  │ Tracker  │  │Generator │  │
│   └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘  │
└──────────┼────────────┼──────────────┼──────────────┼───────┘
           │            │              │              │
┌──────────▼────────────▼──────────────▼──────────────▼───────┐
│                    SQLite (tasks.db)                         │
│   WAL mode │ Foreign keys │ Per-schema tables               │
│   tasks_implementation │ tasks_testing │ tasks_document     │
│   task_relationships │ task_history                          │
└──────────────────────────────────────────────────────────────┘
```

### Layer Descriptions

1. **CLI** (`task`) — Command-line interface for all operations
2. **MCP Server** (`task-mcp`) — AI-accessible server using Model Context Protocol
3. **Application Layer** — Store, Validator, History Tracker, Report Generator
4. **Persistence** — SQLite with automatic schema-based table creation

---

## Quick Start

### Prerequisites

- Python 3.10+
- pip

### Installation

```bash
# Clone the repository
git clone https://github.com/AlotfyDev/Solution_Tasks.git
cd Solution_Tasks

# Install dependencies
pip install -r requirements.txt

# Optional: for SSE (network) MCP mode
pip install uvicorn

# Or install the package itself
pip install -e .
```

### First Steps

```bash
# Validate a task file
task validate path/to/task.json

# Insert a task
task insert path/to/task.json

# List all implementation tasks
task list

# List all testing tasks
task list --schema testing

# Check progress
task status

# View the complete catalog
task catalog
```

### MCP Server

```bash
# stdio mode (for IDE subprocess)
task-mcp

# SSE mode (network daemon)
task-mcp --sse --port 8000
```

---

## Schema System

The toolkit uses a **pluggable schema registry**. Each schema defines the JSON Schema validation rules, SQL table layout, and task ID prefix.

### Implementation Schema (AA)

| Field | Type | Description |
|-------|------|-------------|
| `sub_task_id` | `string` | Pattern: `^[A-Z][A-Z0-9._-]+$` (e.g., `C05-01`) |
| `sequence` | `integer` | Order within parent spec |
| `hierarchy_level` | `integer` | 1–10, task nesting depth |
| `metadata.phase` | `integer` | 0–9, project phase |
| `metadata.effort` | `string` | Effort estimate |
| `task.title` | `string` | Task title |
| `task.description` | `string` | Task description |
| `task.acceptance_criteria` | `array` | `[{id, description, verified_by}]` |
| `task.files_to_modify` | `array` | `[{path, change_type, description}]` |
| `status.state` | `string` | `pending │ in_progress │ completed │ blocked │ cancelled` |
| `traceability.td_reference` | `string` | Links to related test spec |

### Testing Schema (TD)

| Field | Type | Description |
|-------|------|-------------|
| `sub_task_id` | `string` | Pattern: `^TD-[A-Z0-9._-]+$` (e.g., `TD-C05-01`) |
| `metadata.test_level` | `string` | `unit │ integration │ benchmark │ emergency │ thread_safety` |
| `task.scenarios` | `array` | `[{id, name, type}]` with types: `positive │ negative │ production │ thread_safety │ edge_case` |
| `task.files_to_modify` | `array` | Per-file test cases with framework (`gtest │ native_unit_test`) and status (`template │ implemented │ passing │ failing`) |
| `task.acceptance_criteria` | `array` | Test criteria with `TC-*` IDs |
| `traceability.aa_reference` | `string` | Links to the AA task being tested |
| `traceability.aa_sub_task_ids` | `array` | Specific sub-task IDs covered |

### Document Schema

| Field | Type | Description |
|-------|------|-------------|
| `doc_id` | `string` | Format: `{CLASS}-{SERIAL}-{TOPIC}` |
| `file_path` | `string` | Original markdown file path |
| `title` | `string` | Extracted from `# ` heading |
| `content` | `string` | Full markdown content |
| `metadata.phase` | `integer` | Phase extracted from filename (TD-`N`) |

---

## MCP Tools

The MCP server exposes **28 tools** and **5 resources** organized into categories:

### Task CRUD (6 tools)

| Tool | Description |
|------|-------------|
| `insert_task` | Validate + insert a task from JSON |
| `get_task` | Full task with criteria, files, tags, scenarios, test cases |
| `list_tasks` | Filter by schema, status, phase |
| `update_status` | Change task state (pending → in_progress → completed) |
| `update_task` | Update arbitrary field |
| `delete_task` | Remove task and all sub-entities |

### Document Management (6 tools)

| Tool | Description |
|------|-------------|
| `insert_document` | Insert a document record |
| `get_document` | Get document by ID |
| `list_documents` | List all documents |
| `update_document` | Update document fields |
| `delete_document` | Delete document |
| `import_documents` | Batch-import `.md` files as documents |
| `normalize_doc_id` | Generate standard `doc_id` from filename |

### Relationships (2 tools)

| Tool | Description |
|------|-------------|
| `link_tasks` | Create relationship (tests, depends_on, implements, verifies) |
| `unlink_tasks` | Delete a relationship |

### Batch Operations (4 tools)

| Tool | Description |
|------|-------------|
| `import_tasks` | Batch import JSON task files from directory |
| `export_tasks` | Export tasks to JSON files |
| `batch_link_tasks` | Batch link by field matching or mapping file |
| `batch_update_status` | Bulk status update by phase or IDs |
| `batch_delete_tasks` | Bulk delete by phase or IDs |

### Reports & Utilities (6 tools)

| Tool | Description |
|------|-------------|
| `status_report` | Full progress: counts by schema, phase, blocked tasks, activity |
| `gap_analysis` | Find untested implementations, stale tasks, empty schemas |
| `dependency_chain` | Recursive task dependency tree |
| `search_tasks` | Full-text search across schemas |
| `validate_task` | Validate JSON without inserting |
| `get_history` | Change history for a task |
| `reload_schemas` | Force schema reload from disk |
| `get_catalog` | Complete system catalog (markdown or JSON) |

### MCP Resources (5 resources)

| URI | Description |
|-----|-------------|
| `task://{schema_id}/{task_id}` | Task as structured JSON |
| `doc://{doc_id}` | Document as JSON |
| `schema://{schema_id}` | JSON Schema definition |
| `report://status` | Full status report (markdown) |
| `catalog://overview` | Complete tool catalog |

---

## CLI Commands

| Command | Description |
|---------|-------------|
| `validate` | Validate JSON task file against schema |
| `insert` | Validate + insert task into database |
| `get` | Retrieve task with all sub-entities |
| `list` | List tasks with filters |
| `query` | Execute raw SQL (SELECT/PRAGMA only) |
| `update` | Change task status |
| `delete` | Delete a task |
| `link` | Create relationship between two tasks |
| `status` | Show progress summary |
| `schemas` | List registered schemas |
| `history` | Change log for a task |
| `log` | Recent changes across all tasks |
| `import` | Import all JSON files from a directory |
| `export` | Export tasks to JSON files |
| `port` | Find available TCP ports |
| `catalog` | Display tool catalog |
| `batch-import` | Enhanced batch import with dry-run/skip-errors |
| `batch-link` | Batch link by field or mapping file |
| `batch-update` | Bulk status update |
| `batch-delete` | Bulk delete |
| `load-docs` | Parse markdown specs → documents + tasks |
| `import-documents` | Batch-import markdown as documents |
| `list-documents` | List loaded documents |
| `delete-document` | Delete document |
| `update-document` | Update document from JSON |
| `normalize-doc-id` | Generate standard doc_id |

---

## Document Management

Documents represent the source markdown specification files. The system uses a standard naming convention:

### Doc ID Convention

```
{CLASS}-{SERIAL}-{TOPIC}
```

| Part | Value | Example |
|------|-------|---------|
| CLASS | `AA` │ `TD` │ `IMPACT` │ `DOC` | `AA` |
| SERIAL | Numeric hierarchy (e.g., `5.1`, `M05`) | `5.1` |
| TOPIC | PascalCase description | `RateLimiting` |

**Examples:** `AA-5.1-RateLimiting`, `TD-4.13-StderrSink`, `AA-M05-RateLimiting`

### Workflow

1. **Import** markdown files as documents (`task import-documents --dir specs/`)
2. **Parse** spec files into structured tasks (`task load-docs --dir specs/`)
3. **Link** documents to their extracted sub-tasks via `parent_doc_id`
4. **Track** document status independently from tasks

### Spec Parser

The `spec_parser/` module parses markdown spec files into:

- **Document records** — full content stored in `tasks_document`
- **Implementation sub-tasks** — AA tasks with acceptance criteria, file references
- **Testing sub-tasks** — TD tasks with scenarios, test cases, frameworks

The parser uses `mistune` for markdown tokenization and extracts structured data from section headings, code blocks, and list items.

---

## Relationships

Tasks link together through a dedicated `task_relationships` table:

| Type | Source → Target | Purpose |
|------|----------------|---------|
| `tests` | `testing` → `implementation` | TD test task verifies AA implementation |
| `depends_on` | `implementation` → `implementation` | Hard/soft dependency between implementation tasks |
| `implements` | `implementation` → `implementation` | Parent-child hierarchy |
| `verifies` | `testing` → `implementation` | Test case verifies specific acceptance criterion |

### Batch Linking

Automatically link testing tasks to their corresponding implementation tasks:

```bash
# By field matching (e.g., parent_aa_id)
task batch-link --source-schema testing --target-schema implementation --rel-type tests --by-field parent_aa

# From a mapping file
task batch-link --from-file mapping.json
```

---

## Configuration

### Database Path Priority

| Priority | Method | Example |
|----------|--------|---------|
| 1 (highest) | `--db-dir` flag | `task --db-dir /path/to/data list` |
| 2 | `TASK_DB_DIR` env var | `$env:TASK_DB_DIR="/path/to/data"` |
| 3 (default) | Project `.data/` dir | `Solution_Tasks/.data/tasks.db` |

### MCP Server Modes

| Mode | Command | Transport | Use Case |
|------|---------|-----------|----------|
| **stdio** | `task-mcp` | stdin/stdout | IDE spawns as subprocess |
| **SSE** | `task-mcp --sse` | HTTP on `127.0.0.1:8000` | Network daemon, multiple clients |

### Environment Variables

| Variable | Purpose |
|----------|---------|
| `TASK_DB_DIR` | Override database directory |
| `TASK_EXPORT_DIR` | Default export output directory |

---

## Project Structure

```
Solution_Tasks/
├── .data/                          # SQLite database (auto-created)
│   ├── tasks.db
│   ├── tasks.db-shm
│   └── tasks.db-wal
├── default_schemas/                # JSON Schema files
│   ├── implementation-schema.json
│   ├── testing-schema.json
│   ├── document-schema.json
│   └── example-testing-task.json
├── docs/
│   ├── Tasks/                      # Task specification docs
│   └── impact-analysis-document-loader.md
├── spec_parser/                    # Markdown spec parsing
│   ├── parser.py
│   ├── loader.py
│   └── extractor.py
├── task_cli/                       # Core application
│   ├── data/
│   │   ├── engine.py               # SQLite connection, WAL, table creation
│   │   └── store.py                # CRUD operations for tasks & documents
│   ├── history/
│   │   └── tracker.py              # Audit trail
│   ├── presentation/
│   │   ├── commands.py             # CLI command handlers (1278 lines)
│   │   ├── catalog.py              # Self-documenting tool catalog
│   │   └── report.py               # Status reports & gap analysis
│   ├── registry/
│   │   └── base.py                 # Schema & relationship registries
│   ├── schemas/                    # Schema registration
│   ├── validation/
│   │   ├── validator.py            # JSON Schema validation
│   │   └── business_rules.py       # Domain-specific rules
│   ├── utils/
│   ├── main.py                     # CLI entry point
│   └── mcp_server.py               # MCP server entry point
├── tests/                          # Test suite
│   ├── test_*.py                   # pytest tests
│   └── conftest.py
├── scratch/                        # Development scripts
├── MCP_CONFIG.md                   # IDE integration guide
├── pyproject.toml                  # Project metadata
└── requirements.txt                # Python dependencies
```

---

## Development

### Running Tests

```bash
pytest
```

### Adding a New Schema

1. Create a JSON Schema file in `default_schemas/`
2. Register it in `task_cli/schemas/`
3. Define DDL statements and table names
4. The system auto-creates tables on connect

---

## License

MIT License — see [LICENSE](LICENSE) for details.

---

## Links

- **GitHub:** [https://github.com/AlotfyDev/Solution_Tasks](https://github.com/AlotfyDev/Solution_Tasks)
- **MCP Configuration:** [MCP_CONFIG.md](MCP_CONFIG.md)
- **Issues & Feedback:** GitHub Issues

---

*Built with Python 3.11+, SQLite, JSON Schema (Draft 07), and FastMCP.*

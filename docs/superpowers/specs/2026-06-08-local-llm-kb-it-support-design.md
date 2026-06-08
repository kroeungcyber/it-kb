# Design: itkb — Local LLM IT Knowledge Base

**Date:** 2026-06-08  
**Status:** Approved  
**Scope:** Personal/solo use — query your own IT notes, runbooks, configs, PDFs, and web pages using a fully local LLM stack (no cloud APIs).

---

## 1. Architecture Overview

Six layers, each with one responsibility:

```
┌──────────────────────────────────────────────────────┐
│  Interfaces                                          │
│   CLI (Typer)          Web UI (FastAPI + vanilla JS) │
└──────────────────────┬───────────────────────────────┘
                       │
┌──────────────────────▼───────────────────────────────┐
│  Agent Loop  (Ollama LLM — ReAct style)              │
│   tools: search_kb │ run_command │ cite │ followups  │
└──────────────────────┬───────────────────────────────┘
                       │
┌──────────────────────▼───────────────────────────────┐
│  Vector Store  (SQLite + sqlite-vec)                 │
│   documents │ chunks + embeddings │ command history  │
└──────────────────────┬───────────────────────────────┘
                       │
┌──────────────────────▼───────────────────────────────┐
│  Ingestion Pipeline                                  │
│   parsers (md, PDF, DOCX, web, YAML/JSON/config)     │
│   → chunker → embedder (Ollama nomic-embed-text)     │
└──────────────────────────────────────────────────────┘
```

**Ollama models:**
- Embeddings: `nomic-embed-text` (768 dimensions)
- LLM: `llama3.1:8b` (default, configurable)

**Data flow — query path:**
1. User question → embed via `nomic-embed-text`
2. Vector search → top-k=5 chunks from SQLite
3. Agent loop → LLM streams answer with tool calls
4. Citations rendered below answer; commands require explicit confirmation

**Data flow — ingest path:**
1. File/URL → format parser → raw text
2. Chunker → 512-token chunks with 64-token overlap
3. Embedder → `nomic-embed-text` via Ollama
4. Store chunks + embeddings in SQLite

---

## 2. Ingestion Pipeline

**File: `itkb/ingestion/parsers.py`**

| Format | Library |
|--------|---------|
| `.md`, `.txt`, `.rst` | built-in `open()` |
| `.pdf` | `pypdf` |
| `.docx` | `python-docx` |
| `.yaml`, `.json`, `.toml`, `.conf`, `.ini` | read as-is, structure preserved |
| URLs / web pages | `httpx` + `markdownify` |

**Chunking (`itkb/ingestion/chunker.py`):**
- Chunk size: 512 tokens, overlap: 64 tokens
- Split order: `\n\n` boundaries → sentences → tokens
- Metadata per chunk: `source_path`, `title`, `page_number` (PDF), `section_heading` (markdown `#` headers)

**Embedding (`itkb/ingestion/embedder.py`):**
- Calls `POST /api/embeddings` on local Ollama server
- Batches: 32 chunks per request
- Incremental: skips re-embedding if file `mtime` is unchanged

**CLI ingest commands:**
```
kb add <path>          # file or directory (recursive)
kb add --url <url>     # scrape and ingest a web page
kb add --watch <dir>   # watch directory, auto-ingest on changes
```

---

## 3. Vector Store & Data Model

**Storage:** `~/.itkb/kb.sqlite` — single portable file using the `sqlite-vec` extension.

**Schema:**

```sql
-- source documents
CREATE TABLE documents (
    id          TEXT PRIMARY KEY,   -- sha256 of source_path
    source_path TEXT NOT NULL,
    title       TEXT,
    file_type   TEXT,
    ingested_at TEXT,
    chunk_count INTEGER,
    mtime       REAL                -- for incremental re-ingest detection
);

-- text chunks
CREATE TABLE chunks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id      TEXT REFERENCES documents(id) ON DELETE CASCADE,
    content     TEXT NOT NULL,
    chunk_index INTEGER,
    metadata    TEXT                -- JSON: page, section, heading
);

-- vector index (sqlite-vec, 768 dims for nomic-embed-text)
CREATE VIRTUAL TABLE chunk_embeddings USING vec0(
    chunk_id    INTEGER PRIMARY KEY,
    embedding   FLOAT[768]
);

-- shell command audit log
CREATE TABLE command_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    command     TEXT NOT NULL,
    output      TEXT,
    exit_code   INTEGER,
    ran_at      TEXT,
    query_id    TEXT                -- which query triggered this
);
```

**Retrieval:** cosine similarity via `vec_distance_cosine`, top-k=5 default, configurable per query with `-k`.

**Re-ingestion:** if `mtime` changes, old chunks deleted and re-embedded. Full re-index via `kb reindex`.

---

## 4. Agent Loop & Tools

**Pattern:** ReAct (Reason → Act → Observe → repeat), max 5 iterations before forcing a final answer.

**System prompt:** Instructs the LLM it is a personal IT support assistant with access to a local knowledge base and a shell. Must always cite sources. Must always ask for confirmation before running commands.

**Tools (`itkb/agent/tools.py`):**

```python
search_kb(query: str, top_k: int = 5)
    # retrieves top-k chunks from SQLite; returns content + metadata

cite_sources()
    # returns formatted list of source documents used in current context

suggest_followups(answer: str)
    # asks LLM to generate 3 related follow-up questions

run_command(command: str)
    # CLI: prints command, prompts "Run this? [y/N]"
    # Web UI: shows confirmation dialog, calls POST /api/command/confirm
    # captures stdout/stderr, logs to command_history
    # hard-blocked: rm -rf, dd, mkfs, shutdown, reboot
```

**Streaming:** Agent streams tokens to CLI stdout and via SSE (`text/event-stream`) to the web UI.

**Tool calling:** Uses Ollama's native function-calling API (supported by `llama3.1`, `mistral`, `qwen2.5`). Falls back to prompt-based tool parsing for models without native support.

**Security:**
- `run_command` requires explicit confirmation every time — never auto-executes
- `--trusted` CLI flag bypasses confirmation prompt for scripted use only
- Hard-blocked command patterns checked before any execution

---

## 5. CLI Interface

**Entry point:** `kb` command, installed via `pyproject.toml` script entry.

**Commands:**

```
kb add <path>                  # ingest file or directory (recursive)
kb add --url <url>             # scrape and ingest a web page
kb add --watch <dir>           # watch directory, auto-ingest on changes

kb query "<question>"          # ask a question, stream answer
kb query "<question>" -k 8     # increase retrieval top-k
kb query "<question>" --no-run # disable command execution for this query

kb list                        # list all ingested documents (Rich table)
kb delete <doc-id>             # remove a document and its chunks
kb reindex                     # re-embed all documents (after model change)

kb serve                       # start web UI on localhost:8000
kb serve --port <n>            # custom port

kb models                      # list available Ollama models
kb config show                 # print current config
kb config set model <name>     # change LLM model
kb config set embed <name>     # change embedding model
```

**Output style:**
- `list`: Rich-formatted table
- `query`: streaming markdown via `rich.markdown`, citations in dim text below answer
- Errors: Rich-styled with actionable messages (e.g., "Ollama not running — start with `ollama serve`")

**Config file:** `~/.itkb/config.toml`

```toml
model = "llama3.1:8b"
embed_model = "nomic-embed-text"
db_path = "~/.itkb/kb.sqlite"
top_k = 5
trusted = false
```

---

## 6. Web UI

**Backend:** FastAPI app (`itkb/api/app.py`), served on `localhost:8000`.

**Frontend:** Vanilla JS + minimal CSS, no build step, no Node.js dependency. Served as static files.

**Routes:**

```
GET  /                         → chat UI
GET  /docs                     → document library
GET  /history                  → query history

POST /api/query                → streams answer via SSE
POST /api/ingest               → ingest file path or URL
GET  /api/documents            → list all documents (JSON)
DELETE /api/documents/:id      → remove a document
GET  /api/models               → list available Ollama models
POST /api/command/confirm      → confirm and execute a pending command
```

**Chat UI:**
- Question input → SSE stream renders tokens in real time
- Citations appear as collapsible cards below answer (filename + excerpt)
- Follow-up suggestions appear as clickable chips
- Command proposals show a confirmation dialog — never auto-executes

**Document library:**
- Table: title, type, chunk count, ingested date
- Path input or drag-and-drop to add new files
- Delete button per row with confirmation

---

## 7. Project Structure

```
itkb/
├── pyproject.toml
├── itkb/
│   ├── __init__.py
│   ├── config.py                  # settings from ~/.itkb/config.toml
│   ├── cli.py                     # Typer entry point
│   ├── ingestion/
│   │   ├── __init__.py
│   │   ├── parsers.py             # per-format parsers
│   │   ├── chunker.py             # text → chunks with metadata
│   │   └── embedder.py            # Ollama embed API calls
│   ├── store/
│   │   ├── __init__.py
│   │   ├── db.py                  # SQLite + sqlite-vec init and CRUD
│   │   └── models.py              # Document, Chunk dataclasses
│   ├── agent/
│   │   ├── __init__.py
│   │   ├── loop.py                # ReAct agent loop (max 5 iterations)
│   │   ├── tools.py               # search_kb, run_command, cite, followups
│   │   └── prompts.py             # system prompt templates
│   └── api/
│       ├── __init__.py
│       ├── app.py                 # FastAPI app + all routes
│       └── web/
│           ├── static/            # JS, CSS
│           └── templates/         # HTML pages (chat, docs, history)
├── tests/
│   ├── test_parsers.py
│   ├── test_chunker.py
│   ├── test_store.py
│   └── test_agent.py              # mocks Ollama — no live model needed
└── data/                          # gitignored — holds kb.sqlite
```

**Dependencies (`pyproject.toml`):**

```toml
[project]
dependencies = [
    "pypdf>=4.0",
    "python-docx>=1.1",
    "markdownify>=0.12",
    "httpx>=0.27",
    "sqlite-vec>=0.1",
    "ollama>=0.3",
    "fastapi>=0.111",
    "uvicorn>=0.30",
    "typer>=0.12",
    "rich>=13.0",
    "tomli-w>=1.0",
    "watchdog>=4.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "pytest-mock>=3.0"]

[project.scripts]
kb = "itkb.cli:app"
```

---

## 8. Testing Strategy

- **Unit tests** mock the Ollama client — no live model required, runs anywhere
- **Integration tests** marked `@pytest.mark.integration` — require running Ollama instance, skipped in CI
- **Coverage targets:** parsers (all formats), chunker (boundary cases), store (CRUD + vector search), agent tools (mock responses)
- **Security test:** `run_command` hard-block list verified to reject dangerous patterns regardless of LLM output

---

## Non-Goals

- Multi-user support — this is personal/solo use only
- Cloud sync or remote access
- Fine-tuning or model training
- Support for non-Ollama backends (no abstraction layer needed)

# itkb — Local LLM IT Knowledge Base

Your personal IT support system. Feed it runbooks, notes, PDFs, and wiki pages.
Ask questions naturally. It searches your documents and answers with citations.

Everything runs locally — Ollama for LLM, SQLite for storage, your browser for UI.

## Quick Start

```bash
# 1. Install
cd ~/itkb
pip install -e .

# 2. Make sure Ollama has the models you set in PROGRAM.md
ollama list

# 3. Add some knowledge
kb add ~/notes/runbooks.md
kb add --url https://wiki.example.com/nginx-troubleshooting

# 4. Ask a question
kb query "how do I rotate SSL certificates?"

# 5. Open web UI
kb serve
# → http://localhost:8000
```

## Central Control — PROGRAM.md

**Every operation requires approval through PROGRAM.md.** This file is the single
source of truth for what itkb can do. Edit it, save it, and the agent enforces it
on the next query.

```yaml
# PROGRAM.md — what you control:

## Models                  # which Ollama models to use
chat: gemma4:latest
embed: embeddinggemma:latest

## Path Whitelist          # only these directories can be ingested
- /Users/bila/notes/
- /tmp/

## URL Whitelist           # only these URL prefixes can be scraped
- https://wiki.
- https://docs.

## Command Execution       # OFF by default — you must explicitly enable
commands_enabled: false    # set to true when you're ready

## Query Behavior
top_k: 5                   # how many chunks to retrieve per search
trusted: false             # if true, commands run without confirmation prompt
```

### Safety model

| Setting | Default | What it does |
|---------|---------|-------------|
| `commands_enabled` | `false` | Blocks ALL shell commands until you explicitly approve |
| Path whitelist | empty | Only listed directories can be ingested |
| URL whitelist | empty | Only listed URL prefixes can be scraped |
| Blocked patterns | permanent | `rm -rf`, `dd if=`, `mkfs`, `shutdown`, `reboot`, fork bombs — never allowed |
| Confirmation prompt | per-command | Even when enabled, YOU must type `y` for each command |

**To enable commands:** open `PROGRAM.md`, change `commands_enabled: false` to
`commands_enabled: true`, save. That's your explicit approval.

## Commands

```
kb add <path>              # Ingest a file or directory
kb add --url <url>         # Ingest a web page
kb add --watch <dir>       # Watch a directory for changes

kb query "question"        # Ask a question (streaming answer)
kb query -k 10 "q"         # Return more search results

kb list                    # Show all ingested documents
kb delete <doc-id>         # Remove a document

kb serve                   # Start web UI at http://localhost:8000
kb serve --port 3000       # Custom port

kb models                  # List available Ollama models
kb config show             # Show current config
kb config set model llama3.1:8b  # Switch chat model
kb config set embed_model nomic-embed-text  # Switch embedding model

kb reindex                 # Re-embed all docs (after switching embed model)
```

## Web UI

```
http://localhost:8000/          Chat — ask questions, see streaming answers
http://localhost:8000/docs-ui   Documents — add, list, delete knowledge
http://localhost:8000/history   History — command execution log
```

## How It Works

```
Your question  →  embeddinggemma  →  vector search (SQLite vec0)
                                       ↓
                                  top-5 chunks found
                                       ↓
                                  gemma4 ReAct agent
                                  (can search again, propose commands)
                                       ↓
                                  Answer + citations + follow-ups
```

## Files

```
~/.itkb/config.toml     Runtime config (auto-synced from PROGRAM.md)
~/.itkb/kb.sqlite       Your knowledge base (single file)
~/itkb/PROGRAM.md       Central control — edit this to change behavior
```

## Tests

```bash
pytest -v                # 37 unit tests (no Ollama needed)
```

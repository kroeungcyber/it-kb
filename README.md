# itkb — Local LLM IT Knowledge Base

A personal IT support knowledge base that runs entirely locally using Ollama. Ingest your notes, runbooks, PDFs, and web pages — then ask questions via CLI or browser.

## Prerequisites

- Python 3.9+
- [Ollama](https://ollama.ai) running locally
- Models: `ollama pull nomic-embed-text && ollama pull llama3.1:8b`

## Install

```bash
pip install -e .
```

## Usage

```bash
# Ingest content
kb add ~/notes/            # directory of markdown files
kb add --url https://...   # web page
kb add runbook.pdf         # PDF

# Query
kb query "how do I rotate SSL certificates?"

# Browse
kb serve                   # opens http://localhost:8000

# Manage
kb list
kb delete <doc-id>
kb models
kb config show
kb config set model mistral:7b
```

## Tests

```bash
pytest -v                           # unit tests (no Ollama needed)
pytest -m integration               # requires running Ollama
```

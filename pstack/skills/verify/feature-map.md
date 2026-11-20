# it-kb feature map

A sitemap of what a feature *is*, how to reach it, and the proof that it works. Read this
before touching anything; when a bug report arrives with a screenshot and no context, this
is how you find where to look.

## Surfaces

| Surface | Entry point | Proof it works |
|---|---|---|
| CLI | `kb <subcommand>` (`itkb/cli.py`) | run the command, read its stdout/exit code |
| HTTP API | FastAPI at `http://localhost:8000` (`itkb/api/app.py`) | `curl` the endpoint, read the status + body |
| Web UI | `/` chat, `/docs-ui`, `/history` (`itkb/api/web/`) | load the page, drive it, capture the DOM/response |
| Ingest pipeline | `itkb/ingestion/` (parsers → redact → chunker → embedder) | feed a fixture, inspect the stored chunk |

## Feature inventory

### 1. Ask a question (retrieval + answer)

- **How to reach:** `kb query "how do I rotate SSL certs?"` or `POST /api/query`.
- **What it is:** hybrid BM25 (FTS5) + vector (vec0) retrieval merged by RRF, top_k
  chunks, streamed answer with citations.
- **Proof:** a query returns citations that name the source chunk; an off-topic query
  returns no fabricated citation. (`test_store.py`, `test_agent.py`, `test_integration.py`)

### 2. Ingest a document

- **How to reach:** `kb add <path>` / `kb add --url <url>` / `kb add --watch <dir>`,
  or `POST /api/ingest`.
- **What it is:** parse → **PII redact** → heading-aware chunk (512 tok / 64 overlap) →
  embed → store in SQLite.
- **Proof:** a file containing an email/card/phone/SSN yields a stored chunk with
  `[EMAIL REDACTED]` etc., and IPs/hostnames/tokens survive. (`checks.py` PII checks,
  `test_redact.py`, `test_ingest.py`)

### 3. Denied-by-default command execution

- **How to reach:** the agent's `run_command` tool; gated by `PROGRAM.md`.
- **What it is:** `commands_enabled: false` blocks ALL shell commands; blocked patterns
  (`rm -rf`, `dd if=`, `mkfs`, `shutdown`, `reboot`, fork bombs) are permanently denied;
  even when enabled, each command needs a `y` confirmation unless `trusted: true`.
- **Proof:** `commands_enabled()` is `False` by default; a blocked pattern never runs.
  (`checks.py` program checks, `test_program.py`)

### 4. Path and URL whitelists

- **How to reach:** `PROGRAM.md` → `## Path Whitelist` / `## URL Whitelist`.
- **What it is:** only listed directories may be ingested; only listed URL prefixes may
  be scraped. Paths are resolved (symlinks + `..` collapsed) before comparison.
- **Proof:** a path under the whitelist is allowed; `whitelist/../secret` is not.
  (`checks.py` path/url checks)

### 5. Authentication

- **How to reach:** any `/api/*` call requires `X-API-Key` header or `itkb_session` cookie
  (`itkb/api/auth.py`).
- **What it is:** API key auto-generated on first boot; session cookies are HMAC-signed
  digests (the raw key never lives in the cookie), 30-day expiry.
- **Proof:** no key → 401 "Invalid API key or session"; a valid token verifies; a tampered
  token rejects. (`checks.py` auth check, `test_auth.py`)

### 6. Audit log

- **How to reach:** append-only `~/.itkb/audit.jsonl`.
- **What it is:** every query, login, ingest, delete, and command appends one structured
  JSON line.
- **Proof:** perform an action, read the last line, assert the event + fields.
  (`test_audit.py`)

### 7. Configuration precedence

- **How to reach:** `kb config show` / `kb config set ...`; env vars override `config.toml`.
- **What it is:** `ITKB_MODEL` / `ITKB_EMBED_MODEL` / `ITKB_PROGRAM_PATH` / `OLLAMA_HOST`
  env vars > `~/.itkb/config.toml`; `PROGRAM.md` models sync into config.
- **Proof:** set the env var, `load_config()` reflects it. (`test_config.py`)

## Where a symptom points

| Symptom | Look here |
|---|---|
| Answer has no citations / wrong chunk | `itkb/store/db.py` (RRF merge), `itkb/agent/tools.py` (`search_kb`) |
| PII leaking into answers | `itkb/ingestion/redact.py` (regexes), `Config.redact_pii` |
| Legit runbook content being mangled | `redact.py` over-matching (the regexes are deliberately conservative) |
| Command ran without approval | `itkb/program.py` (`commands_enabled`), `itkb/agent/tools.py` (`run_command`) |
| Path traversal allowed | `itkb/program.py` (`ingest_path_allowed`) |
| 401 on a valid request | `itkb/api/auth.py` (`require_auth`), session cookie expiry |
| No audit line | `itkb/audit.py`, `Config.audit_enabled` |

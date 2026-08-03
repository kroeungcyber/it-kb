# Structured JSON Audit Log — Design Spec

Date: 2026-07-24
Status: Approved by user (design review in chat)

## Problem

itkb has no unified audit trail. Queries, retrievals, auth events, and
mutations are scattered: `query_context` and `command_history` live in SQLite;
login attempts, ingest, and document deletes are not recorded anywhere
structured. The portfolio goal is a **structured JSON audit log of every
query/retrieval** (and, per the approved scope, auth and mutation events) —
append-only, human-readable, separate from the database.

## Goal

Every query, auth event, and mutation writes one JSON line to an append-only
`audit.jsonl` next to the KB database. Deniable only by deleting the file
(accepted for a single-user localhost tool).

## Non-Goals

- Tamper-evidence/hash-chaining (rejected by user — plain JSONL).
- PII redaction inside the audit log (the log is on the user's own disk; PII
  redaction is a separate ingestion-pipeline sub-project).
- Rotation/retention/compression of the audit file.
- Replacing the existing SQLite `query_context`/`command_history` tables.

## Architecture

### New module `itkb/audit.py`

```python
def audit_log_path(db_path: str) -> Path:
    # Path(db_path).parent / "audit.jsonl"

def log_event(db_path: str, event: str, **fields) -> None:
    # append one JSON line: {"event": ..., "ts": <utc iso>, **fields}
    # best-effort: swallow and ignore any exception (never breaks the caller)
```

- File opened in `"a"` mode per event; line is `json.dumps(...) + "\n"`.
- `ts` always `datetime.now(timezone.utc).isoformat()`.
- No locking beyond single-line atomic appends (O_APPEND semantics; a single
  writer per process, acceptable for this tool).

### Config

New field on `Config`:

```python
audit_enabled: bool = True
```

Persists through existing `load_config`/`save_config`. When `False`,
`log_event` is a no-op.

### Event catalog

All events: `{"event": <name>, "ts": <utc iso>, <fields>}`.

| Event | Fields | Hook |
|---|---|---|
| `query` | `query_id`, `question`, `chunk_ids` (list of int IDs), `source_count` | cli.py `kb query` path (next to `save_query_context` call) AND `api_query` after the stream completes |
| `auth.login` | `success` (bool) | `api_login` — success and failure |
| `ingest` | `source`, `kind` ("file" or "url") | `api_ingest` and the CLI ingest path |
| `document.delete` | `doc_id` | `api_delete_document` |
| `command` | `command`, `query_id`, `exit_code` | `tools.run_command` after execution (single chokepoint) — stdout/stderr intentionally NOT logged (may contain secrets) |

Note: `auth.login` logs `success` only — never the key, never a hash of it.

### Hook details

- **query (web)**: in `api_query`, the streaming generator `stream()` runs
  `run_agent` and knows the `query_id` (via `qid_holder`). Log the `query`
  event once — after the stream yields `[DONE]`, inside the generator — using
  `qid_holder[0]`. Collected chunk ids come from the `collected_chunks` param
  already passed to `run_agent`.
- **query (CLI)**: cli.py already calls `save_query_context(cfg.db_path,
  qid_holder[0], question, chunk_collector)` — add the `log_event` call
  adjacent to it.
- **command**: `tools.run_command` is the single chokepoint for command
  execution (both CLI and web go through it). It already has `db_path` and
  `query_id`. Log after `log_command` succeeds.

## Data flow

1. User asks a question (web or CLI).
2. Agent runs; on completion, `log_event` appends the `query` line with
   `query_id`, `question`, `chunk_ids`, `source_count`.
3. Every login (success or fail) appends `auth.login`.
4. Every ingest/delete/command appends its event line.
5. `audit.jsonl` lives in `Path(db_path).parent` (e.g. `~/.itkb/audit.jsonl`
   on the host, inside the `itkb-data` volume in Docker).

## Error handling

- `log_event` swallows all exceptions (file unwritable, JSON error, etc.) —
  best-effort, never breaks the query/command that triggered it. Local-first
  simplicity over durability guarantees.
- No retries, no buffering.

## Testing (pytest, TDD)

New file `tests/test_audit.py` (TestClient + temp config, reusing the
`authed_config`-style fixture pattern from `tests/test_auth.py`):

1. `test_log_event_appends_valid_jsonl` — one event → one valid JSON line with
   `event` + `ts`.
2. `test_log_event_append_order` — two events → two lines, order preserved.
3. `test_audit_path_is_next_to_db` — `audit_log_path(tmp_db)` returns
   `Path(tmp_db).parent / "audit.jsonl"`.
4. `test_disabled_audit_is_noop` — `audit_enabled=False` → no file created.
5. `test_web_query_logs_query_event` — authed TestClient POST `/api/query`
   (mock `run_agent` to yield tokens) → audit line with `event: "query"`,
   correct `query_id`/`question`.
6. `test_login_logs_auth_event` — successful login → `auth.login` success
   line; wrong key → `auth.login` failure line.
7. `test_ingest_logs_ingest_event` — POST `/api/ingest` (temp file) →
   `ingest` line.
8. `test_delete_logs_delete_event` — DELETE `/api/documents/{id}` →
   `document.delete` line.
9. `test_command_logs_command_event` — run `run_command` with a stub
   `confirm_fn` and a harmless command → `command` line with exit_code.

Health gates: `flake8 itkb tests`, `mypy itkb`, full `pytest`
(104 + ~9 new ≈ 113 passed).

## Docker compatibility

`audit.jsonl` lands in the `itkb-data` volume (same dir as kb.sqlite) — no
compose change needed; it persists across container restarts.

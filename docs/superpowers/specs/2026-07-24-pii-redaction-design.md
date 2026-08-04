# PII Redaction at Ingestion — Design Spec

Date: 2026-07-24
Status: Approved by user (design review in chat)

## Problem

itkb ingests files and URLs (via `parse_file`/`parse_url`) and stores the full
text as chunks. Any personal data in those sources — email addresses, phone
numbers, national IDs, credit-card numbers — is embedded verbatim in the
knowledge base and in the vector store, and can surface in query answers. The
portfolio goal (secure-rag spec) is a **PII-redaction pass during ingestion**.

## Goal

Every ingested document's text (and derived title) is scrubbed of true-PII
categories before chunking, gated by a `redact_pii` config toggle (default
on). Both the CLI (`kb add`) and the web API (`POST /api/ingest`) get the
redaction, since both funnel through `_ingest_file`/`_ingest_url`.

## Non-Goals

- Redacting IPs, hostnames, usernames, API keys, connection strings — these
  are legitimate IT runbook content; redacting them would destroy the KB's
  usefulness. Explicitly out of scope (user decision).
- Presidio / spaCy / ML-based NER (spec says "regex + presidio if you want to
  go further" — regex-first is the chosen scope; heavy deps avoided).
- Redacting the *query* or *answer* text — ingestion only.
- Retroactive redaction of already-stored chunks (user would re-ingest).

## Architecture

### New module `itkb/ingestion/redact.py`

```python
def redact_pii(text: str) -> str:
    # applies each category regex, replacing matches with type markers
```

Regex categories (applied in a fixed order) — true PII only:

| Category | Pattern | Marker |
|---|---|---|
| Email | `\b[\w.+-]+@[\w-]+\.[\w.]+\b` | `[EMAIL REDACTED]` |
| Phone | `(?<!\d)(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}(?!\d)` | `[PHONE REDACTED]` |
| National ID | `\b\d{3}-\d{2}-\d{4}\b` (SSN) and `\b\d{9}\b` (generic 9-digit) | `[NATIONAL_ID REDACTED]` |
| Credit card | `\b(?:\d[ -]?){13,19}\b` | `[CREDIT_CARD REDACTED]` |

Not redacted: IPs, hostnames, usernames, tokens, connection strings.

### Config

New field on `Config`:

```python
redact_pii: bool = True
```

Persists through existing `load_config`/`save_config`.

### Hook (`itkb/cli.py`)

In `_ingest_file` (after `text, title = parse_file(path)`) and `_ingest_url`
(after `text, title = parse_url(url)`):

```python
from itkb.ingestion.redact import redact_pii
if cfg.redact_pii:
    text = redact_pii(text)
    title = redact_pii(title)
```

Both functions are the single chokepoints for CLI and web ingest (verified:
`kb add`, `kb reindex`, `--watch`, and `POST /api/ingest` all call them). The
redaction happens BEFORE `chunk_text`, so nothing sensitive enters the chunks
or the vector store.

## Data flow

1. User ingests a file or URL (CLI or web).
2. `parse_file`/`parse_url` extracts raw text + title.
3. If `cfg.redact_pii` → `redact_pii(text)` and `redact_pii(title)`.
4. `chunk_text` chunks the scrubbed text.
5. Chunks + embeddings stored. PII never enters the KB.

## Error handling

- Regexes are applied with `re.sub` per category; no exceptions expected.
  Wrap defensively in the same style as `log_event`? No — a redaction failure
  should NOT silently ingest unredacted content. Decision: let it raise
  (fail-closed); the ingest `try/except` in `_ingest_file`/`_ingest_url`
  already catches and prints the error, so a redaction bug surfaces as a
  visible ingest failure rather than silently storing PII.
- Marker collisions: text that already contains `[EMAIL REDACTED]` is left as
  is (no re-scrub needed; harmless).

## Testing (pytest, TDD)

New file `tests/test_redact.py`:

1. `test_redacts_email` — `foo@bar.com` → `[EMAIL REDACTED]`
2. `test_redacts_phone` — `+1 (555) 123-4567` → `[PHONE REDACTED]`
3. `test_redacts_ssn` — `123-45-6789` → `[NATIONAL_ID REDACTED]`
4. `test_redacts_credit_card` — `4111 1111 1111 1111` → `[CREDIT_CARD REDACTED]`
5. `test_keeps_ip_addresses` — `192.168.1.10` intact
6. `test_keeps_hostnames_and_tokens` — `server01.example.com`, `sk-abc123...` intact
7. `test_keeps_version_numbers` — `1.2.3` intact (no false positive on the credit-card/digit regex)
8. `test_ingest_hook_applies_redaction` — `_ingest_file` on a temp file with an email → stored chunk has `[EMAIL REDACTED]`, no raw email
9. `test_ingest_hook_respects_toggle_off` — `redact_pii=False` → raw email preserved in chunk
10. `test_config_redact_pii_defaults_true` — config field default + roundtrip (in `tests/test_config.py`)

Health gates: `flake8 itkb tests`, `mypy itkb`, full `pytest`
(115 + ~10 new ≈ 125 passed).

## Docker compatibility

Redaction is app-level (inside `_ingest_file`/`_ingest_url`); no compose
change. `redact_pii` defaults on in the container too.

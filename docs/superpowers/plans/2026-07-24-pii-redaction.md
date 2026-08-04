# PII Redaction at Ingestion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Scrub true-PII (emails, phones, national IDs, credit cards) from every ingested document's text and title before chunking, gated by a `redact_pii` toggle (default on).

**Architecture:** New `itkb/ingestion/redact.py` (regex-based `redact_pii`), a new `redact_pii: bool = True` config field, and a hook in `_ingest_file`/`_ingest_url` (cli.py) applying redaction after parsing and before chunking — the single chokepoints for both CLI and web ingest.

**Tech Stack:** Python 3.11, stdlib `re`, pytest + pytest-mock.

**Reference spec:** `docs/superpowers/specs/2026-07-24-pii-redaction-design.md`

## Global Constraints

- True PII only: emails, phones, national IDs, credit cards. **Never** redact IPs, hostnames, usernames, tokens, connection strings.
- Type-specific markers: `[EMAIL REDACTED]`, `[PHONE REDACTED]`, `[NATIONAL_ID REDACTED]`, `[CREDIT_CARD REDACTED]`.
- Redaction is fail-closed: a redaction bug surfaces as a visible ingest error (the existing `try/except` in `_ingest_file`/`_ingest_url` prints it) — never silently ingest unredacted content.
- Applied to both text and title, before `chunk_text`.
- Health gates at the end: `flake8 itkb tests`, `mypy itkb` (via `/opt/homebrew/opt/python@3.11/bin/python3.11 -m mypy itkb`), `python3 -m pytest -q` (115 baseline + ~10 new ≈ 125 passed).
- Run pytest as `python3 -m pytest` from the repo root.

---

### Task 1: `itkb/ingestion/redact.py` module

**Files:**
- Create: `itkb/ingestion/redact.py`
- Test: `tests/test_redact.py`

**Interfaces:**
- Produces: `redact_pii(text: str) -> str` replacing true-PII matches with type markers.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_redact.py`:

```python
# tests/test_redact.py
from itkb.ingestion.redact import redact_pii


def test_redacts_email_direct():
    assert "mail: [EMAIL REDACTED]" in redact_pii("mail: foo@bar.com")


def test_redacts_email_not_present_when_absent():
    assert redact_pii("no personal data here") == "no personal data here"


def test_redacts_phone():
    assert "[PHONE REDACTED]" in redact_pii("call +1 (555) 123-4567 now")


def test_redacts_ssn():
    assert "[NATIONAL_ID REDACTED]" in redact_pii("ssn 123-45-6789")


def test_redacts_credit_card():
    assert "[CREDIT_CARD REDACTED]" in redact_pii("card 4111 1111 1111 1111")


def test_keeps_ip_addresses():
    text = "server at 192.168.1.10 and 10.0.0.1"
    assert redact_pii(text) == text


def test_keeps_hostnames_and_tokens():
    text = "ssh server01.example.com; token sk-abc123xyz456"
    assert redact_pii(text) == text


def test_keeps_version_numbers():
    text = "nginx version 1.2.3 and kernel 6.1.0"
    assert redact_pii(text) == text
```

Note: the email test asserts the replacement value is present, and the absence test asserts unchanged text when no PII exists — both are direct. The `test_redacts_email` placeholder-style first assertion was removed; the canonical email test is `test_redacts_email_direct`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_redact.py -v`
Expected: FAIL (ModuleNotFoundError: itkb.ingestion.redact)

- [ ] **Step 3: Create `itkb/ingestion/redact.py`**

```python
# itkb/ingestion/redact.py
from __future__ import annotations
import re

_RULES = [
    (re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b"), "[EMAIL REDACTED]"),
    (re.compile(r"\b(?:\d[ -]?){13,19}\b"), "[CREDIT_CARD REDACTED]"),
    (re.compile(r"(?<!\d)(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}(?!\d)"),
     "[PHONE REDACTED]"),
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[NATIONAL_ID REDACTED]"),
    (re.compile(r"\b\d{9}\b"), "[NATIONAL_ID REDACTED]"),
]


def redact_pii(text: str) -> str:
    for pattern, marker in _RULES:
        text = pattern.sub(marker, text)
    return text
```

Ordering note: credit-card runs BEFORE phone — a 16-digit card (with separators) would otherwise be partially eaten by the 3-3-4 phone pattern. SSN (`123-45-6789`, 11 chars) is too short for the 13-19 char card regex, so it survives to its own rule.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_redact.py -v`
Expected: all pass (adjust the email test per Step 1 note; run the actual file)

- [ ] **Step 5: Commit**

```bash
git add itkb/ingestion/redact.py tests/test_redact.py
git commit -m "feat: regex PII redaction module (emails, phones, IDs, cards)"
```

---

### Task 2: `redact_pii` config field

**Files:**
- Modify: `itkb/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_config.py`:

```python
def test_redact_pii_defaults_true(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    import itkb.config as cfg_mod
    cfg_mod.CONFIG_DIR = tmp_path / ".itkb"
    cfg_mod.CONFIG_FILE = cfg_mod.CONFIG_DIR / "config.toml"

    assert Config().redact_pii is True
    save_config(Config(redact_pii=False))
    assert load_config().redact_pii is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_config.py::test_redact_pii_defaults_true -v`
Expected: FAIL (TypeError unexpected keyword 'redact_pii')

- [ ] **Step 3: Add the field**

In `itkb/config.py`, change:

```python
    api_key: str = ""
    session_secret: str = ""
    audit_enabled: bool = True
```

to:

```python
    api_key: str = ""
    session_secret: str = ""
    audit_enabled: bool = True
    redact_pii: bool = True
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_config.py -v`
Expected: 9 passed (8 existing + 1 new)

- [ ] **Step 5: Commit**

```bash
git add itkb/config.py tests/test_config.py
git commit -m "feat: redact_pii config toggle (default on)"
```

---

### Task 3: Hook into `_ingest_file` and `_ingest_url`

**Files:**
- Modify: `itkb/cli.py`
- Test: `tests/test_redact.py`

**Interfaces:**
- Produces: when `cfg.redact_pii` is true, `_ingest_file`/`_ingest_url` scrub text + title before chunking.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_redact.py`:

```python
def test_ingest_hook_applies_redaction(tmp_path, monkeypatch):
    import pathlib
    import uuid
    import itkb.config as cfg_mod

    monkeypatch.setenv("ITKB_SILENT", "1")
    monkeypatch.setenv("HOME", str(tmp_path))
    cfg_mod.CONFIG_DIR = tmp_path / ".itkb"
    cfg_mod.CONFIG_FILE = cfg_mod.CONFIG_DIR / "config.toml"
    cfg_mod.save_config(cfg_mod.Config(
        redact_pii=True, db_path=str(tmp_path / "kb.sqlite"),
        audit_enabled=False,
    ))
    from itkb.store.db import init_db, doc_id
    init_db(str(tmp_path / "kb.sqlite"))

    src = pathlib.Path("/tmp") / f"itkb-redact-{uuid.uuid4().hex}.md"
    src.write_text("# Note\n\nreach me at foo@bar.com or 123-45-6789\n")

    from itkb.cli import _ingest_file
    cfg = cfg_mod.load_config()
    try:
        _ingest_file(src, cfg)
    finally:
        src.unlink(missing_ok=True)

    # Read chunks back with the same direct-SQL pattern as tests/test_ingest.py:29.
    from itkb.store.db import _connect
    conn = _connect(str(tmp_path / "kb.sqlite"))
    rows = conn.execute(
        "SELECT content FROM chunks WHERE doc_id = ?", (doc_id(str(src)),)
    ).fetchall()
    conn.close()
    text = " ".join(r[0] for r in rows)
    assert "foo@bar.com" not in text
    assert "123-45-6789" not in text
    assert "[EMAIL REDACTED]" in text or "[NATIONAL_ID REDACTED]" in text


def test_ingest_hook_respects_toggle_off(tmp_path, monkeypatch):
    import pathlib
    import uuid
    import itkb.config as cfg_mod

    monkeypatch.setenv("ITKB_SILENT", "1")
    monkeypatch.setenv("HOME", str(tmp_path))
    cfg_mod.CONFIG_DIR = tmp_path / ".itkb"
    cfg_mod.CONFIG_FILE = cfg_mod.CONFIG_DIR / "config.toml"
    cfg_mod.save_config(cfg_mod.Config(
        redact_pii=False, db_path=str(tmp_path / "kb.sqlite"),
        audit_enabled=False,
    ))
    from itkb.store.db import init_db, doc_id, _connect
    init_db(str(tmp_path / "kb.sqlite"))

    src = pathlib.Path("/tmp") / f"itkb-noredact-{uuid.uuid4().hex}.md"
    src.write_text("# Note\n\nreach me at foo@bar.com\n")

    from itkb.cli import _ingest_file
    cfg = cfg_mod.load_config()
    try:
        _ingest_file(src, cfg)
    finally:
        src.unlink(missing_ok=True)

    conn = _connect(str(tmp_path / "kb.sqlite"))
    rows = conn.execute(
        "SELECT content FROM chunks WHERE doc_id = ?", (doc_id(str(src)),)
    ).fetchall()
    conn.close()
    text = " ".join(r[0] for r in rows)
    assert "foo@bar.com" in text
```

Verify that `_connect` is importable from `itkb.store.db` (it is — `db.py` uses it internally; check `def _connect` exists and is not underscore-prefixed-hidden). If `_connect` is private, use `sqlite3.connect(str(tmp_path / "kb.sqlite"))` directly (the DB file is plain SQLite) — either approach is fine; follow what `tests/test_ingest.py` does.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_redact.py -v`
Expected: the two hook tests FAIL (no redaction applied in _ingest_file — raw email present in chunks)

- [ ] **Step 3: Add the hook in `itkb/cli.py`**

In `_ingest_file`, change:

```python
        text, title = parse_file(path)
        raw_chunks = chunk_text(text, str(path))
```

to:

```python
        text, title = parse_file(path)
        if cfg.redact_pii:
            from itkb.ingestion.redact import redact_pii
            text = redact_pii(text)
            title = redact_pii(title)
        raw_chunks = chunk_text(text, str(path))
```

In `_ingest_url`, change:

```python
        text, title = parse_url(url)
        raw_chunks = chunk_text(text, url)
```

to:

```python
        text, title = parse_url(url)
        if cfg.redact_pii:
            from itkb.ingestion.redact import redact_pii
            text = redact_pii(text)
            title = redact_pii(title)
        raw_chunks = chunk_text(text, url)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_redact.py -v`
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add itkb/cli.py tests/test_redact.py
git commit -m "feat: apply PII redaction in ingest path (file + url)"
```

---

### Task 4: Final verification

**Files:** none (verification only)

- [ ] **Step 1: Health stack**

Run:
```bash
flake8 itkb tests
/opt/homebrew/opt/python@3.11/bin/python3.11 -m mypy itkb
python3 -m pytest -q
```
Expected: flake8 no output; mypy `Success: no issues found`; `125 passed` (115 baseline + 10 new: 1 config + 9 redact)

- [ ] **Step 2: Manual smoke**

Run: `python3 -c "
from itkb.ingestion.redact import redact_pii
print(redact_pii('Email foo@bar.com, phone +1 (555) 123-4567, ssn 123-45-6789, card 4111 1111 1111 1111, ip 192.168.1.10, host server01.example.com'))
"` (run from repo root)
Expected: emails/phones/ssn/card replaced with markers; ip + hostname intact

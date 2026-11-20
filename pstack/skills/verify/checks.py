#!/usr/bin/env python3
"""Deterministic behavior checks for it-kb.

Run via verify.sh, which sets ITKB_REPO and PYTHONPATH. Exercises only the
stdlib-importable modules (redact, program) plus an optional guarded auth
round-trip. No Ollama, no FastAPI, no DB required.

Exit code: 0 = all checks passed, 1 = at least one FAIL, 2 = bad invocation.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path


def _repo() -> Path:
    repo = os.environ.get("ITKB_REPO") or os.getcwd()
    p = Path(repo).expanduser()
    if not (p / "pyproject.toml").exists():
        print(f"FAIL: {p} does not look like an it-kb checkout", file=sys.stderr)
        sys.exit(2)
    return p


REPO = _repo()
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from itkb.ingestion.redact import redact_pii  # noqa: E402
from itkb.program import (  # noqa: E402
    commands_enabled,
    ingest_path_allowed,
    ingest_url_allowed,
)

RESULTS = []
SKIPPED = []


def check(name, fn):
    try:
        fn()
        RESULTS.append((name, True, ""))
        print(f"PASS  {name}")
    except AssertionError as e:
        RESULTS.append((name, False, str(e) or "assertion failed"))
        print(f"FAIL  {name}: {e}")
    except Exception as e:  # noqa: BLE001
        RESULTS.append((name, False, f"{type(e).__name__}: {e}"))
        print(f"FAIL  {name}: {type(e).__name__}: {e}")


def write_program(text: str) -> str:
    f = tempfile.NamedTemporaryFile("w", suffix=".md", delete=False)
    f.write(text)
    f.close()
    os.environ["ITKB_PROGRAM_PATH"] = f.name
    return f.name


# ── PII redaction ─────────────────────────────────────────────────────
def _pii_redacted():
    assert "[EMAIL REDACTED]" in redact_pii("mail alice@example.com now")
    assert "[CREDIT_CARD REDACTED]" in redact_pii("card 4242 4242 4242 4242 ok")
    assert "[PHONE REDACTED]" in redact_pii("call 555-123-4567 now")
    assert "[NATIONAL_ID REDACTED]" in redact_pii("ssn 123-45-6789 now")


def _pii_leaves_it_content():
    # IPs, hostnames, tokens, bare numeric IDs, and non-Luhn digit runs survive.
    text = "host 10.0.0.1 port 22 token abc123 id 1111111111111111 epoch 1720000000"
    assert redact_pii(text) == text, redact_pii(text)


# ── PROGRAM.md governance (denied-by-default) ─────────────────────────
def _commands_default_off():
    write_program("# PROGRAM.md\n")
    assert commands_enabled() is False


def _commands_explicit_on():
    write_program("## Command Execution\n```yaml\ncommands_enabled: true\n```\n")
    assert commands_enabled() is True


def _path_whitelist_blocks_escape():
    root = Path(tempfile.mkdtemp(prefix="itkb_verify_"))
    wl = root / "whitelist"
    wl.mkdir()
    write_program("## Path Whitelist\n```yaml\n- %s\n```\n" % wl)
    assert ingest_path_allowed(str(wl / "notes.md")) is True
    assert ingest_path_allowed(str(wl / ".." / "secret.md")) is False


def _url_whitelist_prefix():
    write_program("## URL Whitelist\n```yaml\n- https://wiki.\n- https://docs.\n```\n")
    assert ingest_url_allowed("https://wiki.example.com/x") is True
    assert ingest_url_allowed("https://evil.com/x") is False


# ── Session auth (guarded: needs fastapi) ─────────────────────────────
def _auth_roundtrip():
    try:
        from itkb.api.auth import make_session_token, verify_session_token
    except ImportError:
        SKIPPED.append("auth round-trip (fastapi not installed)")
        print("SKIP  auth round-trip (fastapi not installed)")
        return
    secret, key = "s3cret", "k3y"
    tok = make_session_token(key, secret)
    assert verify_session_token(tok, key, secret) is True
    assert verify_session_token(tok + "x", key, secret) is False
    assert verify_session_token(tok, "wrong", secret) is False


# ── Governance: PROGRAM.md actually drives config (the regression this
#    whole fix exists to prevent) ───────────────────────────────────────
def _program_drives_config():
    try:
        import itkb.config as cfg_mod
        from itkb.config import Config, load_config, save_config
    except ImportError:
        SKIPPED.append("program drives config (tomli/tomli_w not installed)")
        print("SKIP  program drives config (tomli/tomli_w not installed)")
        return
    home = tempfile.mkdtemp(prefix="itkb_home_")
    cfg_mod.CONFIG_DIR = Path(home) / ".itkb"
    cfg_mod.CONFIG_FILE = cfg_mod.CONFIG_DIR / "config.toml"
    save_config(Config(model="toml-model", top_k=3))
    prog = Path(home) / "PROGRAM.md"
    prog.write_text(
        "## 1. Models\n```yaml\nchat: program-model       # LLM for ReAct agent loop\n"
        "embed: program-embed     # embedding model\n```\n"
        "## 5. Query Behavior\n```yaml\ntop_k: 9                  # chunks per search\n"
        "max_iterations: 7        # loop budget\ntrusted: true             # no prompt\n```\n"
    )
    os.environ["ITKB_PROGRAM_PATH"] = str(prog)
    cfg = load_config()
    assert cfg.model == "program-model"
    assert cfg.embed_model == "program-embed"
    assert cfg.top_k == 9
    assert cfg.max_iterations == 7
    assert cfg.trusted is True


check("pii: email/card/phone/ssn redacted", _pii_redacted)
check("pii: ips, hostnames, tokens, non-luhn numbers survive", _pii_leaves_it_content)
check("program: commands default OFF", _commands_default_off)
check("program: commands_enabled=true honored", _commands_explicit_on)
check("program: path whitelist blocks ../ escape", _path_whitelist_blocks_escape)
check("program: url whitelist prefix match", _url_whitelist_prefix)
check("auth: session token round-trip + tamper reject", _auth_roundtrip)
check("config: PROGRAM.md drives model/embed/top_k/iterations/trusted", _program_drives_config)

fails = [r for r in RESULTS if not r[1]]
print(f"\n{len(RESULTS) - len(fails)} passed, {len(fails)} failed"
      + (f", {len(SKIPPED)} skipped" if SKIPPED else ""))
sys.exit(1 if fails else 0)

#!/usr/bin/env python3
"""Static security gate for it-kb.

Encodes the rules that "make the mistake impossible" at the highest rung of the
trust ladder: fail the build when a safe default is weakened or a secret is
committed. This is the `/correct` step turned into a CI gate — a repeated
correction becomes structure instead of more text.

Checks:
  1. denied-by-default  — committed PROGRAM.md must not set `commands_enabled`
                          or `trusted` to true.
  2. safe code defaults — itkb/config.py must keep `trusted=False`,
                          `redact_pii=True`, `audit_enabled=True`.
  3. no committed secrets — no private keys or non-empty secret literals under
                          itkb/ or in root deploy files.

Exit 0 = pass, 1 = fail. Stdlib only. No Ollama, no deps, no DB.

Run it directly, or via CI:
    python pstack/ci/security-gate.py            # defaults to the repo root
    ITKB_REPO=/path/to/itkb python .../security-gate.py
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

ROOT = Path(os.environ.get("ITKB_REPO") or Path(__file__).resolve().parents[2])

# Directories that are tooling or fixtures, not product code.
SKIP_DIRS = {".git", "tests", "samples", "docs", "pstack"}
# Root deploy files worth scanning alongside itkb/.
ROOT_FILES = ["docker-compose.yml", "Dockerfile", "PROGRAM.md"]

PRIVATE_KEY = re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY")
# name = "literal" / name: "literal" where the value is a long, non-placeholder string.
SECRET_ASSIGN = re.compile(
    r"(?i)\b(api_?key|secret|password|passwd|token|access_?key)\b\s*[:=]\s*[\"']([^\"']{12,})[\"']"
)
PLACEHOLDERS = ("example", "changeme", "your-", "your_", "<", "redacted", "placeholder", "xxx")

FAILURES = []


def fail(msg: str) -> None:
    FAILURES.append(msg)
    print(f"FAIL  {msg}")


def ok(msg: str) -> None:
    print(f"PASS  {msg}")


def _repo_files() -> list[Path]:
    if not (ROOT / "pyproject.toml").exists():
        fail(f"not an it-kb checkout: {ROOT} (no pyproject.toml)")
        return []
    files: list[Path] = [ROOT / f for f in ROOT_FILES if (ROOT / f).exists()]
    itkb = ROOT / "itkb"
    if itkb.is_dir():
        files += [p for p in itkb.rglob("*") if p.is_file()]
    return files


def check_denied_by_default() -> None:
    p = ROOT / "PROGRAM.md"
    if not p.exists():
        fail("PROGRAM.md missing — cannot verify denied-by-default")
        return
    text = p.read_text(errors="replace")
    bad = [k for k in ("commands_enabled: true", "trusted: true") if k in text]
    for knob in bad:
        fail(f"PROGRAM.md sets {knob!r} — denied-by-default weakened")
    if not bad:
        ok("denied-by-default: PROGRAM.md keeps commands/trusted off")


def check_safe_defaults() -> None:
    p = ROOT / "itkb" / "config.py"
    if not p.exists():
        fail("itkb/config.py missing")
        return
    text = p.read_text(errors="replace")
    bad = [
        s for s in (
            "trusted: bool = False",
            "redact_pii: bool = True",
            "audit_enabled: bool = True",
        ) if s not in text
    ]
    for snippet in bad:
        fail(f"itkb/config.py lost safe default: {snippet!r}")
    if not bad:
        ok("safe defaults: trusted=False, redact_pii=True, audit_enabled=True")


def check_no_secrets() -> None:
    found = False
    for p in _repo_files():
        rel = p.relative_to(ROOT)
        text = p.read_text(errors="replace")
        if PRIVATE_KEY.search(text):
            found = True
            fail(f"{rel}: private key material committed")
        for m in SECRET_ASSIGN.finditer(text):
            name, val = m.group(1), m.group(2)
            if any(ph in val.lower() for ph in PLACEHOLDERS):
                continue
            found = True
            fail(f"{rel}: hardcoded secret '{name}'")
    if not found:
        ok("no secrets: no private keys or non-empty secret literals")


if __name__ == "__main__":
    if _repo_files() or (ROOT / "pyproject.toml").exists():
        check_denied_by_default()
        check_safe_defaults()
        check_no_secrets()
    fails = len(FAILURES)
    print(f"\n{3 - fails} passed, {fails} failed")
    sys.exit(1 if fails else 0)

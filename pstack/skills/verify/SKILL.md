---
name: verify
description: Deterministic proof that it-kb behaves as specified. Run ./verify.sh against a checkout; it checks PII redaction, PROGRAM.md governance, session auth, and the test suite — no Ollama or DB required. Use before declaring any change "done".
disable-model-invocation: true
---

# Verify it-kb

`it-kb` cannot be judged by "it compiles." It has to be *proven*: retrieval is
correct, PII is actually redacted, and "denied-by-default" actually denies.

This skill is that proof. It is a **deterministic CLI** that re-runs the same checks
every session — not a fresh ad-hoc script per task. Reusing the same tool is what makes
an agent's "done" trustworthy.

## Run it

```bash
# from this directory
./verify.sh --repo <path-to-it-kb-checkout>

# or via env var
ITKB_REPO=<path-to-it-kb-checkout> ./verify.sh
```

Requirements: Python 3 (stdlib only for the behavior checks) and the `itkb` package.
No Ollama, no FastAPI, no SQLite, no network. `pytest` is used if present, skipped
otherwise.

## What it proves

| Check | Against | Why it matters |
|---|---|---|
| email/card/phone/SSN → `[X REDACTED]` markers | `itkb/ingestion/redact.py` | the PII promise |
| IPs/hostnames/tokens/non-Luhn numbers survive | `itkb/ingestion/redact.py` | not over-redacting legitimate runbook content |
| `commands_enabled` defaults OFF | `itkb/program.py` | the denied-by-default control plane |
| path whitelist blocks `../` escape | `itkb/program.py` | path traversal does not escape the sandbox |
| URL whitelist matches by prefix | `itkb/program.py` | only approved sources scrape |
| session token round-trip + tamper reject | `itkb/api/auth.py` | the session cookie can't leak the API key |
| full test suite green | `pytest` | the 132 unit tests |

## When to run it

- After every bug fix or feature, before "done" (see the mode playbooks).
- Before opening a PR.
- When a bug report arrives and you need to know *what surface* is involved — read
  `feature-map.md` first, then verify the current behavior.

## Extending it (Encode Lessons in Structure)

The second time you correct an agent for the same mistake, add a check to `checks.py`.
A check is a few lines; a repeated correction is forever.

## The map

`feature-map.md` is the sitemap of what a feature *is*, how to reach it, and the proof
that it works. Read it before touching anything you don't already understand.

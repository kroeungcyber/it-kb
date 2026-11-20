#!/usr/bin/env bash
# verify.sh — deterministic behavior checks for it-kb.
# The CLI that agents re-run instead of writing a fresh script each session.
#
# Usage:
#   ./verify.sh --repo ~/itkb
#   ITKB_REPO=~/itkb ./verify.sh
#
# Exit code: 0 = PASS, 1 = FAIL, 2 = usage/not-a-checkout.
set -u

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
REPO="${ITKB_REPO:-}"

while [ $# -gt 0 ]; do
  case "$1" in
    --repo) REPO="$2"; shift 2 ;;
    --repo=*) REPO="${1#--repo=}"; shift ;;
    *) echo "error: unknown arg '$1'"; exit 2 ;;
  esac
done

if [ -z "$REPO" ]; then
  echo "error: no it-kb checkout. pass --repo <path> or set ITKB_REPO."
  exit 2
fi

_orig="$REPO"
REPO=$(cd "$REPO" 2>/dev/null && pwd) || { echo "error: '$_orig' not found"; exit 2; }
if [ ! -f "$REPO/pyproject.toml" ]; then
  echo "error: $REPO does not look like an it-kb checkout (no pyproject.toml)."
  exit 2
fi

echo "== it-kb verification =="
echo "repo: $REPO"
echo

echo "== behavior checks =="
ITKB_REPO="$REPO" PYTHONPATH="$REPO" python3 "$SCRIPT_DIR/checks.py"
PY_RC=$?
echo

echo "== unit tests =="
if command -v pytest >/dev/null 2>&1; then
  ( cd "$REPO" && pytest -q )
  TEST_RC=$?
else
  echo "skipped (pytest not installed)"
  TEST_RC=0
fi
echo

if [ "$PY_RC" -ne 0 ] || [ "$TEST_RC" -ne 0 ]; then
  echo "RESULT: FAIL"
  exit 1
fi
echo "RESULT: PASS"

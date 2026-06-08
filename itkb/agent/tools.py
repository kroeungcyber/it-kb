# itkb/agent/tools.py
from __future__ import annotations
import shlex
import subprocess
from datetime import datetime, timezone
from typing import Callable, Optional
import ollama

from itkb.store.db import search_chunks, log_command

BLOCKED_PATTERNS = ["rm -rf", "dd if=", "mkfs", "shutdown", "reboot", ":(){:|:&};:"]

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "search_kb",
            "description": "Search the IT knowledge base for relevant information",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "top_k": {"type": "integer", "description": "Number of results to return", "default": 5},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "Propose a shell command. Requires user confirmation before execution.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "The shell command to run"},
                },
                "required": ["command"],
            },
        },
    },
]


def search_kb(query_embedding: list[float], db_path: str, top_k: int) -> list[dict]:
    results = search_chunks(db_path, query_embedding, top_k)
    return [
        {
            "content": chunk.content,
            "source": chunk.doc_id,
            "metadata": chunk.metadata,
            "distance": dist,
        }
        for chunk, dist in results
    ]


def cite_sources(chunks: list[dict]) -> str:
    seen: dict[str, str] = {}
    for c in chunks:
        sid = c["source"]
        if sid not in seen:
            seen[sid] = c.get("metadata", {}).get("source_path", sid)
    return "\n".join(f"- [{sid}] {path}" for sid, path in seen.items())


def suggest_followups(answer: str, model: str) -> list[str]:
    resp = ollama.chat(
        model=model,
        messages=[
            {
                "role": "system",
                "content": (
                    "Generate exactly 3 short follow-up questions based on this IT support answer. "
                    "Return only the questions, one per line, no numbering or bullets."
                ),
            },
            {"role": "user", "content": answer},
        ],
    )
    lines = [ln.strip() for ln in resp["message"]["content"].strip().split("\n") if ln.strip()]
    return lines[:3]


def run_command(
    command: str,
    confirm_fn: Callable[[str], bool],
    db_path: str,
    query_id: str,
    timeout: int = 30,
) -> str:
    from itkb.program import commands_enabled

    if not commands_enabled():
        return "[Commands are disabled in PROGRAM.md. Set commands_enabled: true to enable.]"

    _assert_not_blocked(command)

    if not confirm_fn(command):
        return "[Command skipped by user]"

    result = subprocess.run(
        shlex.split(command),
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    output = (result.stdout + result.stderr).strip()

    log_command(
        db_path, command, output, result.returncode,
        datetime.now(timezone.utc).isoformat(), query_id
    )
    return output or f"[exit code {result.returncode}]"


def _assert_not_blocked(command: str) -> None:
    for pattern in BLOCKED_PATTERNS:
        if pattern in command:
            raise ValueError(f"Command blocked for safety: contains '{pattern}'")

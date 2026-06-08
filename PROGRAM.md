# PROGRAM.md — itkb Central Control File

> **Every operation below requires your explicit approval.**
> This file is the single source of truth for itkb's behavior.
> Edit it directly and the agent enforces it on the next query.

---

## 1. Models

```yaml
chat: gemma4:latest            # LLM for ReAct agent loop
embed: embeddinggemma:latest    # embedding model for vector search
```

## 2. Path Whitelist — Ingest

> Only files under these directories can be ingested.
> Any path outside this list is rejected.

```yaml
ingest_paths:
  - /Users/bila/notes/
  - /Users/bila/itkb/
  - /tmp/
```

## 3. URL Whitelist — Ingest

> Only URLs matching these prefixes can be scraped.

```yaml
ingest_urls:
  - https://wiki.
  - https://docs.
  - https://man.
```

## 4. Command Execution

> **OFF by default.** Set to `true` only after reviewing what the agent
> can run. Even when ON, dangerous patterns are always blocked.

```yaml
commands_enabled: false
```

**Always blocked (cannot be overridden):**
- `rm -rf`, `dd if=`, `mkfs`, `shutdown`, `reboot`, fork bombs

**When commands_enabled is `true`:**
- The agent PROPOSES a command before running it
- You must type `y` to approve each command
- All commands and output logged to `~/.itkb/kb.sqlite` → `command_history`

## 5. Query Behavior

```yaml
top_k: 5                        # max chunks returned per search
max_iterations: 5               # max ReAct loop iterations
trusted: false                  # if true, commands run without prompt
```

## 6. Web UI

```yaml
host: 127.0.0.1                 # local only
port: 8000
```

## 7. Database

```yaml
path: ~/.itkb/kb.sqlite         # single-file, fully local
```

---

## Change Log

Edit below when you approve changes:

| Date | What | Approved |
|------|------|----------|
| 2026-06-08 | Initial setup | ✓ |

# Docker Packaging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `docker compose up` runs the itkb web UI on any machine — default profile uses the host's Ollama (GPU on this Mac), `--profile bundled` adds a self-contained Ollama + small models, `--profile demo-data` pre-loads a sample corpus.

**Architecture:** One `Dockerfile` (python:3.11-slim, `pip install .`), one `docker-compose.yml` (YAML anchor shares the api definition between the default `api` service and the profile-gated `api-demo`), plus three small code changes (`--host` flag, env config overrides, `ITKB_PROGRAM_PATH`), a `samples/` corpus, and a README section.

**Tech Stack:** Docker / Docker Compose profiles, python:3.11-slim, ollama/ollama image, FastAPI + uvicorn, typer CLI, pytest + pytest-mock + typer's CliRunner.

**Reference spec:** `docs/superpowers/specs/2026-07-24-docker-packaging-design.md`

## Global Constraints

- Default `kb serve` behavior unchanged: binds `127.0.0.1` unless `--host` is passed.
- Local (non-container) behavior unchanged when no `ITKB_*` env vars are set.
- Config precedence: env vars > `config.toml` (which PROGRAM.md syncs). Document this in the README section.
- No changes to retrieval, agent, or web UI logic.
- Health gates at the end: `flake8 itkb tests`, `mypy itkb` (via `/opt/homebrew/opt/python@3.11/bin/python3.11 -m mypy itkb` if `mypy` isn't on PATH), `python3 -m pytest -q` (81 baseline + 4 new = 85 passed).
- Run pytest as `python3 -m pytest` from the repo root (editable-install gotcha: bare `pytest` may import the wrong package copy — here main repo IS the editable target, but keep the habit).

---

### Task 1: Add `--host` option to `kb serve`

**Files:**
- Modify: `itkb/cli.py:268-275` (the `serve` command)
- Create: `tests/test_cli.py`

**Interfaces:**
- Produces: `kb serve [--port N] [--host X]`; default host stays `127.0.0.1`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_cli.py`:

```python
# tests/test_cli.py
from typer.testing import CliRunner
from itkb.cli import app

runner = CliRunner()


def test_serve_default_host(mocker):
    mock_run = mocker.patch("uvicorn.run")
    result = runner.invoke(app, ["serve"])
    assert result.exit_code == 0
    assert mock_run.call_args.kwargs["host"] == "127.0.0.1"


def test_serve_host_flag(mocker):
    mock_run = mocker.patch("uvicorn.run")
    result = runner.invoke(app, ["serve", "--host", "0.0.0.0"])
    assert result.exit_code == 0
    assert mock_run.call_args.kwargs["host"] == "0.0.0.0"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_cli.py -v`
Expected: both FAIL with non-zero exit code — typer rejects the unknown `--host` option, so the `host` kwarg assertion can't pass

- [ ] **Step 3: Add the option**

In `itkb/cli.py`, change:

```python
def serve(port: int = typer.Option(8000, "--port", help="Port to listen on")):
    """Start the web UI server."""
    import uvicorn
    from itkb.api.app import app as fastapi_app

    console.print(f"[green]Starting web UI at http://localhost:{port}[/green]")
    uvicorn.run(fastapi_app, host="127.0.0.1", port=port)
```

to:

```python
def serve(port: int = typer.Option(8000, "--port", help="Port to listen on"),
          host: str = typer.Option("127.0.0.1", "--host", help="Host/interface to bind")):
    """Start the web UI server."""
    import uvicorn
    from itkb.api.app import app as fastapi_app

    console.print(f"[green]Starting web UI at http://{host}:{port}[/green]")
    uvicorn.run(fastapi_app, host=host, port=port)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_cli.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add itkb/cli.py tests/test_cli.py
git commit -m "feat: add --host option to kb serve"
```

---

### Task 2: Env-var overrides for model config

**Files:**
- Modify: `itkb/config.py` (imports + `load_config`)
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: `ITKB_MODEL` → `cfg.model`, `ITKB_EMBED_MODEL` → `cfg.embed_model`; env wins over the TOML value; unset env → TOML value (local behavior unchanged).

- [ ] **Step 1: Write the failing test**

Append to `tests/test_config.py`:

```python
def test_env_overrides_model_and_embed(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    import itkb.config as cfg_mod
    cfg_mod.CONFIG_DIR = tmp_path / ".itkb"
    cfg_mod.CONFIG_FILE = cfg_mod.CONFIG_DIR / "config.toml"

    save_config(Config(model="toml-model", embed_model="toml-embed"))
    monkeypatch.setenv("ITKB_MODEL", "env-model")
    monkeypatch.setenv("ITKB_EMBED_MODEL", "env-embed")
    loaded = load_config()
    assert loaded.model == "env-model"
    assert loaded.embed_model == "env-embed"

    monkeypatch.delenv("ITKB_MODEL")
    monkeypatch.delenv("ITKB_EMBED_MODEL")
    loaded = load_config()
    assert loaded.model == "toml-model"
    assert loaded.embed_model == "toml-embed"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_config.py::test_env_overrides_model_and_embed -v`
Expected: FAIL with `AssertionError: assert 'toml-model' == 'env-model'`

- [ ] **Step 3: Implement the override**

In `itkb/config.py`, add `import os` at the top (after `from __future__ import annotations`), and change:

```python
    valid_keys = {f.name for f in fields(Config)}
    return Config(**{k: v for k, v in data.items() if k in valid_keys})
```

to:

```python
    valid_keys = {f.name for f in fields(Config)}
    cfg = Config(**{k: v for k, v in data.items() if k in valid_keys})
    if os.environ.get("ITKB_MODEL"):
        cfg.model = os.environ["ITKB_MODEL"]
    if os.environ.get("ITKB_EMBED_MODEL"):
        cfg.embed_model = os.environ["ITKB_EMBED_MODEL"]
    return cfg
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_config.py -v`
Expected: 4 passed (3 existing + 1 new)

- [ ] **Step 5: Commit**

```bash
git add itkb/config.py tests/test_config.py
git commit -m "feat: ITKB_MODEL/ITKB_EMBED_MODEL env overrides in load_config"
```

---

### Task 3: `ITKB_PROGRAM_PATH` env override in program.py

**Files:**
- Modify: `itkb/program.py` (imports + `_read_program`)
- Test: `tests/test_program.py`

**Interfaces:**
- Produces: when `ITKB_PROGRAM_PATH` is set, all `program.py` readers use that file; unset → current `Path(__file__).parent.parent / "PROGRAM.md"` (fixes the broken lookup under non-editable pip installs, e.g. the container).

- [ ] **Step 1: Write the failing test**

First check the existing imports/style at the top of `tests/test_program.py` and follow them. Append:

```python
def test_program_path_env_override(tmp_path, monkeypatch):
    custom = tmp_path / "CUSTOM_PROGRAM.md"
    custom.write_text(
        "## 5. Command Execution\n\n```yaml\ncommands_enabled: true\n```\n"
    )
    monkeypatch.setenv("ITKB_PROGRAM_PATH", str(custom))
    from itkb.program import commands_enabled
    assert commands_enabled() is True
```

(Note: `commands_enabled` reads `"Command Execution"` and defaults false — so this proves the env-pointed file, not the repo PROGRAM.md, is being read, since the repo file has commands OFF.)

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_program.py -v`
Expected: the new test FAILS (`assert False is True`)

- [ ] **Step 3: Implement the override**

In `itkb/program.py`, change the imports:

```python
from __future__ import annotations
import re
from pathlib import Path
```

to:

```python
from __future__ import annotations
import os
import re
from pathlib import Path
```

and change `_read_program`:

```python
def _read_program() -> str:
    return PROGRAM_PATH.read_text()
```

to:

```python
def _read_program() -> str:
    path = Path(os.environ.get("ITKB_PROGRAM_PATH", PROGRAM_PATH))
    return path.read_text()
```

(`PROGRAM_PATH` stays as the default constant; env is read at call time so tests can use `monkeypatch.setenv` without reloading the module.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_program.py -v`
Expected: all pass (existing + 1 new)

- [ ] **Step 5: Commit**

```bash
git add itkb/program.py tests/test_program.py
git commit -m "feat: ITKB_PROGRAM_PATH env override for PROGRAM.md lookup"
```

---

### Task 4: Sample corpus + whitelist entry

**Files:**
- Create: `samples/nginx-restart.md`, `samples/docker-debug.md`, `samples/ssh-config.md`
- Modify: `PROGRAM.md` (ingest path whitelist)

- [ ] **Step 1: Create the three runbooks**

`samples/nginx-restart.md`:

```markdown
# Nginx Restart Runbook

## When to restart vs reload

Use `reload` for config changes (zero downtime). Use `restart` only when
reload fails or a binary/module change requires it.

## Standard procedure

1. Validate config first: `sudo nginx -t`
2. Reload gracefully: `sudo systemctl reload nginx`
3. If reload fails, check the error: `journalctl -u nginx -n 50`
4. Full restart as last resort: `sudo systemctl restart nginx`

## Common pitfalls

- Skipping `nginx -t` and taking the site down with a syntax error.
- Port conflicts: check with `ss -tlnp | grep nginx`.
- Stale PID file after an unclean stop: remove `/run/nginx.pid` and retry.

## Verification

- `curl -I http://localhost` returns 200.
- `systemctl status nginx` shows active (running).
```

`samples/docker-debug.md`:

```markdown
# Docker Container Debugging

## Container won't start

1. Check logs: `docker logs <container>`
2. Inspect exit code: `docker ps -a` — 0 means clean exit, non-zero is an app error.
3. Check config: `docker inspect <container>`

## Container starts then dies

- Usually the main process exits. Run interactively to see output:
  `docker run -it --rm <image> /bin/sh`
- Check OOM kills: `docker inspect <container> | grep -i oom`

## Networking issues

- List networks: `docker network ls`
- Test connectivity between containers: `docker exec <c1> ping <c2>`
- Check published ports: `docker port <container>`

## Cleanup

- Stopped containers: `docker container prune`
- Unused images: `docker image prune`
```

`samples/ssh-config.md`:

```markdown
# SSH Configuration Runbook

## Client config (~/.ssh/config)

```
Host prod
    HostName 203.0.113.10
    User deploy
    IdentityFile ~/.ssh/id_ed25519
    Port 22
```

## Hardening checklist (/etc/ssh/sshd_config)

- `PermitRootLogin no`
- `PasswordAuthentication no` (keys only)
- `MaxAuthTries 3`
- After edits: `sudo sshd -t` then `sudo systemctl reload sshd`

## Troubleshooting

- Verbose client output: `ssh -vvv user@host`
- Permission denied (publickey): check `~/.ssh` is 700, key files 600.
- Agent not forwarding keys: `ssh-add -l` then `ssh -A user@host`.
```

- [ ] **Step 2: Add `/samples/` to the PROGRAM.md ingest whitelist**

In `PROGRAM.md`, change:

```yaml
ingest_paths:
  - /Users/bila/notes/
  - /Users/bila/itkb/
  - /Users/bila/Desktop/it-checklist/
  - /Users/bila/dotfiles/
  - /etc/
  - /tmp/
```

to:

```yaml
ingest_paths:
  - /Users/bila/notes/
  - /Users/bila/itkb/
  - /Users/bila/Desktop/it-checklist/
  - /Users/bila/dotfiles/
  - /etc/
  - /tmp/
  - /samples/
```

- [ ] **Step 3: Verify ingest accepts a samples path**

Run: `python3 -c "from itkb.program import ingest_path_allowed; print(ingest_path_allowed('/samples/nginx-restart.md'))"`
Expected: `True`

- [ ] **Step 4: Commit**

```bash
git add samples/ PROGRAM.md
git commit -m "feat: add samples/ demo corpus, whitelist /samples/ for ingest"
```

---

### Task 5: Dockerfile + .dockerignore

**Files:**
- Create: `Dockerfile`, `.dockerignore`

- [ ] **Step 1: Create `Dockerfile`**

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY . .
RUN pip install --no-cache-dir .

ENV ITKB_PROGRAM_PATH=/app/PROGRAM.md
EXPOSE 8000
CMD ["kb", "serve", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 2: Create `.dockerignore`**

```
.git
.claude
.gstack
__pycache__
*.pyc
.pytest_cache
.mypy_cache
docs/
tests/
*.sqlite
```

- [ ] **Step 3: Verify the image builds**

Run: `docker build -t itkb-demo .`
Expected: build completes; `docker images itkb-demo` shows an image. (Requires Docker Desktop running; if Docker is unavailable, report DONE_WITH_CONCERNS and note it for the verification task.)

- [ ] **Step 4: Smoke-test the container CLI**

Run: `docker run --rm itkb-demo kb --help`
Expected: typer help output listing commands (serve, ingest, query, etc.)

- [ ] **Step 5: Commit**

```bash
git add Dockerfile .dockerignore
git commit -m "feat: Dockerfile for itkb api server"
```

---

### Task 6: docker-compose.yml

**Files:**
- Create: `docker-compose.yml`

- [ ] **Step 1: Create `docker-compose.yml`**

```yaml
x-api-common: &api-common
  build: .
  ports:
    - "8000:8000"
  volumes:
    - itkb-data:/root/.itkb
    - ./samples:/samples:ro
    - ./PROGRAM.md:/app/PROGRAM.md:ro
  healthcheck:
    test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/')"]
    interval: 10s
    timeout: 3s
    retries: 12

services:
  # Default: API only, talks to the host's Ollama (GPU on this Mac).
  api:
    <<: *api-common
    environment:
      OLLAMA_HOST: http://host.docker.internal:11434
    extra_hosts:
      - "host.docker.internal:host-gateway"

  # Bundled demo: API wired to the compose Ollama service + small models.
  api-demo:
    <<: *api-common
    profiles: ["bundled"]
    environment:
      OLLAMA_HOST: http://ollama:11434
      ITKB_MODEL: llama3.2:3b
      ITKB_EMBED_MODEL: nomic-embed-text
    depends_on:
      ollama-init:
        condition: service_completed_successfully

  ollama:
    profiles: ["bundled"]
    image: ollama/ollama:latest
    volumes:
      - ollama-models:/root/.ollama
    healthcheck:
      test: ["CMD", "ollama", "list"]
      interval: 5s
      timeout: 3s
      retries: 12

  ollama-init:
    profiles: ["bundled"]
    image: ollama/ollama:latest
    restart: "no"
    depends_on:
      ollama:
        condition: service_healthy
    environment:
      OLLAMA_HOST: http://ollama:11434
    command: sh -c "ollama pull llama3.2:3b && ollama pull nomic-embed-text"

  # Optional: pre-load samples/ into the KB (use together with bundled).
  ingest-samples:
    profiles: ["demo-data"]
    build: .
    restart: "no"
    volumes:
      - itkb-data:/root/.itkb
      - ./samples:/samples:ro
      - ./PROGRAM.md:/app/PROGRAM.md:ro
    environment:
      OLLAMA_HOST: http://ollama:11434
      ITKB_EMBED_MODEL: nomic-embed-text
    depends_on:
      ollama-init:
        condition: service_completed_successfully
    command: ["kb", "ingest", "/samples"]

volumes:
  itkb-data:
  ollama-models:
```

- [ ] **Step 2: Validate the compose file**

Run: `docker compose config -q && docker compose --profile bundled --profile demo-data config -q`
Expected: no output, exit 0 (both the default and all-profiles views validate)

- [ ] **Step 3: Commit**

```bash
git add docker-compose.yml
git commit -m "feat: docker-compose with default/bundled/demo-data profiles"
```

---

### Task 7: README "Run with Docker" section

**Files:**
- Modify: `README.md` (insert after the `## Quick Start` section, before `## Central Control — PROGRAM.md`)

- [ ] **Step 1: Insert the section**

```markdown
## Run with Docker

Prereq: Docker Desktop (or Docker Engine + compose plugin).

```bash
# Default: API container + your host's Ollama (keeps GPU + your models)
docker compose up

# Self-contained demo: bundled Ollama + llama3.2:3b + sample corpus (~2.3GB first pull)
docker compose --profile bundled --profile demo-data up
```

Then open http://localhost:8000.

Config precedence: env vars (`ITKB_MODEL`, `ITKB_EMBED_MODEL`,
`ITKB_PROGRAM_PATH`, `OLLAMA_HOST`) > `config.toml` (synced from PROGRAM.md).
Edit `PROGRAM.md` and restart the api container to change behavior — it is
mounted read-only into the container.

Data persists in the `itkb-data` volume. Full reset:

```bash
docker compose down -v
```

Note: on Linux, `host.docker.internal` is wired via `extra_hosts` in the
compose file; on macOS/Windows it works out of the box.
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add Run with Docker section to README"
```

---

### Task 8: Final verification

**Files:** none (verification only)

- [ ] **Step 1: Health stack**

Run:
```bash
flake8 itkb tests
/opt/homebrew/opt/python@3.11/bin/python3.11 -m mypy itkb
python3 -m pytest -q
```
Expected: flake8 no output; mypy `Success: no issues found`; `85 passed` (81 baseline + 4 new: 2 cli + 1 config + 1 program)

- [ ] **Step 2: Default-profile boot test**

Run:
```bash
docker compose up -d --build
sleep 8
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8000/
docker compose down
```
Expected: `200`. (The query endpoint needs the host's Ollama running; the UI itself must render regardless.)

- [ ] **Step 3: Bundled demo (optional, ~2.3GB download — manual)**

Run:
```bash
docker compose --profile bundled --profile demo-data up -d --build
docker compose logs -f ollama-init ingest-samples   # wait for both to complete
curl -s -X POST http://localhost:8000/api/query -H "Content-Type: application/json" -d '{"question": "how do I restart nginx"}'
docker compose down
```
Expected: response streams an answer citing `samples/nginx-restart.md`. Mark DONE if Step 1-2 pass and this is deferred to the user.

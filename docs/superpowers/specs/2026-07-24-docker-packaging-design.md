# Docker Packaging — Design Spec

Date: 2026-07-24
Status: Approved by user (design review in chat)

## Problem

itkb runs only as a host-installed CLI (`pip install -e .` + local Ollama).
There is no containerized, one-command way to run the service, which blocks the
portfolio requirement: `docker compose up` → working RAG demo on any machine.

## Goal

`docker compose up` gives a working itkb web UI on any machine, with three
composable profiles covering daily use (host Ollama + GPU), a self-contained
demo (bundled Ollama + small models), and an optional pre-loaded sample corpus.

## Non-Goals

- GPU passthrough inside containers (impossible on macOS Docker Desktop; the
  default profile sidesteps it by using the host's Ollama).
- Kubernetes/Helm, multi-replica, production hardening (TLS, reverse proxy).
- The README "Design decisions & trade-offs" narrative and architecture
  diagram — that is the separate README sub-project; this one only adds a
  "Run with Docker" quickstart section.
- API-key auth, audit log, PII redaction — separate sub-projects.

## Architecture

One `Dockerfile` + one `docker-compose.yml` with three profiles, plus two
small code changes, a `samples/` corpus, and a README section.

### Files

- **Create `Dockerfile`** — `python:3.11-slim`, copy repo, `pip install .`
  (pyproject.toml already exists; non-editable is fine given the
  `ITKB_PROGRAM_PATH` fix below), `CMD ["kb", "serve", "--host", "0.0.0.0",
  "--port", "8000"]`. Image stays ~300MB: embeddings go over HTTP to Ollama,
  no torch/sentence-transformers.
- **Create `docker-compose.yml`** — services and profiles below.
- **Create `samples/`** — 3 generic IT runbooks: `nginx-restart.md`,
  `docker-debug.md`, `ssh-config.md` (matches the KB's existing domain).
- **Modify `itkb/cli.py`** — add `--host` option to `serve` (default stays
  `127.0.0.1`; container passes `0.0.0.0`).
- **Modify `itkb/config.py`** — env-var overrides applied at the end of
  `load_config`: `ITKB_MODEL` → `model`, `ITKB_EMBED_MODEL` → `embed_model`.
- **Modify `itkb/program.py`** — `PROGRAM_PATH` respects `ITKB_PROGRAM_PATH`
  env var, defaulting to the current `Path(__file__).parent.parent /
  "PROGRAM.md"` (the current lookup breaks under a non-editable install).
- **Modify `PROGRAM.md`** — add `- /samples/` to the ingest path whitelist
  (no-op on the host where the path doesn't exist; enables the container's
  demo ingest).
- **Modify `README.md`** — new "Run with Docker" section (quickstart only).

### Services and profiles

| Profile | Services | Ollama | Models | Use case |
|---|---|---|---|---|
| *(default)* | `api` | host's via `host.docker.internal:11434` | host's (gemma4 / embeddinggemma) | daily use on this Mac, GPU speed |
| `bundled` | `api`, `ollama`, `ollama-init` | `ollama/ollama` service | pulls `llama3.2:3b` + `nomic-embed-text` on first boot | one-command demo on any machine |
| `demo-data` (with `bundled`) | + `ingest-samples` one-shot | — | — | pre-loads `samples/` so the demo answers immediately |

- `api`: build `.`, ports `8000:8000`, named volume `itkb-data` mounted at
  `/root/.itkb` (db + config survive rebuilds), repo `PROGRAM.md` mounted
  read-only at the path `ITKB_PROGRAM_PATH` points to, healthcheck on `GET /`.
  Default profile env: `OLLAMA_HOST=http://host.docker.internal:11434`
  (the official Ollama python client honors `OLLAMA_HOST` natively — no code
  change needed). Bundled profile env: `OLLAMA_HOST=http://ollama:11434`,
  `ITKB_MODEL=llama3.2:3b`, `ITKB_EMBED_MODEL=nomic-embed-text`.
- `ollama` (bundled): `ollama/ollama` image, named volume `ollama-models`,
  healthcheck on `ollama list` / API tags endpoint.
- `ollama-init` (bundled): one-shot using the same image; runs
  `ollama pull llama3.2:3b && ollama pull nomic-embed-text`;
  `depends_on: ollama: service_healthy`.
- `ingest-samples` (demo-data): one-shot from the app image; runs
  `kb ingest /samples`; `depends_on: api: service_healthy` (or service_started
  with a retry loop if healthcheck gating proves flaky — implementation
  detail).

### Config precedence (documented in README)

env vars > `config.toml` (which PROGRAM.md's models section syncs).
Local behavior is unchanged when no env vars are set.

## Data flow (bundled one-command demo)

1. `docker compose --profile bundled --profile demo-data up`
2. `ollama` starts and becomes healthy → `ollama-init` pulls
   `llama3.2:3b` (~2GB) and `nomic-embed-text` (~274MB).
3. `api` starts with bundled env vars, initializes the DB in `itkb-data`.
4. `ingest-samples` runs `kb ingest /samples`; `/samples/` is whitelisted in
   PROGRAM.md and mounted read-only.
5. User opens `http://localhost:8000`, asks "how do I restart nginx" →
   grounded answer citing the sample runbook.

## Error handling

- Startup ordering via healthchecks (`depends_on: condition:
  service_healthy`); one-shot init containers fail loudly and their logs say
  why (pull failure, ingest rejection).
- No Tavily key in the container → existing "[Web search unavailable…]" tool
  message path, unchanged.
- `docker compose down -v` documented as the full reset (drops `itkb-data`
  and `ollama-models`).
- Host Ollama not running in the default profile → API still serves the UI;
  queries fail with the Ollama connection error (same as today) — documented
  in the README section.

## Testing

TDD for the two code changes (repo conventions: pytest + pytest-mock):

1. `--host` flag — invoke `serve` with mocked `uvicorn.run`, assert the host
   argument is passed through; default remains `127.0.0.1`.
2. `ITKB_MODEL`/`ITKB_EMBED_MODEL` env overrides — set env, `load_config()`,
   assert override wins over the TOML value; unset env, assert TOML value.
3. `ITKB_PROGRAM_PATH` — point env var at a temp PROGRAM.md, assert
   `program.py` reads it; unset, assert default path behavior unchanged.

Container verification (shell-level, recorded in the plan):

- `docker compose config` validates.
- Default profile: `docker compose up -d` → `curl localhost:8000/` → 200.
- Bundled: `docker compose --profile bundled --profile demo-data up -d` →
  wait for init containers → `curl -X POST localhost:8000/api/query` returns
  a grounded answer citing `samples/`.

Health gates: `flake8 itkb tests`, `mypy itkb`, and full `pytest`
(81 baseline + new tests) all green.

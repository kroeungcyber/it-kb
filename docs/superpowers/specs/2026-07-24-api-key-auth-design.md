# API-Key Auth (Denied by Default) — Design Spec

Date: 2026-07-24
Status: Approved by user (design review in chat)

## Problem

The itkb FastAPI service exposes 7 `/api/*` endpoints with no authentication.
Any local process (or, if the host is ever bound to a non-loopback interface,
anything on the network) can query the KB, mutate the document store, trigger
ingest, and — worst of all — call `/api/command/confirm`, which executes
arbitrary shell commands after a pending-token check. The portfolio goal is
API-key auth **denied by default**: every `/api/*` request must present
credentials or be rejected.

## Goal

All `/api/*` endpoints require either a valid `X-API-Key` header or a valid
session cookie. Denied by default: no key configured → the server generates
one on first boot. The browser web UI authenticates via a minimal one-time
login overlay (HttpOnly cookie), with **no changes to existing JS fetch
calls** (same-origin cookies flow automatically).

## Non-Goals

- TLS/HTTPS termination, rate limiting, CSRF tokens, RBAC/multi-user,
  LDAP/OAuth, brute-force lockout. This is a single-user localhost/container
  service.
- Encrypting the API key at rest (config.toml is user-owned).
- Changing any retrieval/agent/ingest logic.

## Architecture

### Config (`itkb/config.py`)

Two new fields on the `Config` dataclass:

```python
api_key: str = ""
session_secret: str = ""
```

Both persist through the existing `load_config`/`save_config` (which already
iterate `fields(Config)`).

### Key/secret bootstrap (`itkb/api/app.py` startup)

On `startup`, after `load_config()`:
- If `cfg.api_key` is empty → `api_key = secrets.token_urlsafe(32)`,
  `save_config(cfg)`, and print once (styled, e.g. a visible
  `console.print`/`print` block):
  `API key: <key>` with a hint to paste it into the login box (or use as
  `X-API-Key` for curl).
- If `cfg.session_secret` is empty → generate `secrets.token_urlsafe(32)`,
  save.

Rotation: user sets `api_key`/`session_secret` via `kb config set` (or direct
TOML edit). Changing either invalidates outstanding session cookies
(stateless HMAC, see below).

### Auth gate (`itkb/api/app.py`)

A FastAPI **dependency** applied to every `/api/*` route except `/api/login`
and `/api/logout`:

```
Accept:  X-API-Key: <key>  OR  cookie itkb_session=<token>
Reject:  401 + WWW-Authenticate: Bearer
```

- `X-API-Key` matches `cfg.api_key` exactly (constant-time compare via
  `secrets.compare_digest`).
- Session token validity: recompute HMAC over `(api_key + expiry_iso)` with
  `session_secret`; valid iff the presented token equals the recomputed value
  AND expiry is in the future.

### Session token

Stateless, no server store:

```python
payload = f"{api_key}:{expiry_iso}"
token = payload + "." + hmac.new(session_secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
```

- Cookie `itkb_session`, `HttpOnly`, `SameSite=Lax`, `Path=/`,
  `Max-Age=2592000` (30 days).
- `expiry_iso` = `(datetime.now(timezone.utc) + timedelta(days=30))`
  ISO-8601. Reject if `< now`.
- Cookie set on `POST /api/login` success; cleared on `POST /api/logout`
  (Set-Cookie with `Max-Age=0`).

### Endpoints

| Route | Auth | Notes |
|---|---|---|
| `GET /` | open | HTML shell |
| `GET /static/*` | open | assets |
| `POST /api/login` | open | body `{"key": "..."}`; 200 + cookie, or 401 |
| `POST /api/logout` | open (best-effort) | clears cookie, 200 |
| `POST /api/query` | gated | SSE |
| `POST /api/ingest` | gated | |
| `GET /api/documents` | gated | |
| `DELETE /api/documents/{id}` | gated | |
| `GET /api/models` | gated | |
| `POST /api/command/confirm` | gated | highest risk |
| `GET /api/notes` | gated | |

Implementation: one `require_auth` dependency used by each gated route, or a
router-level dependency on a shared `/api` router (chosen at implementation
for clarity — a single `APIRouter(prefix="/api", dependencies=[Depends(require_auth)])`
for the gated routes, with login/logout registered on the bare app).

### Web UI login overlay

A minimal, self-contained snippet added to `chat.html`, `docs.html`,
`history.html`, `notes.html` (each is a standalone served file; no template
engine). Behavior:
- On load, JS probes `GET /api/notes` (cheap, gated). If 401 → show an
  overlay: an input + "Log in" button posting JSON to `/api/login`.
- On success → reload the page; cookies flow automatically, all existing
  fetches work unchanged.
- If a key is pasted into the input, that's the login credential; the overlay
  never stores the key in localStorage.

Style: reuse existing design tokens (cream/terracotta), matching the current
UI. Keep the snippet tiny (~25 lines).

## Data flow

1. First boot: startup generates + persists `api_key` and `session_secret`,
   prints the key once.
2. Browser opens `/` → page JS probes a gated endpoint → 401 → login overlay.
3. User pastes the printed key → `POST /api/login` → 200 + HttpOnly cookie.
4. Reload → probe succeeds → normal UI; all fetches carry the cookie.
5. curl/scripts: `curl -H "X-API-Key: <key>" http://127.0.0.1:8000/api/documents`.
6. 30 days later (or after key/secret rotation) → cookie invalid → 401 →
   overlay reappears.

## Error handling

- Missing/expired/forged credentials → `401` with
  `WWW-Authenticate: Bearer`. Body: JSON `{"detail": "Invalid API key or session"}`.
- Login with wrong key → `401`, no cookie set.
- `GET /api/models` already swallows its own runtime errors; auth wraps it
  the same as every other route.
- Startup generation is idempotent: never overwrites an existing key/secret
  (checked before generating).

## Testing (pytest + FastAPI TestClient)

New file `tests/test_auth.py`. `TestClient` is not used by any existing test
(verified — no blast radius).

1. `test_every_api_endpoint_requires_auth` — iterate the gated routes with no
   credentials → all 401.
2. `test_valid_x_api_key_allows_request` — set `cfg.api_key`, request with
   header → 200.
3. `test_wrong_api_key_rejected` — bad header → 401.
4. `test_login_sets_cookie` — POST `/api/login` with correct key → 200, cookie
   present with HttpOnly/SameSite attrs; subsequent gated request with cookie
   → 200.
5. `test_login_wrong_key_rejected` — 401, no cookie.
6. `test_logout_clears_cookie` — after login, logout → cookie cleared → gated
   request 401.
7. `test_expired_cookie_rejected` — craft a token with past expiry → 401.
8. `test_startup_generates_and_persists_key` — empty config → startup generates
   api_key + session_secret, writes to config.toml, and a second startup
   doesn't overwrite.
9. `test_tampered_cookie_rejected` — valid cookie with a flipped char → 401
   (HMAC integrity).

Auth config for tests: use a temp config dir via the existing
`monkeypatch`/`cfg_mod.CONFIG_DIR` pattern from `tests/test_config.py`, or
monkeypatch `load_config` — implementation detail; tests must not depend on
the real `~/.itkb`.

Health gates: `flake8 itkb tests`, `mypy itkb`, full `pytest` (88 + ~9 new).

## Docker compatibility

- The login overlay works inside the container: key printed to `api` logs on
  first boot, or `docker compose exec api kb config show api_key`.
- No compose changes required (auth is app-level).

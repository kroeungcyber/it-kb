# API-Key Auth Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Gate all 7 `/api/*` endpoints with API-key auth (denied by default), give the web UI a one-time login overlay, and auto-generate the key on first boot.

**Architecture:** New `itkb/api/auth.py` module (session-token helpers + a `require_auth` FastAPI dependency). `app.py` gains `api_key`/`session_secret` bootstrap in startup, `POST /api/login` + `POST /api/logout` (open), and the `require_auth` dependency on the 7 existing gated routes. Config gains two fields. Four HTML pages get a small login overlay.

**Tech Stack:** Python 3.11, FastAPI + TestClient, hmac/secrets stdlib, pytest + pytest-mock.

**Reference spec:** `docs/superpowers/specs/2026-07-24-api-key-auth-design.md`

## Global Constraints

- `/`, `/static/*`, `/api/login`, `/api/logout` stay open. All other `/api/*` routes are gated.
- Stateless sessions: HMAC-SHA256 over `api_key:expiry`, no server session store.
- Constant-time compares via `secrets.compare_digest` for API key and HMAC.
- No changes to retrieval/agent/ingest logic, no JS fetch changes (same-origin cookies).
- Health gates at the end: `flake8 itkb tests`, `mypy itkb` (via `/opt/homebrew/opt/python@3.11/bin/python3.11 -m mypy itkb`), `python3 -m pytest -q` (88 baseline + ~9 new ≈ 97 passed).
- Run pytest as `python3 -m pytest` from the repo root.
- Tests must not touch the real `~/.itkb` config — use the `cfg_mod.CONFIG_DIR/CONFIG_FILE` monkeypatch pattern from `tests/test_config.py`.

---

### Task 1: Config fields `api_key` and `session_secret`

**Files:**
- Modify: `itkb/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_config.py`:

```python
def test_api_key_and_session_secret_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    import itkb.config as cfg_mod
    cfg_mod.CONFIG_DIR = tmp_path / ".itkb"
    cfg_mod.CONFIG_FILE = cfg_mod.CONFIG_DIR / "config.toml"

    assert Config().api_key == ""
    assert Config().session_secret == ""
    save_config(Config(api_key="k123", session_secret="s456"))
    loaded = load_config()
    assert loaded.api_key == "k123"
    assert loaded.session_secret == "s456"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_config.py::test_api_key_and_session_secret_roundtrip -v`
Expected: FAIL (TypeError unexpected keyword 'api_key' or AttributeError)

- [ ] **Step 3: Add the fields**

In `itkb/config.py`, change:

```python
    tavily_api_key: str = ""
    web_fallback: bool = True
```

to:

```python
    tavily_api_key: str = ""
    web_fallback: bool = True
    api_key: str = ""
    session_secret: str = ""
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_config.py -v`
Expected: 6 passed (5 existing + 1 new)

- [ ] **Step 5: Commit**

```bash
git add itkb/config.py tests/test_config.py
git commit -m "feat: add api_key and session_secret config fields"
```

---

### Task 2: Startup auto-generation of key + secret

**Files:**
- Modify: `itkb/api/app.py` (imports + `startup`)
- Test: `tests/test_auth.py`

**Interfaces:**
- Produces: on first boot, `api_key`/`session_secret` are generated (`secrets.token_urlsafe(32)`), persisted via `save_config`, and the key printed once. Print suppressed when `ITKB_SILENT` env is set (for tests). Never overwrites existing values.

- [ ] **Step 1: Write the failing test**

Create `tests/test_auth.py`:

```python
# tests/test_auth.py
import itkb.config as cfg_mod
from itkb.api.app import app
from fastapi.testclient import TestClient


def _temp_config(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("ITKB_SILENT", "1")
    cfg_mod.CONFIG_DIR = tmp_path / ".itkb"
    cfg_mod.CONFIG_FILE = cfg_mod.CONFIG_DIR / "config.toml"
    cfg_mod.CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def test_startup_generates_and_persists_key(tmp_path, monkeypatch):
    _temp_config(tmp_path, monkeypatch)
    with TestClient(app) as client:
        first = cfg_mod.load_config()
        assert first.api_key
        assert first.session_secret
    with TestClient(app) as client:
        second = cfg_mod.load_config()
        assert second.api_key == first.api_key
        assert second.session_secret == first.session_secret
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_auth.py::test_startup_generates_and_persists_key -v`
Expected: FAIL (api_key stays "" — no generation code yet)

- [ ] **Step 3: Implement startup generation**

In `itkb/api/app.py`, change the imports:

```python
from __future__ import annotations
import json
from pathlib import Path
from typing import Optional
```

to:

```python
from __future__ import annotations
import json
import os
import secrets
from pathlib import Path
from typing import Optional
```

and change:

```python
from itkb.config import load_config
from itkb.store.db import init_db, list_documents, delete_document
```

to:

```python
from itkb.config import load_config, save_config
from itkb.store.db import init_db, list_documents, delete_document
```

and change the `startup` function:

```python
@app.on_event("startup")
def startup():
    cfg = load_config()
    init_db(cfg.db_path)
```

to:

```python
@app.on_event("startup")
def startup():
    cfg = load_config()
    changed = False
    if not cfg.api_key:
        cfg.api_key = secrets.token_urlsafe(32)
        changed = True
    if not cfg.session_secret:
        cfg.session_secret = secrets.token_urlsafe(32)
        changed = True
    if changed:
        save_config(cfg)
        if not os.environ.get("ITKB_SILENT"):
            print(f"\n=== itkb API key ===\n{cfg.api_key}\n=====================\n")
    init_db(cfg.db_path)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_auth.py -v`
Expected: 1 passed

- [ ] **Step 5: Commit**

```bash
git add itkb/api/app.py tests/test_auth.py
git commit -m "feat: auto-generate api key and session secret on first boot"
```

---

### Task 3: Session-token helpers in `itkb/api/auth.py`

**Files:**
- Create: `itkb/api/auth.py`
- Test: `tests/test_auth.py`

**Interfaces:**
- Produces: `make_session_token(api_key, secret, ttl_days=30) -> str` and `verify_session_token(token, api_key, secret) -> bool`. Token format: `{api_key}:{expiry_iso}.{hex_hmac}`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_auth.py`:

```python
from datetime import datetime, timedelta, timezone
from itkb.api.auth import make_session_token, verify_session_token


def test_make_and_verify_session_token():
    token = make_session_token("k123", "s456")
    assert verify_session_token(token, "k123", "s456") is True


def test_verify_rejects_wrong_secret():
    token = make_session_token("k123", "s456")
    assert verify_session_token(token, "k123", "WRONG") is False


def test_verify_rejects_wrong_key():
    token = make_session_token("k123", "s456")
    assert verify_session_token(token, "k999", "s456") is False


def test_verify_rejects_tampered_token():
    token = make_session_token("k123", "s456")
    tampered = token[:-1] + ("0" if token[-1] != "0" else "1")
    assert verify_session_token(tampered, "k123", "s456") is False


def test_verify_rejects_expired_token():
    expired = datetime.now(timezone.utc) - timedelta(days=1)
    token = make_session_token("k123", "s456", ttl_days=30)
    payload = f"k123:{expired.isoformat()}"
    import hashlib
    import hmac
    sig = hmac.new(b"s456", payload.encode(), hashlib.sha256).hexdigest()
    forged = f"{payload}.{sig}"
    assert verify_session_token(forged, "k123", "s456") is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_auth.py -v`
Expected: FAIL (ModuleNotFoundError: itkb.api.auth)

- [ ] **Step 3: Create `itkb/api/auth.py`**

```python
# itkb/api/auth.py
from __future__ import annotations
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone


def make_session_token(api_key: str, secret: str, ttl_days: int = 30) -> str:
    expiry = (datetime.now(timezone.utc) + timedelta(days=ttl_days)).isoformat()
    payload = f"{api_key}:{expiry}"
    return f"{payload}.{_sign(payload, secret)}"


def verify_session_token(token: str, api_key: str, secret: str) -> bool:
    try:
        payload, sig = token.rsplit(".", 1)
    except ValueError:
        return False
    if not secrets.compare_digest(sig, _sign(payload, secret)):
        return False
    try:
        stored_key, expiry = payload.split(":", 1)
    except ValueError:
        return False
    if stored_key != api_key:
        return False
    try:
        exp = datetime.fromisoformat(expiry)
    except ValueError:
        return False
    return exp > datetime.now(timezone.utc)


def _sign(payload: str, secret: str) -> str:
    return hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_auth.py -v`
Expected: 6 passed (1 startup + 5 token)

- [ ] **Step 5: Commit**

```bash
git add itkb/api/auth.py tests/test_auth.py
git commit -m "feat: session token helpers (HMAC-signed, expiring)"
```

---

### Task 4: `require_auth` dependency + gate all 7 endpoints

**Files:**
- Modify: `itkb/api/auth.py` (add `require_auth`), `itkb/api/app.py` (add dependency to 7 routes)
- Test: `tests/test_auth.py`

**Interfaces:**
- Produces: `require_auth(request, x_api_key)` dependency — accepts valid `X-API-Key` header or valid `itkb_session` cookie; else 401 with `WWW-Authenticate: Bearer`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_auth.py`:

```python
from fastapi.testclient import TestClient


@pytest.fixture
def authed_config(tmp_path, monkeypatch):
    _temp_config(tmp_path, monkeypatch)
    cfg_mod.save_config(cfg_mod.Config(api_key="testkey123", session_secret="testsecret456"))


def _gated_routes():
    return [
        ("get", "/api/documents"),
        ("get", "/api/models"),
        ("get", "/api/notes"),
        ("post", "/api/query"),
        ("post", "/api/ingest"),
        ("delete", "/api/documents/abc"),
        ("post", "/api/command/confirm"),
    ]


def test_every_gated_route_rejects_without_auth(authed_config):
    with TestClient(app) as client:
        for method, path in _gated_routes():
            r = getattr(client, method)(path, json={} if method == "post" else None)
            assert r.status_code == 401, f"{method} {path} expected 401, got {r.status_code}"


def test_valid_api_key_allows_request(authed_config):
    with TestClient(app) as client:
        r = client.get("/api/documents", headers={"X-API-Key": "testkey123"})
        assert r.status_code == 200


def test_wrong_api_key_rejected(authed_config):
    with TestClient(app) as client:
        r = client.get("/api/documents", headers={"X-API-Key": "wrong"})
        assert r.status_code == 401
```

Also add `import pytest` at the top of the test file if not present.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_auth.py -v`
Expected: the three new tests FAIL (routes still open → 200/404 instead of 401)

- [ ] **Step 3: Add `require_auth` to `itkb/api/auth.py`**

Append:

```python
from fastapi import Depends, Header, HTTPException, Request


def require_auth(request: Request, x_api_key: str = Header(default="")) -> None:
    from itkb.config import load_config

    cfg = load_config()
    expected = cfg.api_key or ""
    if x_api_key:
        if expected and secrets.compare_digest(x_api_key, expected):
            return
        _reject()
    token = request.cookies.get("itkb_session")
    if token and expected and verify_session_token(token, expected, cfg.session_secret):
        return
    _reject()


def _reject():
    raise HTTPException(
        status_code=401,
        detail="Invalid API key or session",
        headers={"WWW-Authenticate": "Bearer"},
    )
```

- [ ] **Step 4: Wire the dependency into `itkb/api/app.py`**

Add `from itkb.api.auth import require_auth` to the imports, then add `dependencies=[Depends(require_auth)]` to each of the 7 gated route decorators (add `from fastapi import Depends` to the existing fastapi import):

- `@app.post("/api/query")` → `@app.post("/api/query", dependencies=[Depends(require_auth)])`
- `@app.post("/api/ingest")` → `@app.post("/api/ingest", dependencies=[Depends(require_auth)])`
- `@app.get("/api/documents")` → `@app.get("/api/documents", dependencies=[Depends(require_auth)])`
- `@app.delete("/api/documents/{doc_id}")` → `@app.delete("/api/documents/{doc_id}", dependencies=[Depends(require_auth)])`
- `@app.get("/api/models")` → `@app.get("/api/models", dependencies=[Depends(require_auth)])`
- `@app.post("/api/command/confirm")` → `@app.post("/api/command/confirm", dependencies=[Depends(require_auth)])`
- `@app.get("/api/notes")` → `@app.get("/api/notes", dependencies=[Depends(require_auth)])`

Do NOT touch `/`, `/static`, or the new login/logout routes (added in Task 5).

- [ ] **Step 5: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_auth.py -v`
Expected: 9 passed

- [ ] **Step 6: Commit**

```bash
git add itkb/api/auth.py itkb/api/app.py tests/test_auth.py
git commit -m "feat: require API key or session on all /api routes"
```

---

### Task 5: Login/logout endpoints + cookie flow

**Files:**
- Modify: `itkb/api/app.py`
- Test: `tests/test_auth.py`

**Interfaces:**
- Produces: `POST /api/login` (body `{"key": str}`) → 200 + `itkb_session` HttpOnly cookie on success; 401 on bad key. `POST /api/logout` → clears cookie.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_auth.py`:

```python
def test_login_sets_cookie(authed_config):
    with TestClient(app) as client:
        r = client.post("/api/login", json={"key": "testkey123"})
        assert r.status_code == 200
        cookie = client.cookies.get("itkb_session")
        assert cookie
        r2 = client.get("/api/documents")
        assert r2.status_code == 200


def test_login_wrong_key_rejected(authed_config):
    with TestClient(app) as client:
        r = client.post("/api/login", json={"key": "wrong"})
        assert r.status_code == 401
        assert "itkb_session" not in client.cookies


def test_logout_clears_cookie(authed_config):
    with TestClient(app) as client:
        client.post("/api/login", json={"key": "testkey123"})
        r = client.post("/api/logout")
        assert r.status_code == 200
        r2 = client.get("/api/documents")
        assert r2.status_code == 401


def test_expired_cookie_rejected(authed_config):
    from datetime import datetime, timedelta, timezone
    import hashlib, hmac
    from itkb.api.auth import _sign
    expired = datetime.now(timezone.utc) - timedelta(days=1)
    payload = f"testkey123:{expired.isoformat()}"
    token = f"{payload}.{_sign(payload, 'testsecret456')}"
    with TestClient(app) as client:
        client.cookies.set("itkb_session", token)
        r = client.get("/api/documents")
        assert r.status_code == 401
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_auth.py -v`
Expected: the four new tests FAIL (404 on /api/login — route doesn't exist)

- [ ] **Step 3: Add login/logout to `itkb/api/app.py`**

Add a `LoginRequest` model next to the other request models:

```python
class LoginRequest(BaseModel):
    key: str
```

Add `from fastapi import ... Response` to the fastapi import line (append `Response`), and change `from itkb.api.auth import require_auth` to `from itkb.api.auth import make_session_token, require_auth`. Then append the two routes (open — no `require_auth` dependency):

```python
@app.post("/api/login")
def api_login(req: LoginRequest, response: Response):
    import secrets as _secrets
    from itkb.config import load_config

    cfg = load_config()
    if not (cfg.api_key and _secrets.compare_digest(req.key, cfg.api_key)):
        raise HTTPException(status_code=401, detail="Invalid API key")
    token = make_session_token(cfg.api_key, cfg.session_secret)
    response.set_cookie(
        "itkb_session", token, httponly=True, samesite="lax",
        max_age=2592000, path="/",
    )
    return {"status": "ok"}


@app.post("/api/logout")
def api_logout(response: Response):
    response.delete_cookie("itkb_session", path="/")
    return {"status": "ok"}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_auth.py -v`
Expected: 13 passed

- [ ] **Step 5: Commit**

```bash
git add itkb/api/app.py tests/test_auth.py
git commit -m "feat: login/logout endpoints with HttpOnly session cookie"
```

---

### Task 6: Login overlay in the four HTML pages

**Files:**
- Modify: `itkb/api/web/templates/chat.html`, `docs.html`, `history.html`, `notes.html`

**Interfaces:**
- Produces: an overlay that appears when an API probe returns 401, with a key input + login button; logs in via `/api/login` and reloads. No JS fetch changes to existing app logic.

- [ ] **Step 1: Add the overlay markup + script to each page**

Insert immediately before the closing `</body>` tag in each of the four files:

```html
<div id="auth-overlay" style="display:none;position:fixed;inset:0;background:#faf9f5;z-index:1000;align-items:center;justify-content:center;flex-direction:column;gap:1rem;text-align:center">
  <h2>Enter API key</h2>
  <p style="color:#6b6659">Paste the API key printed when the server started.</p>
  <input id="auth-key-input" type="password" placeholder="API key"
         style="padding:0.6rem 0.75rem;border:1px solid #e6e1d3;border-radius:6px;width:280px">
  <button id="auth-login-btn"
          style="background:#c1653c;color:#fff;border:none;padding:0.6rem 1.25rem;border-radius:6px;cursor:pointer">Log in</button>
  <div id="auth-error" style="color:#a83b32"></div>
</div>
<script>
(function () {
  function show() { document.getElementById("auth-overlay").style.display = "flex"; }
  fetch("/api/notes").then(function (r) { if (r.status === 401) show(); }).catch(show);
  document.getElementById("auth-login-btn").addEventListener("click", function () {
    var key = document.getElementById("auth-key-input").value.trim();
    fetch("/api/login", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ key: key }) })
      .then(function (r) { if (r.ok) { location.reload(); } else { document.getElementById("auth-error").textContent = "Invalid key"; } })
      .catch(function () { document.getElementById("auth-error").textContent = "Request failed"; });
  });
})();
</script>
```

The snippet is identical in all four files (each is served standalone; no template engine).

- [ ] **Step 2: Verify the overlay is present in all four files**

Run: `grep -c "auth-overlay" itkb/api/web/templates/*.html`
Expected: `chat.html:1`, `docs.html:1`, `history.html:1`, `notes.html:1`

- [ ] **Step 3: Commit**

```bash
git add itkb/api/web/templates/
git commit -m "feat: login overlay on chat, docs, history, notes pages"
```

---

### Task 7: Final verification

**Files:** none (verification only)

- [ ] **Step 1: Health stack**

Run:
```bash
flake8 itkb tests
/opt/homebrew/opt/python@3.11/bin/python3.11 -m mypy itkb
python3 -m pytest -q
```
Expected: flake8 no output; mypy `Success: no issues found`; `102 passed` (88 baseline + 14 new: 1 config + 13 auth)

- [ ] **Step 2: Manual smoke test**

Run: `ITKB_SILENT=1 python3 -c "
import itkb.config as c
import tempfile, os
tmp = tempfile.mkdtemp()
os.environ['HOME'] = tmp
c.CONFIG_DIR = __import__('pathlib').Path(tmp) / '.itkb'
c.CONFIG_FILE = c.CONFIG_DIR / 'config.toml'
from itkb.api.app import app
from fastapi.testclient import TestClient
with TestClient(app) as client:
    cfg = c.load_config()
    print('key:', cfg.api_key)
    print('no auth:', client.get('/api/documents').status_code)
    print('with key:', client.get('/api/documents', headers={'X-API-Key': cfg.api_key}).status_code)
"` (run from repo root so `itkb` resolves; the editable install points here)
Expected: a generated key prints; `no auth: 401`; `with key: 200`

- [ ] **Step 3: Browser check (manual, optional)**

Start the server (`kb serve`), open http://127.0.0.1:8000/, confirm: page loads, API probe fails silently, login overlay appears, pasting the printed key logs in and the UI works. (Note: the overlay shows on all 4 pages; verify at least the chat page.)

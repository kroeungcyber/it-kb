# tests/test_auth.py
import hashlib
import hmac
from datetime import datetime, timedelta, timezone

import pytest

import itkb.config as cfg_mod
from fastapi.testclient import TestClient

from itkb.api.app import app
from itkb.api.auth import _sign, make_session_token, verify_session_token


def _temp_config(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("ITKB_SILENT", "1")
    cfg_mod.CONFIG_DIR = tmp_path / ".itkb"
    cfg_mod.CONFIG_FILE = cfg_mod.CONFIG_DIR / "config.toml"
    cfg_mod.CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def test_startup_generates_and_persists_key(tmp_path, monkeypatch):
    _temp_config(tmp_path, monkeypatch)
    with TestClient(app):
        first = cfg_mod.load_config()
        assert first.api_key
        assert first.session_secret
    with TestClient(app):
        second = cfg_mod.load_config()
        assert second.api_key == first.api_key
        assert second.session_secret == first.session_secret


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
    payload = f"k123:{expired.isoformat()}"
    sig = hmac.new(b"s456", payload.encode(), hashlib.sha256).hexdigest()
    forged = f"{payload}.{sig}"
    assert verify_session_token(forged, "k123", "s456") is False


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
            if method == "post":
                r = client.post(path, json={})
            else:
                r = getattr(client, method)(path)
            assert r.status_code == 401, f"{method} {path} expected 401, got {r.status_code}"


def test_valid_api_key_allows_request(authed_config):
    with TestClient(app) as client:
        r = client.get("/api/documents", headers={"X-API-Key": "testkey123"})
        assert r.status_code == 200


def test_wrong_api_key_rejected(authed_config):
    with TestClient(app) as client:
        r = client.get("/api/documents", headers={"X-API-Key": "wrong"})
        assert r.status_code == 401


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
    expired = datetime.now(timezone.utc) - timedelta(days=1)
    payload = f"testkey123:{expired.isoformat()}"
    token = f"{payload}.{_sign(payload, 'testsecret456')}"
    with TestClient(app) as client:
        client.cookies.set("itkb_session", token)
        r = client.get("/api/documents")
        assert r.status_code == 401

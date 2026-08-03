# tests/test_auth.py
import hashlib
import hmac
from datetime import datetime, timedelta, timezone

import itkb.config as cfg_mod
from fastapi.testclient import TestClient

from itkb.api.app import app
from itkb.api.auth import make_session_token, verify_session_token


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

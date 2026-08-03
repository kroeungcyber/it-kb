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
    with TestClient(app):
        first = cfg_mod.load_config()
        assert first.api_key
        assert first.session_secret
    with TestClient(app):
        second = cfg_mod.load_config()
        assert second.api_key == first.api_key
        assert second.session_secret == first.session_secret

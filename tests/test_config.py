# tests/test_config.py
import pytest
from pathlib import Path
from itkb.config import Config, load_config, save_config

def test_default_config_values():
    cfg = Config()
    assert cfg.model == "llama3.1:8b"
    assert cfg.embed_model == "nomic-embed-text"
    assert cfg.top_k == 5
    assert cfg.trusted is False

def test_save_and_load_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    # Patch CONFIG_DIR after monkeypatching HOME
    import itkb.config as cfg_mod
    cfg_mod.CONFIG_DIR = tmp_path / ".itkb"
    cfg_mod.CONFIG_FILE = cfg_mod.CONFIG_DIR / "config.toml"

    original = Config(model="mistral:7b", top_k=8)
    save_config(original)
    loaded = load_config()
    assert loaded.model == "mistral:7b"
    assert loaded.top_k == 8

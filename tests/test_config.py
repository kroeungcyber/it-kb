# tests/test_config.py
import pytest

from itkb.config import Config, load_config, save_config


@pytest.fixture(autouse=True)
def _isolate_program(tmp_path, monkeypatch):
    """Keep config tests independent of the repo's committed PROGRAM.md."""
    p = tmp_path / "PROGRAM.md"
    p.write_text("# empty program\n")
    monkeypatch.setenv("ITKB_PROGRAM_PATH", str(p))


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

def test_web_fallback_config_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    import itkb.config as cfg_mod
    cfg_mod.CONFIG_DIR = tmp_path / ".itkb"
    cfg_mod.CONFIG_FILE = cfg_mod.CONFIG_DIR / "config.toml"

    assert Config().web_fallback is True          # default on
    save_config(Config(web_fallback=False))
    assert load_config().web_fallback is False    # persists

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

def test_load_config_apply_env_false_ignores_env(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    import itkb.config as cfg_mod
    cfg_mod.CONFIG_DIR = tmp_path / ".itkb"
    cfg_mod.CONFIG_FILE = cfg_mod.CONFIG_DIR / "config.toml"

    save_config(Config(model="toml-model"))
    monkeypatch.setenv("ITKB_MODEL", "env-model")
    assert load_config().model == "env-model"
    assert load_config(apply_env=False).model == "toml-model"

def test_audit_enabled_defaults_true(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    import itkb.config as cfg_mod
    cfg_mod.CONFIG_DIR = tmp_path / ".itkb"
    cfg_mod.CONFIG_FILE = cfg_mod.CONFIG_DIR / "config.toml"

    assert Config().audit_enabled is True
    save_config(Config(audit_enabled=False))
    assert load_config().audit_enabled is False

def test_redact_pii_defaults_true(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    import itkb.config as cfg_mod
    cfg_mod.CONFIG_DIR = tmp_path / ".itkb"
    cfg_mod.CONFIG_FILE = cfg_mod.CONFIG_DIR / "config.toml"

    assert Config().redact_pii is True
    save_config(Config(redact_pii=False))
    assert load_config().redact_pii is False


def test_program_models_drive_config(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    import itkb.config as cfg_mod
    cfg_mod.CONFIG_DIR = tmp_path / ".itkb"
    cfg_mod.CONFIG_FILE = cfg_mod.CONFIG_DIR / "config.toml"

    save_config(Config(model="toml-model", top_k=3))
    p = tmp_path / "PROGRAM.md"
    p.write_text(
        "## 1. Models\n\n```yaml\nchat: program-model       # LLM for ReAct agent loop\n"
        "embed: program-embed     # embedding model\n```\n\n"
        "## 5. Query Behavior\n\n```yaml\ntop_k: 9                  # chunks per search\n"
        "max_iterations: 7        # loop budget\ntrusted: true             # no prompt\n```\n"
    )
    monkeypatch.setenv("ITKB_PROGRAM_PATH", str(p))
    cfg = load_config()
    assert cfg.model == "program-model"
    assert cfg.embed_model == "program-embed"
    assert cfg.top_k == 9
    assert cfg.max_iterations == 7
    assert cfg.trusted is True


def test_env_overrides_program(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    import itkb.config as cfg_mod
    cfg_mod.CONFIG_DIR = tmp_path / ".itkb"
    cfg_mod.CONFIG_FILE = cfg_mod.CONFIG_DIR / "config.toml"

    save_config(Config())
    p = tmp_path / "PROGRAM.md"
    p.write_text("## 1. Models\n\n```yaml\nchat: program-model   # comment\nembed: program-embed # comment\n```\n")
    monkeypatch.setenv("ITKB_PROGRAM_PATH", str(p))
    monkeypatch.setenv("ITKB_MODEL", "env-model")
    cfg = load_config()
    assert cfg.model == "env-model"           # env beats PROGRAM.md
    assert cfg.embed_model == "program-embed"  # no env var for embed

# itkb/config.py
from __future__ import annotations
import os
import tomli as tomllib
import tomli_w
from pathlib import Path
from dataclasses import dataclass, asdict, fields

CONFIG_DIR = Path.home() / ".itkb"
CONFIG_FILE = CONFIG_DIR / "config.toml"

@dataclass
class Config:
    model: str = "llama3.1:8b"
    embed_model: str = "nomic-embed-text"
    db_path: str = str(Path.home() / ".itkb" / "kb.sqlite")
    top_k: int = 5
    max_iterations: int = 5
    trusted: bool = False
    tavily_api_key: str = ""
    web_fallback: bool = True
    api_key: str = ""
    session_secret: str = ""
    audit_enabled: bool = True
    redact_pii: bool = True

def _apply_program(cfg: Config) -> None:
    """PROGRAM.md is the source of truth for model/embed/top_k/max_iterations/trusted."""
    try:
        from itkb.program import get_models, get_query_settings
        models = get_models()
        settings = get_query_settings()
    except Exception:
        return  # PROGRAM.md missing or unreadable: keep config.toml values
    if models.get("chat"):
        cfg.model = models["chat"]
    if models.get("embed"):
        cfg.embed_model = models["embed"]
    if settings.get("top_k"):
        try:
            cfg.top_k = int(settings["top_k"])
        except (TypeError, ValueError):
            pass
    if settings.get("max_iterations"):
        try:
            cfg.max_iterations = int(settings["max_iterations"])
        except (TypeError, ValueError):
            pass
    if settings.get("trusted") is not None:
        cfg.trusted = str(settings["trusted"]).strip().lower() == "true"


def load_config(apply_env: bool = True) -> Config:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if not CONFIG_FILE.exists():
        save_config(Config())
    with open(CONFIG_FILE, "rb") as f:
        data = tomllib.load(f)
    valid_keys = {f.name for f in fields(Config)}
    cfg = Config(**{k: v for k, v in data.items() if k in valid_keys})
    _apply_program(cfg)
    if apply_env:
        if os.environ.get("ITKB_MODEL"):
            cfg.model = os.environ["ITKB_MODEL"]
        if os.environ.get("ITKB_EMBED_MODEL"):
            cfg.embed_model = os.environ["ITKB_EMBED_MODEL"]
    return cfg

def save_config(cfg: Config) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "wb") as f:
        tomli_w.dump(asdict(cfg), f)

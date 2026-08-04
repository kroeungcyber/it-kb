# tests/test_audit.py
import json

from itkb.audit import audit_log_path, log_event


def _tmp_cfg(tmp_path, monkeypatch, **overrides):
    monkeypatch.setenv("HOME", str(tmp_path))
    import itkb.config as cfg_mod
    cfg_mod.CONFIG_DIR = tmp_path / ".itkb"
    cfg_mod.CONFIG_FILE = cfg_mod.CONFIG_DIR / "config.toml"
    cfg_mod.save_config(cfg_mod.Config(**overrides))


def test_audit_path_is_next_to_db(tmp_path):
    assert audit_log_path(str(tmp_path / "kb.sqlite")) == tmp_path / "audit.jsonl"


def test_log_event_appends_valid_jsonl(tmp_path, monkeypatch):
    _tmp_cfg(tmp_path, monkeypatch)
    log_event(str(tmp_path / "kb.sqlite"), "query", query_id="abc", question="hi")
    lines = (tmp_path / "audit.jsonl").read_text().strip().split("\n")
    assert len(lines) == 1
    rec = json.loads(lines[0])
    assert rec["event"] == "query"
    assert rec["query_id"] == "abc"
    assert rec["question"] == "hi"
    assert "ts" in rec


def test_log_event_append_order(tmp_path, monkeypatch):
    _tmp_cfg(tmp_path, monkeypatch)
    db = str(tmp_path / "kb.sqlite")
    log_event(db, "a", n=1)
    log_event(db, "b", n=2)
    lines = (tmp_path / "audit.jsonl").read_text().strip().split("\n")
    assert json.loads(lines[0])["event"] == "a"
    assert json.loads(lines[1])["event"] == "b"


def test_disabled_audit_is_noop(tmp_path, monkeypatch):
    _tmp_cfg(tmp_path, monkeypatch, audit_enabled=False)
    log_event(str(tmp_path / "kb.sqlite"), "query", question="x")
    assert not (tmp_path / "audit.jsonl").exists()

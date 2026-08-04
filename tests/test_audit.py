# tests/test_audit.py
import json

from fastapi.testclient import TestClient

from itkb.audit import audit_log_path, log_event


def _tmp_cfg(tmp_path, monkeypatch, **overrides):
    monkeypatch.setenv("HOME", str(tmp_path))
    import itkb.config as cfg_mod
    cfg_mod.CONFIG_DIR = tmp_path / ".itkb"
    cfg_mod.CONFIG_FILE = cfg_mod.CONFIG_DIR / "config.toml"
    cfg_mod.save_config(
        cfg_mod.Config(db_path=str(tmp_path / "kb.sqlite"), **overrides)
    )


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


def test_web_query_logs_query_event(tmp_path, monkeypatch, mocker):
    monkeypatch.setenv("ITKB_SILENT", "1")
    _tmp_cfg(tmp_path, monkeypatch, api_key="testkey123", session_secret="testsecret456")

    def fake_run_agent(question, cfg, confirm_fn, collected_chunks=None,
                       query_id_holder=None):
        if query_id_holder is not None:
            query_id_holder.append("qid123")
        collected_chunks.extend(["1", "2"])
        yield "token1"
        yield "token2"

    mocker.patch("itkb.agent.loop.run_agent", side_effect=fake_run_agent)

    from itkb.api.app import app
    with TestClient(app) as client:
        r = client.post(
            "/api/query",
            json={"question": "restart nginx"},
            headers={"X-API-Key": "testkey123"},
        )
        assert r.status_code == 200

    lines = (tmp_path / "audit.jsonl").read_text().strip().split("\n")
    query_events = [json.loads(line) for line in lines
                    if json.loads(line)["event"] == "query"]
    assert len(query_events) == 1
    assert query_events[0]["query_id"] == "qid123"
    assert query_events[0]["question"] == "restart nginx"
    assert query_events[0]["chunk_ids"] == ["1", "2"]
    assert query_events[0]["source_count"] == 2


def test_login_logs_auth_event(tmp_path, monkeypatch):
    monkeypatch.setenv("ITKB_SILENT", "1")
    _tmp_cfg(tmp_path, monkeypatch, api_key="testkey123", session_secret="testsecret456")

    from itkb.api.app import app
    with TestClient(app) as client:
        r = client.post("/api/login", json={"key": "testkey123"})
        assert r.status_code == 200
        r2 = client.post("/api/login", json={"key": "wrong"})
        assert r2.status_code == 401

    lines = (tmp_path / "audit.jsonl").read_text().strip().split("\n")
    events = [json.loads(line) for line in lines if json.loads(line)["event"] == "auth.login"]
    assert [e["success"] for e in events] == [True, False]

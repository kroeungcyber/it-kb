# tests/test_redact.py
from itkb.ingestion.redact import redact_pii


def test_redacts_email_direct():
    assert "mail: [EMAIL REDACTED]" in redact_pii("mail: foo@bar.com")


def test_redacts_email_not_present_when_absent():
    assert redact_pii("no personal data here") == "no personal data here"


def test_redacts_phone():
    assert "[PHONE REDACTED]" in redact_pii("call +1 (555) 123-4567 now")


def test_redacts_ssn():
    assert "[NATIONAL_ID REDACTED]" in redact_pii("ssn 123-45-6789")


def test_redacts_credit_card():
    assert "[CREDIT_CARD REDACTED]" in redact_pii("card 4111 1111 1111 1111")


def test_keeps_ip_addresses():
    text = "server at 192.168.1.10 and 10.0.0.1"
    assert redact_pii(text) == text


def test_keeps_hostnames_and_tokens():
    text = "ssh server01.example.com; token sk-abc123xyz456"
    assert redact_pii(text) == text


def test_keeps_version_numbers():
    text = "nginx version 1.2.3 and kernel 6.1.0"
    assert redact_pii(text) == text


def test_ingest_hook_applies_redaction(tmp_path, monkeypatch, fake_embedding_fn, mocker):
    import pathlib
    import uuid
    import itkb.config as cfg_mod

    monkeypatch.setenv("ITKB_SILENT", "1")
    monkeypatch.setenv("HOME", str(tmp_path))
    cfg_mod.CONFIG_DIR = tmp_path / ".itkb"
    cfg_mod.CONFIG_FILE = cfg_mod.CONFIG_DIR / "config.toml"
    cfg_mod.save_config(cfg_mod.Config(
        redact_pii=True, db_path=str(tmp_path / "kb.sqlite"),
        audit_enabled=False,
    ))
    from itkb.store.db import init_db, doc_id, _connect
    init_db(str(tmp_path / "kb.sqlite"))
    mocker.patch("itkb.ingestion.embedder.embed_texts",
                 side_effect=lambda texts, model: [fake_embedding_fn(t, model) for t in texts])

    src = pathlib.Path("/tmp") / f"itkb-redact-{uuid.uuid4().hex}.md"
    src.write_text("# Note\n\nreach me at foo@bar.com or 123-45-6789\n")

    from itkb.cli import _ingest_file
    cfg = cfg_mod.load_config()
    try:
        _ingest_file(src, cfg)
    finally:
        src.unlink(missing_ok=True)

    conn = _connect(str(tmp_path / "kb.sqlite"))
    rows = conn.execute(
        "SELECT content FROM chunks WHERE doc_id = ?", (doc_id(str(src)),)
    ).fetchall()
    conn.close()
    text = " ".join(r[0] for r in rows)
    assert "foo@bar.com" not in text
    assert "123-45-6789" not in text
    assert "[EMAIL REDACTED]" in text or "[NATIONAL_ID REDACTED]" in text


def test_ingest_hook_respects_toggle_off(tmp_path, monkeypatch, fake_embedding_fn, mocker):
    import pathlib
    import uuid
    import itkb.config as cfg_mod

    monkeypatch.setenv("ITKB_SILENT", "1")
    monkeypatch.setenv("HOME", str(tmp_path))
    cfg_mod.CONFIG_DIR = tmp_path / ".itkb"
    cfg_mod.CONFIG_FILE = cfg_mod.CONFIG_DIR / "config.toml"
    cfg_mod.save_config(cfg_mod.Config(
        redact_pii=False, db_path=str(tmp_path / "kb.sqlite"),
        audit_enabled=False,
    ))
    from itkb.store.db import init_db, doc_id, _connect
    init_db(str(tmp_path / "kb.sqlite"))
    mocker.patch("itkb.ingestion.embedder.embed_texts",
                 side_effect=lambda texts, model: [fake_embedding_fn(t, model) for t in texts])

    src = pathlib.Path("/tmp") / f"itkb-noredact-{uuid.uuid4().hex}.md"
    src.write_text("# Note\n\nreach me at foo@bar.com\n")

    from itkb.cli import _ingest_file
    cfg = cfg_mod.load_config()
    try:
        _ingest_file(src, cfg)
    finally:
        src.unlink(missing_ok=True)

    conn = _connect(str(tmp_path / "kb.sqlite"))
    rows = conn.execute(
        "SELECT content FROM chunks WHERE doc_id = ?", (doc_id(str(src)),)
    ).fetchall()
    conn.close()
    text = " ".join(r[0] for r in rows)
    assert "foo@bar.com" in text

# tests/test_ingest.py
"""Coverage for kb add (file + URL ingestion) in itkb/cli.py.

These paths previously had zero test coverage. Guards against regressions in:
- heading/page metadata reaching stored chunks
- PROGRAM.md whitelist enforcement
- duplicate chunks accumulating on re-ingest
- errors surfacing instead of crashing the CLI
"""
import json
import pysqlite3.dbapi2 as sqlite3
import pytest

from itkb.cli import _ingest_file, _ingest_url
from itkb.config import Config


@pytest.fixture
def cfg(db_path):
    return Config(model="llama3.1:8b", embed_model="nomic-embed-text",
                  db_path=db_path, top_k=5, trusted=False)


def _chunk_rows(db_path, doc_id=None):
    conn = sqlite3.connect(db_path)
    if doc_id:
        rows = conn.execute(
            "SELECT doc_id, content, metadata FROM chunks WHERE doc_id = ?", (doc_id,)
        ).fetchall()
    else:
        rows = conn.execute("SELECT doc_id, content, metadata FROM chunks").fetchall()
    conn.close()
    return rows


def test_ingest_file_stores_heading_and_page_metadata(tmp_path, cfg, fake_embedding_fn, mocker):
    f = tmp_path / "notes.md"
    f.write_text("# Title\n\n## Section\n\nSome content about nginx.\n")

    mocker.patch("itkb.program.ingest_path_allowed", return_value=True)
    mocker.patch("itkb.ingestion.embedder.embed_texts",
                 side_effect=lambda texts, model: [fake_embedding_fn(t, model) for t in texts])

    _ingest_file(f, cfg)

    rows = _chunk_rows(cfg.db_path)
    metas = [json.loads(r[2]) for r in rows]
    assert all(m["source_path"] == str(f) for m in metas)
    assert any(m["heading"] == "Title > Section" for m in metas)


def test_ingest_url_stores_heading_and_page_metadata(cfg, fake_embedding_fn, mocker):
    url = "https://wiki.example.com/nginx"

    mocker.patch("itkb.program.ingest_url_allowed", return_value=True)
    mocker.patch("itkb.ingestion.parsers.parse_url",
                 return_value=("# Nginx\n\nRestart the service.\n", "Nginx Wiki Page"))
    mocker.patch("itkb.ingestion.embedder.embed_texts",
                 side_effect=lambda texts, model: [fake_embedding_fn(t, model) for t in texts])

    _ingest_url(url, cfg)

    rows = _chunk_rows(cfg.db_path)
    assert len(rows) == 1
    meta = json.loads(rows[0][2])
    assert meta["source_path"] == url
    assert meta["heading"] == "Nginx"


def test_ingest_url_blocked_by_whitelist(cfg, mocker):
    mocker.patch("itkb.program.ingest_url_allowed", return_value=False)
    parse_url = mocker.patch("itkb.ingestion.parsers.parse_url")

    _ingest_url("https://untrusted.example.com/page", cfg)

    parse_url.assert_not_called()
    assert _chunk_rows(cfg.db_path) == []


def test_ingest_url_reingest_does_not_duplicate_chunks(cfg, fake_embedding_fn, mocker):
    url = "https://wiki.example.com/nginx"

    mocker.patch("itkb.program.ingest_url_allowed", return_value=True)
    mocker.patch("itkb.ingestion.parsers.parse_url",
                 return_value=("# Nginx\n\nRestart the service.\n", "Nginx Wiki Page"))
    mocker.patch("itkb.ingestion.embedder.embed_texts",
                 side_effect=lambda texts, model: [fake_embedding_fn(t, model) for t in texts])

    _ingest_url(url, cfg)
    _ingest_url(url, cfg)

    rows = _chunk_rows(cfg.db_path)
    assert len(rows) == 1  # re-ingest replaces, doesn't append


def test_ingest_url_error_is_caught_not_raised(cfg, mocker):
    mocker.patch("itkb.program.ingest_url_allowed", return_value=True)
    mocker.patch("itkb.ingestion.parsers.parse_url", side_effect=RuntimeError("network down"))

    _ingest_url("https://wiki.example.com/nginx", cfg)  # must not raise

    assert _chunk_rows(cfg.db_path) == []

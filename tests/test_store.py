# tests/test_store.py
from itkb.store.db import (
    upsert_document, get_document, delete_document,
    insert_chunks, search_chunks, list_documents, log_command, doc_id
)
from itkb.store.models import Document, Chunk
from datetime import datetime, timezone

def make_doc(path="/notes/test.md"):
    return Document(
        id=doc_id(path), source_path=path, title="Test",
        file_type="md", ingested_at=datetime.now(timezone.utc).isoformat(),
        chunk_count=1, mtime=1000.0
    )

def test_init_creates_tables(db_path):
    import pysqlite3.dbapi2 as sqlite3
    import sqlite_vec
    conn = sqlite3.connect(db_path)
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' OR type='shadow'"
    ).fetchall()}
    conn.close()
    assert "documents" in tables
    assert "chunks" in tables
    assert "command_history" in tables

def test_upsert_and_get_document(db_path):
    doc = make_doc()
    upsert_document(db_path, doc)
    fetched = get_document(db_path, "/notes/test.md")
    assert fetched is not None
    assert fetched.title == "Test"

def test_get_document_returns_none_if_missing(db_path):
    assert get_document(db_path, "/nonexistent.md") is None

def test_insert_and_search_chunks(db_path):
    doc = make_doc()
    upsert_document(db_path, doc)
    chunk = Chunk(id=None, doc_id=doc.id, content="restart the nginx service", chunk_index=0)
    embedding = [0.1] * 768
    insert_chunks(db_path, [chunk], [embedding])
    results = search_chunks(db_path, [0.1] * 768, top_k=1)
    assert len(results) == 1
    assert results[0][0].content == "restart the nginx service"

def test_delete_document_removes_chunks(db_path):
    doc = make_doc()
    upsert_document(db_path, doc)
    chunk = Chunk(id=None, doc_id=doc.id, content="hello", chunk_index=0)
    insert_chunks(db_path, [chunk], [[0.1] * 768])
    delete_document(db_path, doc.id)
    assert get_document(db_path, "/notes/test.md") is None
    results = search_chunks(db_path, [0.1] * 768, top_k=5)
    assert results == []

def test_list_documents(db_path):
    upsert_document(db_path, make_doc("/a.md"))
    upsert_document(db_path, make_doc("/b.md"))
    docs = list_documents(db_path)
    assert len(docs) == 2

def test_log_command(db_path):
    log_command(db_path, "ls -la", "file1\nfile2", 0, "2026-06-08T00:00:00Z", "qid1")
    import pysqlite3.dbapi2 as sqlite3
    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT command, exit_code FROM command_history").fetchone()
    conn.close()
    assert row[0] == "ls -la"
    assert row[1] == 0

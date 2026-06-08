# itkb/store/db.py
from __future__ import annotations
import hashlib
import json
import pysqlite3.dbapi2 as sqlite3
import struct
from pathlib import Path
from typing import Optional
import sqlite_vec

from itkb.store.models import Document, Chunk


def _connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _serialize(v: list[float]) -> bytes:
    return struct.pack(f"{len(v)}f", *v)


def init_db(db_path: str) -> None:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = _connect(db_path)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS documents (
            id          TEXT PRIMARY KEY,
            source_path TEXT NOT NULL,
            title       TEXT,
            file_type   TEXT,
            ingested_at TEXT,
            chunk_count INTEGER,
            mtime       REAL
        );
        CREATE TABLE IF NOT EXISTS chunks (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_id      TEXT REFERENCES documents(id) ON DELETE CASCADE,
            content     TEXT NOT NULL,
            chunk_index INTEGER,
            metadata    TEXT
        );
        CREATE VIRTUAL TABLE IF NOT EXISTS chunk_embeddings USING vec0(
            chunk_id  INTEGER PRIMARY KEY,
            embedding FLOAT[768]
        );
        CREATE TABLE IF NOT EXISTS command_history (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            command   TEXT NOT NULL,
            output    TEXT,
            exit_code INTEGER,
            ran_at    TEXT,
            query_id  TEXT
        );
    """)
    conn.commit()
    conn.close()


def doc_id(source_path: str) -> str:
    return hashlib.sha256(source_path.encode()).hexdigest()[:16]


def get_document(db_path: str, source_path: str) -> Optional[Document]:
    conn = _connect(db_path)
    row = conn.execute(
        "SELECT id, source_path, title, file_type, ingested_at, chunk_count, mtime "
        "FROM documents WHERE id = ?",
        (doc_id(source_path),)
    ).fetchone()
    conn.close()
    if row is None:
        return None
    return Document(*row)


def upsert_document(db_path: str, doc: Document) -> None:
    conn = _connect(db_path)
    conn.execute("""
        INSERT INTO documents (id, source_path, title, file_type, ingested_at, chunk_count, mtime)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            title=excluded.title, file_type=excluded.file_type,
            ingested_at=excluded.ingested_at, chunk_count=excluded.chunk_count,
            mtime=excluded.mtime
    """, (doc.id, doc.source_path, doc.title, doc.file_type,
          doc.ingested_at, doc.chunk_count, doc.mtime))
    conn.commit()
    conn.close()


def delete_document(db_path: str, doc_id_: str) -> None:
    conn = _connect(db_path)
    chunk_ids = [r[0] for r in conn.execute(
        "SELECT id FROM chunks WHERE doc_id = ?", (doc_id_,)
    ).fetchall()]
    for cid in chunk_ids:
        conn.execute("DELETE FROM chunk_embeddings WHERE chunk_id = ?", (cid,))
    conn.execute("DELETE FROM chunks WHERE doc_id = ?", (doc_id_,))
    conn.execute("DELETE FROM documents WHERE id = ?", (doc_id_,))
    conn.commit()
    conn.close()


def insert_chunks(db_path: str, chunks: list[Chunk], embeddings: list[list[float]]) -> None:
    conn = _connect(db_path)
    for chunk, embedding in zip(chunks, embeddings):
        cursor = conn.execute(
            "INSERT INTO chunks (doc_id, content, chunk_index, metadata) VALUES (?, ?, ?, ?)",
            (chunk.doc_id, chunk.content, chunk.chunk_index, chunk.metadata_json())
        )
        chunk_id = cursor.lastrowid
        conn.execute(
            "INSERT INTO chunk_embeddings (chunk_id, embedding) VALUES (?, ?)",
            (chunk_id, _serialize(embedding))
        )
    conn.commit()
    conn.close()


def search_chunks(db_path: str, query_embedding: list[float], top_k: int = 5) -> list[tuple[Chunk, float]]:
    conn = _connect(db_path)
    rows = conn.execute("""
        SELECT c.id, c.doc_id, c.content, c.chunk_index, c.metadata, ce.distance
        FROM chunk_embeddings ce
        JOIN chunks c ON c.id = ce.chunk_id
        WHERE ce.embedding MATCH ?
          AND k = ?
        ORDER BY ce.distance
    """, (_serialize(query_embedding), top_k)).fetchall()
    conn.close()
    return [
        (Chunk(id=r[0], doc_id=r[1], content=r[2], chunk_index=r[3],
               metadata=json.loads(r[4] or "{}")), r[5])
        for r in rows
    ]


def list_documents(db_path: str) -> list[Document]:
    conn = _connect(db_path)
    rows = conn.execute(
        "SELECT id, source_path, title, file_type, ingested_at, chunk_count, mtime "
        "FROM documents ORDER BY ingested_at DESC"
    ).fetchall()
    conn.close()
    return [Document(*r) for r in rows]


def log_command(db_path: str, command: str, output: str, exit_code: int,
                ran_at: str, query_id: str) -> None:
    conn = _connect(db_path)
    conn.execute(
        "INSERT INTO command_history (command, output, exit_code, ran_at, query_id) "
        "VALUES (?, ?, ?, ?, ?)",
        (command, output, exit_code, ran_at, query_id)
    )
    conn.commit()
    conn.close()

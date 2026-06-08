# tests/test_agent.py
import pytest
from itkb.agent.loop import run_agent
from itkb.config import Config

def _cfg(db_path):
    cfg = Config()
    cfg.db_path = db_path
    cfg.trusted = False
    return cfg

def test_agent_returns_answer_when_no_tool_calls(mocker, db_path):
    mock_chat = mocker.patch("itkb.agent.loop.ollama.chat")
    mock_chat.return_value = {
        "message": {
            "content": "Restart nginx with: sudo systemctl restart nginx",
            "tool_calls": [],
        }
    }
    mocker.patch("itkb.agent.loop.suggest_followups", return_value=["Q1?", "Q2?", "Q3?"])

    tokens = list(run_agent("how do I restart nginx?", _cfg(db_path),
                             confirm_fn=lambda cmd: False))
    full = "".join(tokens)
    assert "nginx" in full.lower()

def test_agent_calls_search_kb_tool(mocker, db_path):
    from itkb.store.db import upsert_document, insert_chunks, doc_id
    from itkb.store.models import Document, Chunk
    from datetime import datetime, timezone

    doc = Document(
        id=doc_id("/kb/nginx.md"), source_path="/kb/nginx.md", title="Nginx",
        file_type="md", ingested_at=datetime.now(timezone.utc).isoformat(),
        chunk_count=1, mtime=1.0
    )
    upsert_document(db_path, doc)
    insert_chunks(db_path, [Chunk(None, doc.id, "nginx restart command", 0)], [[0.1]*768])

    call_count = 0
    def fake_chat(**kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return {
                "message": {
                    "content": "",
                    "tool_calls": [{"function": {"name": "search_kb", "arguments": {"query": "restart nginx"}}}],
                }
            }
        return {"message": {"content": "Use systemctl restart nginx", "tool_calls": []}}

    mocker.patch("itkb.agent.loop.ollama.chat", side_effect=fake_chat)
    mocker.patch("itkb.agent.loop.embed_query", return_value=[0.1]*768)
    mocker.patch("itkb.agent.loop.suggest_followups", return_value=[])

    tokens = list(run_agent("restart nginx", _cfg(db_path), confirm_fn=lambda cmd: False))
    assert call_count == 2

def test_agent_stops_after_max_iterations(mocker, db_path):
    call_count = 0
    def always_calls_tool(**kwargs):
        nonlocal call_count
        call_count += 1
        return {
            "message": {
                "content": "",
                "tool_calls": [{"function": {"name": "search_kb", "arguments": {"query": "q"}}}],
            }
        }

    mocker.patch("itkb.agent.loop.ollama.chat", side_effect=always_calls_tool)
    mocker.patch("itkb.agent.loop.embed_query", return_value=[0.1]*768)
    mocker.patch("itkb.agent.loop.suggest_followups", return_value=[])

    list(run_agent("keep searching forever", _cfg(db_path), confirm_fn=lambda cmd: False))
    assert call_count <= 6  # max 5 iterations + 1 forced final answer

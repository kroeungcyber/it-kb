# itkb/api/app.py
from __future__ import annotations
import json
import uuid
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from itkb.config import load_config
from itkb.store.db import init_db, list_documents, delete_document

app = FastAPI(title="itkb Web UI")

_STATIC = Path(__file__).parent / "web" / "static"
_TEMPLATES = Path(__file__).parent / "web" / "templates"

app.mount("/static", StaticFiles(directory=str(_STATIC)), name="static")


class QueryRequest(BaseModel):
    question: str
    top_k: int = 0


class IngestRequest(BaseModel):
    path: Optional[str] = None
    url: Optional[str] = None


class CommandRequest(BaseModel):
    command: str
    query_id: str


@app.on_event("startup")
def startup():
    cfg = load_config()
    init_db(cfg.db_path)


@app.get("/", response_class=HTMLResponse)
def chat_page():
    return (_TEMPLATES / "chat.html").read_text()


@app.get("/docs-ui", response_class=HTMLResponse)
def docs_page():
    return (_TEMPLATES / "docs.html").read_text()


@app.get("/history", response_class=HTMLResponse)
def history_page():
    return (_TEMPLATES / "history.html").read_text()


@app.post("/api/query")
def api_query(req: QueryRequest):
    from itkb.agent.loop import run_agent

    cfg = load_config()
    if req.top_k > 0:
        cfg.top_k = req.top_k

    def stream():
        for token in run_agent(req.question, cfg, confirm_fn=lambda cmd: False):
            yield f"data: {json.dumps({'token': token})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


@app.post("/api/ingest")
def api_ingest(req: IngestRequest):
    from itkb.cli import _ingest_file, _ingest_url

    cfg = load_config()
    if req.url:
        _ingest_url(req.url, cfg)
        return {"status": "ok", "source": req.url}
    if req.path:
        p = Path(req.path)
        if not p.exists():
            raise HTTPException(status_code=404, detail=f"Path not found: {req.path}")
        _ingest_file(p, cfg)
        return {"status": "ok", "source": req.path}
    raise HTTPException(status_code=400, detail="Provide path or url")


@app.get("/api/documents")
def api_list_documents():
    cfg = load_config()
    docs = list_documents(cfg.db_path)
    return [
        {
            "id": d.id, "title": d.title, "source_path": d.source_path,
            "file_type": d.file_type, "chunk_count": d.chunk_count,
            "ingested_at": d.ingested_at,
        }
        for d in docs
    ]


@app.delete("/api/documents/{doc_id}")
def api_delete_document(doc_id: str):
    cfg = load_config()
    delete_document(cfg.db_path, doc_id)
    return {"status": "ok"}


@app.get("/api/models")
def api_models():
    import ollama
    try:
        resp = ollama.list()
        return {"models": [m["name"] for m in resp.get("models", [])]}
    except Exception as e:
        return {"models": [], "error": str(e)}


@app.post("/api/command/confirm")
def api_run_command(req: CommandRequest):
    from itkb.agent.tools import run_command

    cfg = load_config()
    try:
        output = run_command(req.command, confirm_fn=lambda cmd: True,
                             db_path=cfg.db_path, query_id=req.query_id)
        return {"output": output}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

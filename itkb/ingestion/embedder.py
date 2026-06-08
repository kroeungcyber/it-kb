# itkb/ingestion/embedder.py
from __future__ import annotations
from typing import Generator
import ollama

BATCH_SIZE = 32


def embed_texts(texts: list[str], model: str) -> list[list[float]]:
    embeddings: list[list[float]] = []
    for batch in _batches(texts, BATCH_SIZE):
        for text in batch:
            resp = ollama.embeddings(model=model, prompt=text)
            embeddings.append(resp["embedding"])
    return embeddings


def embed_query(text: str, model: str) -> list[float]:
    resp = ollama.embeddings(model=model, prompt=text)
    return resp["embedding"]


def _batches(items: list, size: int) -> Generator:
    for i in range(0, len(items), size):
        yield items[i : i + size]

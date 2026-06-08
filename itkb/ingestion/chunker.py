# itkb/ingestion/chunker.py
from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Optional

CHUNK_SIZE = 512   # approximate tokens
CHUNK_OVERLAP = 64


@dataclass
class RawChunk:
    content: str
    chunk_index: int
    page_number: Optional[int] = None
    section_heading: Optional[str] = None


def chunk_text(text: str, source_path: str) -> list[RawChunk]:
    sections = _split_into_sections(text)
    chunks: list[RawChunk] = []
    idx = 0
    for section in sections:
        for content in _chunk_section(section["text"]):
            chunks.append(RawChunk(
                content=content,
                chunk_index=idx,
                page_number=section.get("page"),
                section_heading=section.get("heading"),
            ))
            idx += 1
    return chunks


def _approx_tokens(text: str) -> int:
    return int(len(text.split()) * 1.3)


def _split_into_sections(text: str) -> list[dict]:
    sections: list[dict] = []
    current: dict = {"text": "", "heading": None, "page": None}

    for line in text.split("\n"):
        page_m = re.match(r"\[Page (\d+)\]", line)
        heading_m = re.match(r"^#{1,3}\s+(.+)", line)

        if page_m:
            if current["text"].strip():
                sections.append(current)
            current = {"text": "", "heading": current["heading"], "page": int(page_m.group(1))}
        elif heading_m:
            if current["text"].strip():
                sections.append(current)
            current = {"text": line + "\n", "heading": heading_m.group(1), "page": current["page"]}
        else:
            current["text"] += line + "\n"

    if current["text"].strip():
        sections.append(current)

    return sections or [{"text": text, "heading": None, "page": None}]


def _chunk_section(text: str) -> list[str]:
    text = text.strip()
    if not text:
        return []
    if _approx_tokens(text) <= CHUNK_SIZE:
        return [text]

    paragraphs = [p.strip() for p in re.split(r"\n\n+", text) if p.strip()]
    raw_chunks: list[str] = []
    current = ""

    for para in paragraphs:
        candidate = (current + "\n\n" + para).strip() if current else para
        if _approx_tokens(candidate) <= CHUNK_SIZE:
            current = candidate
        else:
            if current:
                raw_chunks.append(current)
            current = para

    if current:
        raw_chunks.append(current)

    # Apply overlap: prepend tail of previous chunk
    overlapped: list[str] = []
    for i, chunk in enumerate(raw_chunks):
        if i > 0:
            prev_words = raw_chunks[i - 1].split()
            tail = prev_words[-CHUNK_OVERLAP:] if len(prev_words) > CHUNK_OVERLAP else prev_words
            chunk = " ".join(tail) + "\n\n" + chunk
        overlapped.append(chunk)

    return overlapped

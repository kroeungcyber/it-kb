# itkb/agent/loop.py
from __future__ import annotations
import json
import uuid
from typing import Callable, Generator
import ollama

from itkb.agent.prompts import SYSTEM_PROMPT
from itkb.agent.tools import (
    TOOL_DEFINITIONS, search_kb, cite_sources, suggest_followups, run_command
)
from itkb.ingestion.embedder import embed_query
from itkb.config import Config

MAX_ITERATIONS = 5


def run_agent(
    question: str,
    cfg: Config,
    confirm_fn: Callable[[str], bool],
) -> Generator[str, None, None]:
    """Yield streamed response tokens including citations and follow-ups."""
    query_id = uuid.uuid4().hex[:8]
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]
    context_chunks: list[dict] = []

    for _ in range(MAX_ITERATIONS):
        response = ollama.chat(
            model=cfg.model,
            messages=messages,
            tools=TOOL_DEFINITIONS,
        )
        msg = response["message"]
        messages.append(msg)
        tool_calls = msg.get("tool_calls") or []

        if not tool_calls:
            answer = msg["content"]
            yield answer
            if context_chunks:
                yield f"\n\n---\n**Sources:**\n{cite_sources(context_chunks)}"
            followups = suggest_followups(answer, cfg.model)
            if followups:
                yield "\n\n**Follow-up questions:**\n" + "".join(f"- {q}\n" for q in followups)
            return

        for call in tool_calls:
            name = call["function"]["name"]
            args = call["function"]["arguments"]
            if isinstance(args, str):
                args = json.loads(args)

            if name == "search_kb":
                q_emb = embed_query(args["query"], cfg.embed_model)
                chunks = search_kb(q_emb, cfg.db_path, args.get("top_k", cfg.top_k))
                context_chunks.extend(chunks)
                tool_result = "\n\n".join(
                    f"[{c['source']}]\n{c['content']}" for c in chunks
                ) or "No results found."
                messages.append({"role": "tool", "content": tool_result})

            elif name == "run_command":
                output = run_command(args["command"], confirm_fn, cfg.db_path, query_id)
                messages.append({"role": "tool", "content": output})

    # Forced final answer after max iterations
    response = ollama.chat(
        model=cfg.model,
        messages=messages + [{"role": "user", "content": "Provide your final answer now."}],
    )
    yield response["message"]["content"]

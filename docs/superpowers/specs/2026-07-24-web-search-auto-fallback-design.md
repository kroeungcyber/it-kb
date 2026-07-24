# Automatic KB→Web Fallback — Design Spec

Date: 2026-07-24
Status: Approved by user (design review in chat)

## Problem

The itkb agent already ships a Tavily `web_search` tool, and the system prompt
tells the model to use it when the KB is insufficient. But the switch is 100%
model-driven: after `search_kb` returns "No results found." (empty database, or
a new issue with no matching markdown), the local model may call `web_search` —
or may hallucinate an answer instead. Nothing in `run_agent` guarantees the
fallback, so "new issue" queries can get confident, ungrounded answers despite
a configured Tavily key.

## Goal

When a `search_kb` call returns zero chunks, the agent loop itself calls
`web_search` and feeds the results to the model — deterministic KB→web
switching that does not depend on the local model's tool-calling reliability.

## Non-Goals

- Relevance-threshold fallback for non-empty-but-weak KB results (RRF scores
  are rank-based and awkward to threshold; evaluated and rejected as fuzzy to
  tune — YAGNI for now).
- Changes to the `web_search` tool itself (HTTP call, result formatting).
- Changes to the system prompt (existing rules already require citing web
  sources; the auto tool message is self-explanatory).
- UI changes.

## Architecture

One change site — the `search_kb` branch of `run_agent` in
`itkb/agent/loop.py` — plus one new field in `itkb/config.py`. No new modules,
no API changes.

### Config

Add to the `Config` dataclass in `itkb/config.py`:

```python
web_fallback: bool = True
```

Persists in `~/.itkb/config.toml` next to `tavily_api_key` via the existing
`load_config`/`save_config` (new field is picked up automatically since both
already iterate `fields(Config)`). `false` restores today's behavior.

### Fallback logic (`itkb/agent/loop.py`)

In `run_agent`, track a per-query flag `web_fallback_used = False`. In the
`search_kb` branch, after computing `chunks`:

```python
if not chunks and cfg.web_fallback and not web_fallback_used:
    web_fallback_used = True
    result = web_search(args["query"], api_key)
    messages.append({"role": "tool", "content":
        "[Auto web search: KB returned no results for this query]\n" + result})
```

- The KB tool message stays "No results found." so the model knows the KB was
  empty.
- Fires at most once per query: repeated empty `search_kb` calls within one
  query do not burn Tavily credits.
- `web_search` is already imported in `loop.py`; `api_key` is already resolved
  per query via `_resolve_api_key(cfg)`.

### Data flow (new issue, empty KB)

1. Model calls `search_kb("…")` → 0 chunks → tool message "No results found."
2. Loop auto-calls `web_search` → tool message with Tavily summary + top
   results (title/URL/content per hit).
3. Model answers from the web results and cites URLs (system prompt rule 3
   already requires citing web sources).
4. Streamed output: answer + follow-ups. No KB "Sources:" block, since
   `context_chunks` is empty — correct behavior.

## Error handling

All paths reuse existing behavior:

- No API key configured → `web_search` returns "[Web search unavailable…]" as
  the tool message; the model answers from general knowledge. No crash.
- Network/API failure → `web_search` returns "[Web search error: …]" as the
  tool message.
- Empty KB + `web_fallback: false` → byte-identical to today's behavior.

## Testing

Four new tests in `tests/test_agent.py`, following the existing mock patterns
(`mocker.patch("itkb.agent.loop.ollama.chat", side_effect=fake_chat)`, patched
`embed_query` and `suggest_followups`, empty `db_path` fixture):

1. **Fires on empty KB** — fake model calls `search_kb` once then answers;
   patch `itkb.agent.loop.web_search` to return "web results"; assert it was
   called once and that the second `ollama.chat` call's messages contain the
   `[Auto web search…]` tool message.
2. **Fires at most once per query** — fake model calls `search_kb` twice
   (empty DB both times) then answers; assert `web_search` call count == 1.
3. **Respects config toggle** — `cfg.web_fallback = False`, empty DB; assert
   `web_search` not called.
4. **No fallback when KB has results** — ingest one doc like
   `test_agent_calls_search_kb_tool` does; assert `web_search` not called.

Health Stack gates: `flake8 itkb tests` clean, full `pytest` green (76 + 4
new = 80 tests).

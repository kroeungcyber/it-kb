# Web Search Auto-Fallback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the itkb agent deterministically fall back to Tavily `web_search` whenever a `search_kb` call returns zero chunks, so "new issue" queries get grounded answers instead of hallucinations.

**Architecture:** One new field on the `Config` dataclass (`web_fallback: bool = True`) plus a small addition to the `search_kb` branch of `run_agent` in `itkb/agent/loop.py` that calls the existing `web_search` tool itself (at most once per query) and appends the results as a second tool message. No new modules, no prompt changes, no UI changes.

**Tech Stack:** Python 3.11, pytest + pytest-mock, Ollama tool-calling loop, Tavily HTTP API (already integrated).

**Reference spec:** `docs/superpowers/specs/2026-07-24-web-search-auto-fallback-design.md`

## Global Constraints

- No changes to `web_search` in `itkb/agent/tools.py` — reuse it exactly as-is.
- No changes to `itkb/api/app.py` or any web/static/template file.
- Fallback fires at most once per `run_agent` call (per query), and only when `cfg.web_fallback` is true.
- The existing `test_agent_stops_after_max_iterations` test calls `search_kb` against an empty DB; after this change it would trigger a **real** Tavily HTTP call on machines with a key configured. Task 2 stubs `web_search` in that test — this is required, not optional.
- Health Stack gates: `flake8 itkb tests` and full `pytest` must pass at the end.

---

### Task 1: Add `web_fallback` config field

**Files:**
- Modify: `itkb/config.py:18`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: `Config.web_fallback: bool`, default `True`, persisted in `~/.itkb/config.toml` via the existing `save_config`/`load_config` (both already iterate `dataclasses.fields(Config)`, so no other config code changes).

- [ ] **Step 1: Write the failing test**

Append to `tests/test_config.py`:

```python
def test_web_fallback_config_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    import itkb.config as cfg_mod
    cfg_mod.CONFIG_DIR = tmp_path / ".itkb"
    cfg_mod.CONFIG_FILE = cfg_mod.CONFIG_DIR / "config.toml"

    assert Config().web_fallback is True          # default on
    save_config(Config(web_fallback=False))
    assert load_config().web_fallback is False    # persists
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_config.py::test_web_fallback_config_roundtrip -v`
Expected: FAIL with `TypeError: Config.__init__() got an unexpected keyword argument 'web_fallback'` (or AttributeError on the first assert)

- [ ] **Step 3: Add the field**

In `itkb/config.py`, change:

```python
    tavily_api_key: str = ""
```

to:

```python
    tavily_api_key: str = ""
    web_fallback: bool = True
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_config.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add itkb/config.py tests/test_config.py
git commit -m "feat: add web_fallback config toggle (default on)"
```

---

### Task 2: Auto-fallback on empty KB results

**Files:**
- Modify: `itkb/agent/loop.py:92-103` (the `search_kb` branch)
- Test: `tests/test_agent.py`

**Interfaces:**
- Consumes: `Config.web_fallback` (Task 1); existing `web_search(query, api_key)` already imported in `loop.py`; `api_key` already resolved per query at `loop.py:64`.
- Produces: when `search_kb` returns zero chunks and fallback is enabled, a second tool message is appended right after the "No results found." one:
  `[Auto web search: KB returned no results for this query]\n<web_search output>`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_agent.py`:

```python
def test_agent_auto_web_fallback_on_empty_kb(mocker, db_path):
    call_count = 0

    def fake_chat(**kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return {
                "message": {
                    "content": "",
                    "tool_calls": [{"function": {"name": "search_kb", "arguments": {"query": "brand new issue"}}}],
                }
            }
        return {"message": {"content": "Answer from the web", "tool_calls": []}}

    mock_chat = mocker.patch("itkb.agent.loop.ollama.chat", side_effect=fake_chat)
    mocker.patch("itkb.agent.loop.embed_query", return_value=[0.1] * 768)
    mocker.patch("itkb.agent.loop.suggest_followups", return_value=[])
    mock_web = mocker.patch("itkb.agent.loop.web_search", return_value="Summary: answer from web")

    list(run_agent("brand new issue", _cfg(db_path), confirm_fn=lambda cmd: False))

    assert mock_web.call_count == 1
    second_msgs = mock_chat.call_args_list[1].kwargs["messages"]
    tool_msgs = [m.get("content", "") for m in second_msgs if m.get("role") == "tool"]
    assert any("[Auto web search" in c for c in tool_msgs)
```

Note: use `m.get("role")` / `m.get("content", "")` — assistant messages appended from the mocked ollama response have no `"role"` key, so `m["role"]` would raise KeyError.

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_agent.py::test_agent_auto_web_fallback_on_empty_kb -v`
Expected: FAIL with `AssertionError: assert 0 == 1` (mock_web never called)

- [ ] **Step 3: Implement the fallback (without once-per-query guard yet)**

In `itkb/agent/loop.py`, change the `search_kb` branch from:

```python
                tool_result = "\n\n".join(
                    _format_chunk(c) for c in chunks
                ) or "No results found."
                messages.append({"role": "tool", "content": tool_result})
```

to:

```python
                tool_result = "\n\n".join(
                    _format_chunk(c) for c in chunks
                ) or "No results found."
                messages.append({"role": "tool", "content": tool_result})
                if not chunks and cfg.web_fallback:
                    result = web_search(args["query"], api_key)
                    messages.append({"role": "tool", "content":
                                     "[Auto web search: KB returned no results for this query]\n" + result})
```

- [ ] **Step 4: Run the new test to verify it passes**

Run: `python3 -m pytest tests/test_agent.py::test_agent_auto_web_fallback_on_empty_kb -v`
Expected: PASS

- [ ] **Step 5: Stub `web_search` in the existing max-iterations test**

The fallback now fires in `test_agent_stops_after_max_iterations` (empty DB), which would make a real Tavily HTTP call. In `tests/test_agent.py`, change:

```python
    mocker.patch("itkb.agent.loop.ollama.chat", side_effect=always_calls_tool)
    mocker.patch("itkb.agent.loop.embed_query", return_value=[0.1]*768)
    mocker.patch("itkb.agent.loop.suggest_followups", return_value=[])
```

to:

```python
    mocker.patch("itkb.agent.loop.ollama.chat", side_effect=always_calls_tool)
    mocker.patch("itkb.agent.loop.embed_query", return_value=[0.1]*768)
    mocker.patch("itkb.agent.loop.web_search", return_value="web")  # empty DB now auto-falls back; stub HTTP
    mocker.patch("itkb.agent.loop.suggest_followups", return_value=[])
```

- [ ] **Step 6: Run the whole agent test file**

Run: `python3 -m pytest tests/test_agent.py -v`
Expected: 6 passed (5 existing + 1 new)

- [ ] **Step 7: Commit**

```bash
git add itkb/agent/loop.py tests/test_agent.py
git commit -m "feat: auto web_search fallback when KB returns zero chunks"
```

---

### Task 3: Fire the fallback at most once per query

**Files:**
- Modify: `itkb/agent/loop.py:62` (init) and the fallback block added in Task 2
- Test: `tests/test_agent.py`

**Interfaces:**
- Produces: per-query flag `web_fallback_used` local to `run_agent`; no signature changes.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_agent.py`:

```python
def test_agent_web_fallback_fires_once_per_query(mocker, db_path):
    call_count = 0

    def fake_chat(**kwargs):
        nonlocal call_count
        call_count += 1
        if call_count <= 2:
            return {
                "message": {
                    "content": "",
                    "tool_calls": [{"function": {"name": "search_kb", "arguments": {"query": "q"}}}],
                }
            }
        return {"message": {"content": "final", "tool_calls": []}}

    mocker.patch("itkb.agent.loop.ollama.chat", side_effect=fake_chat)
    mocker.patch("itkb.agent.loop.embed_query", return_value=[0.1] * 768)
    mocker.patch("itkb.agent.loop.suggest_followups", return_value=[])
    mock_web = mocker.patch("itkb.agent.loop.web_search", return_value="web")

    list(run_agent("q", _cfg(db_path), confirm_fn=lambda cmd: False))
    assert mock_web.call_count == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_agent.py::test_agent_web_fallback_fires_once_per_query -v`
Expected: FAIL with `AssertionError: assert 2 == 1` (fallback fires on both empty `search_kb` calls)

- [ ] **Step 3: Add the once-per-query flag**

In `itkb/agent/loop.py`, change (around line 62):

```python
    context_chunks: list[dict] = []

    api_key = _resolve_api_key(cfg)
```

to:

```python
    context_chunks: list[dict] = []
    web_fallback_used = False

    api_key = _resolve_api_key(cfg)
```

and change the fallback block from Task 2:

```python
                if not chunks and cfg.web_fallback:
                    result = web_search(args["query"], api_key)
                    messages.append({"role": "tool", "content":
                                     "[Auto web search: KB returned no results for this query]\n" + result})
```

to:

```python
                if not chunks and cfg.web_fallback and not web_fallback_used:
                    web_fallback_used = True
                    result = web_search(args["query"], api_key)
                    messages.append({"role": "tool", "content":
                                     "[Auto web search: KB returned no results for this query]\n" + result})
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_agent.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add itkb/agent/loop.py tests/test_agent.py
git commit -m "feat: fire web fallback at most once per query"
```

---

### Task 4: Guard tests — toggle off, KB has results

**Files:**
- Test: `tests/test_agent.py`

These lock in the two no-fallback paths from the spec. They pass against the current implementation; they exist so future refactors can't silently break them.

- [ ] **Step 1: Write the tests**

Append to `tests/test_agent.py`:

```python
def test_agent_no_web_fallback_when_disabled(mocker, db_path):
    call_count = 0

    def fake_chat(**kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return {
                "message": {
                    "content": "",
                    "tool_calls": [{"function": {"name": "search_kb", "arguments": {"query": "q"}}}],
                }
            }
        return {"message": {"content": "final", "tool_calls": []}}

    mocker.patch("itkb.agent.loop.ollama.chat", side_effect=fake_chat)
    mocker.patch("itkb.agent.loop.embed_query", return_value=[0.1] * 768)
    mocker.patch("itkb.agent.loop.suggest_followups", return_value=[])
    mock_web = mocker.patch("itkb.agent.loop.web_search", return_value="web")

    cfg = _cfg(db_path)
    cfg.web_fallback = False
    list(run_agent("q", cfg, confirm_fn=lambda cmd: False))
    assert mock_web.call_count == 0


def test_agent_no_web_fallback_when_kb_has_results(mocker, db_path):
    from itkb.store.db import upsert_document, insert_chunks, doc_id
    from itkb.store.models import Document, Chunk
    from datetime import datetime, timezone

    doc = Document(
        id=doc_id("/kb/nginx.md"), source_path="/kb/nginx.md", title="Nginx",
        file_type="md", ingested_at=datetime.now(timezone.utc).isoformat(),
        chunk_count=1, mtime=1.0
    )
    upsert_document(db_path, doc)
    insert_chunks(db_path, [Chunk(None, doc.id, "nginx restart command", 0)], [[0.1] * 768])

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
    mocker.patch("itkb.agent.loop.embed_query", return_value=[0.1] * 768)
    mocker.patch("itkb.agent.loop.suggest_followups", return_value=[])
    mock_web = mocker.patch("itkb.agent.loop.web_search", return_value="web")

    list(run_agent("restart nginx", _cfg(db_path), confirm_fn=lambda cmd: False))
    assert mock_web.call_count == 0
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_agent.py -v`
Expected: 9 passed

- [ ] **Step 3: Commit**

```bash
git add tests/test_agent.py
git commit -m "test: guard web fallback toggle and KB-has-results paths"
```

---

### Task 5: Final verification

**Files:** none (verification only)

- [ ] **Step 1: Lint**

Run: `flake8 itkb tests`
Expected: no output

- [ ] **Step 2: Full test suite**

Run: `python3 -m pytest -q`
Expected: `81 passed` (76 baseline + 5 new: 1 config + 4 agent)

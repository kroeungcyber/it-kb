# Chat UI Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restyle the itkb chat screen and shared sidebar shell from the current dark violet-on-navy "AI SaaS clone" look into a warm, restrained, editorial UI matching Claude's actual chat interface — no functional/behavioral changes.

**Architecture:** Pure front-end restyle across 3 layers: (1) `style.css` gets a full palette/design-system rewrite behind the same CSS custom-property names wherever possible so page markup doesn't need to change just to pick up new colors; (2) `app.js`'s message-rendering DOM structure changes so assistant replies render as plain text (no bubble/avatar) while user messages keep a bubble (no avatar) — this is the single biggest visual change; (3) the 4 template files (`chat.html`, `docs.html`, `history.html`, `notes.html`) get their duplicated sidebar markup updated (drop the gradient brand-dot, add a "New chat" link) since this project has no template-include mechanism (routes serve raw `.read_text()`, not Jinja2) — see `itkb/api/app.py:44-61`.

**Tech Stack:** Plain HTML/CSS/vanilla JS, FastAPI serving static files, no build step, no external font/CDN dependencies (system font stack only, per project being local-first/offline).

## Global Constraints

- No changes to `app.js` request/streaming/parsing logic (`sendQuestion`, `parseMarkdown`, `parseAssistantResponse`, SSE handling, pending-command token flow) — only the DOM structure `appendMsg`/`renderStreaming`/`renderAssistantFinal`/`showTyping` write into, per the approved spec.
- No webfont/CDN loading — system font stack only.
- No new backend routes, no Jinja2Templates migration — keep the existing `Path.read_text()` static-serve pattern in `itkb/api/app.py`.
- Documents/History/Notes page-specific content (tables, forms, note cards) keeps its current structure; only the shared sidebar markup and inherited CSS variables change for those pages.
- Palette: warm cream background (`~#faf9f5`), warm near-black text (`~#2d2b26`), single muted terracotta accent (`~#c1653c`) — no gradients, no glow/box-shadow halos in the old violet.
- Reference spec: `docs/superpowers/specs/2026-07-23-chat-ui-redesign-design.md`.

---

### Task 1: Rewrite `style.css` design system

**Files:**
- Modify: `itkb/api/web/static/style.css` (complete rewrite, all 647 lines)

**Interfaces:**
- Produces: CSS custom properties consumed by all 4 templates and by `app.js`-generated markup — `--bg-root`, `--bg-sidebar`, `--bg-main`, `--bg-surface`, `--bg-bubble-user`, `--bg-input`, `--bg-code`, `--border`, `--border-focus`, `--text-primary`, `--text-secondary`, `--text-muted`, `--accent`, `--accent-hover`, `--accent-tint`, `--danger`, `--danger-hover`, `--radius-sm/md/lg/xl`, `--font-sans`, `--font-mono`.
- Produces: new class names that Task 2/3/4 markup must use — `.new-chat-btn` (sidebar new-chat link), `.msg-content` (replaces `.msg-bubble` as the element `app.js` queries/fills — both user and assistant rows use this class, styled differently via `.msg-row.user .msg-content` / `.msg-row.assistant .msg-content`).
- Removes (no longer defined, must not be referenced by markup after this plan completes): `.brand-dot`, `.msg-avatar`, `.empty-icon`, `--bg-bubble-assistant`, `--accent-soft`, `--danger-soft`.

- [ ] **Step 1: Replace the full contents of `itkb/api/web/static/style.css`**

```css
/* ══════════════════════════════════════════════════════════════════════
   itkb — Chat Interface
   ══════════════════════════════════════════════════════════════════════ */

/* ── Reset & Variables ─────────────────────────────────────────────── */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

:root {
  --bg-root: #faf9f5;
  --bg-sidebar: #f4f1ea;
  --bg-main: #faf9f5;
  --bg-surface: #efece3;
  --bg-bubble-user: #ece4d6;
  --bg-input: #ffffff;
  --bg-code: #f1ede2;
  --border: #e6e1d3;
  --border-focus: #c1653c;
  --text-primary: #2d2b26;
  --text-secondary: #6b6659;
  --text-muted: #9a9585;
  --accent: #c1653c;
  --accent-hover: #a8532f;
  --accent-tint: #f4e3d7;
  --danger: #a83b32;
  --danger-hover: #8a2f28;
  --radius-sm: 6px;
  --radius-md: 12px;
  --radius-lg: 20px;
  --radius-xl: 28px;
  --font-sans: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  --font-mono: ui-monospace, "SF Mono", "Cascadia Code", "Roboto Mono", Menlo, Consolas, monospace;
}

/* ── Layout ────────────────────────────────────────────────────────── */
body {
  font-family: var(--font-sans);
  background: var(--bg-root);
  color: var(--text-primary);
  height: 100vh;
  display: flex;
  overflow: hidden;
}

/* ══════════════════════════════════════════════════════════════════════
   Sidebar
   ══════════════════════════════════════════════════════════════════════ */
.sidebar {
  width: 260px;
  min-width: 260px;
  background: var(--bg-sidebar);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  padding: 1.25rem;
  gap: 0.25rem;
}

.sidebar-brand {
  font-size: 1.05rem;
  font-weight: 700;
  color: var(--text-primary);
  letter-spacing: -0.02em;
  margin-bottom: 1rem;
}

.new-chat-btn {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.55rem 0.75rem;
  margin-bottom: 0.9rem;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--bg-main);
  color: var(--text-primary);
  text-decoration: none;
  font-size: 0.85rem;
  font-weight: 500;
  transition: all 0.15s ease;
}

.new-chat-btn:hover {
  border-color: var(--accent);
  color: var(--accent-hover);
  background: var(--accent-tint);
}

.new-chat-btn svg { width: 16px; height: 16px; flex-shrink: 0; }

.sidebar-nav {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.sidebar-nav a {
  display: flex;
  align-items: center;
  gap: 0.625rem;
  padding: 0.55rem 0.75rem;
  border-radius: var(--radius-sm);
  color: var(--text-secondary);
  text-decoration: none;
  font-size: 0.875rem;
  font-weight: 450;
  transition: all 0.15s ease;
}

.sidebar-nav a:hover {
  background: var(--bg-surface);
  color: var(--text-primary);
}

.sidebar-nav a.active {
  background: var(--accent-tint);
  color: var(--accent-hover);
  font-weight: 600;
  box-shadow: inset 2px 0 0 0 var(--accent);
}

.sidebar-nav svg {
  width: 18px; height: 18px;
  flex-shrink: 0;
  opacity: 0.65;
}

.sidebar-nav a.active svg { opacity: 1; }

.sidebar-footer {
  margin-top: auto;
  padding-top: 1rem;
  border-top: 1px solid var(--border);
  font-size: 0.75rem;
  color: var(--text-muted);
  line-height: 1.6;
}

/* ══════════════════════════════════════════════════════════════════════
   Main Content Area
   ══════════════════════════════════════════════════════════════════════ */
.main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.chat-header {
  padding: 0.875rem 1.5rem;
  border-bottom: 1px solid var(--border);
  font-size: 0.85rem;
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-shrink: 0;
}

.header-icon { opacity: 0.5; }
.header-spacer { flex: 1; }

.model-badge {
  background: var(--bg-surface);
  padding: 0.2rem 0.6rem;
  border-radius: var(--radius-sm);
  font-size: 0.75rem;
  font-family: var(--font-mono);
  color: var(--accent-hover);
  border: 1px solid var(--border);
}

/* ══════════════════════════════════════════════════════════════════════
   Messages
   ══════════════════════════════════════════════════════════════════════ */
.messages {
  flex: 1;
  overflow-y: auto;
  padding: 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
  scroll-behavior: smooth;
  width: 100%;
  max-width: 900px;
  margin: 0 auto;
}

/* ── Empty State ──────────────────────────────────────────────────── */
.empty-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 1.25rem;
  text-align: center;
  padding: 2rem;
}

.empty-state h2 {
  font-size: 1.35rem;
  font-weight: 600;
  color: var(--text-primary);
}

.empty-state p {
  font-size: 0.9rem;
  color: var(--text-secondary);
  max-width: 440px;
  line-height: 1.6;
}

.suggestions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  justify-content: center;
  max-width: 480px;
}

.suggestion-chip {
  background: var(--bg-main);
  border: 1px solid var(--border);
  color: var(--text-secondary);
  padding: 0.55rem 1rem;
  border-radius: var(--radius-lg);
  font-size: 0.825rem;
  cursor: pointer;
  transition: all 0.15s ease;
  white-space: nowrap;
  font-family: var(--font-sans);
}

.suggestion-chip:hover {
  border-color: var(--accent);
  color: var(--accent-hover);
  background: var(--accent-tint);
}

/* ── Message Rows ─────────────────────────────────────────────────── */
.msg-row {
  display: flex;
  animation: msg-in 0.25s ease-out;
}

@keyframes msg-in {
  from { opacity: 0; transform: translateY(8px); }
  to   { opacity: 1; transform: translateY(0); }
}

.msg-row.user      { align-self: flex-end; max-width: 75%; }
.msg-row.assistant { align-self: stretch;  width: 100%; }

.msg-content {
  line-height: 1.65;
  font-size: 0.95rem;
  word-wrap: break-word;
  overflow-wrap: break-word;
  min-width: 0;
}

.msg-row.user .msg-content {
  background: var(--bg-bubble-user);
  color: var(--text-primary);
  padding: 0.7rem 1rem;
  border-radius: var(--radius-md);
  border-bottom-right-radius: var(--radius-sm);
}

.msg-row.assistant .msg-content {
  color: var(--text-primary);
  padding: 0.15rem 0;
}

/* ── Markdown Inside Messages ─────────────────────────────────────── */
.msg-content p         { margin: 0.4rem 0; }
.msg-content p:first-child { margin-top: 0; }
.msg-content p:last-child  { margin-bottom: 0; }
.msg-content strong    { color: var(--text-primary); font-weight: 600; }

.msg-content code {
  background: var(--bg-code);
  padding: 0.125rem 0.35rem;
  border-radius: 3px;
  font-family: var(--font-mono);
  font-size: 0.85em;
  color: var(--accent-hover);
}

.msg-content pre {
  background: var(--bg-code);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 0.75rem 1rem;
  margin: 0.5rem 0;
  overflow-x: auto;
}

.msg-content pre code {
  background: none;
  padding: 0;
  color: var(--text-primary);
}

.msg-content ul, .msg-content ol {
  padding-left: 1.5rem;
  margin: 0.4rem 0;
}

.msg-content li { margin: 0.2rem 0; }

.msg-content blockquote {
  border-left: 3px solid var(--accent);
  padding-left: 0.75rem;
  margin: 0.5rem 0;
  color: var(--text-secondary);
}

/* ── Sources ──────────────────────────────────────────────────────── */
.sources {
  margin-top: 0.65rem;
  padding-top: 0.65rem;
  border-top: 1px solid var(--border);
  font-size: 0.775rem;
  color: var(--text-muted);
  line-height: 1.5;
}

.sources strong { color: var(--text-secondary); }

/* ── Follow-up Chips ──────────────────────────────────────────────── */
.followups {
  margin-top: 0.75rem;
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
}

.followup-chip {
  background: transparent;
  border: 1px solid var(--border);
  color: var(--accent-hover);
  padding: 0.3rem 0.8rem;
  border-radius: var(--radius-lg);
  font-size: 0.775rem;
  cursor: pointer;
  transition: all 0.15s ease;
  font-family: var(--font-sans);
}

.followup-chip:hover {
  border-color: var(--accent);
  background: var(--accent-tint);
}

/* ── Command Block (run_command tool) ─────────────────────────────── */
.cmd-block {
  background: var(--bg-code);
  border: 1px solid var(--danger);
  border-radius: var(--radius-sm);
  padding: 0.5rem 0.75rem;
  margin-top: 0.5rem;
}

.cmd-block code {
  color: var(--danger);
  font-family: var(--font-mono);
}

.cmd-block button {
  background: var(--danger);
  color: white;
  border: none;
  padding: 0.25rem 0.75rem;
  border-radius: 4px;
  cursor: pointer;
  margin-left: 1rem;
  font-size: 0.8rem;
}

.cmd-block button:hover { background: var(--danger-hover); }

/* ── Streaming Cursor ─────────────────────────────────────────────── */
.msg-row.streaming .msg-content::after {
  content: "";
  display: inline-block;
  width: 8px; height: 16px;
  background: var(--accent);
  margin-left: 2px;
  vertical-align: text-bottom;
  animation: blink 0.8s step-end infinite;
}

@keyframes blink { 50% { opacity: 0; } }

/* ── Typing Indicator ─────────────────────────────────────────────── */
.typing-dots {
  display: flex; gap: 4px; padding: 0.25rem 0;
}

.typing-dots span {
  width: 6px; height: 6px;
  background: var(--text-muted);
  border-radius: 50%;
  animation: dot-bounce 1.2s infinite ease-in-out;
}

.typing-dots span:nth-child(2) { animation-delay: 0.15s; }
.typing-dots span:nth-child(3) { animation-delay: 0.3s; }

@keyframes dot-bounce {
  0%, 60%, 100% { transform: translateY(0); }
  30%           { transform: translateY(-5px); }
}

/* ══════════════════════════════════════════════════════════════════════
   Input Area
   ══════════════════════════════════════════════════════════════════════ */
.input-area {
  padding: 1rem 1.5rem 1.25rem;
  flex-shrink: 0;
}

.input-wrapper {
  max-width: 800px;
  margin: 0 auto;
  display: flex;
  gap: 0.5rem;
  background: var(--bg-input);
  border: 1px solid var(--border);
  border-radius: var(--radius-xl);
  padding: 0.4rem 0.4rem 0.4rem 1.125rem;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}

.input-wrapper:focus-within {
  border-color: var(--border-focus);
  box-shadow: 0 1px 3px rgba(45, 43, 38, 0.06), 0 0 0 3px var(--accent-tint);
}

.input-wrapper input {
  flex: 1;
  background: none;
  border: none;
  color: var(--text-primary);
  font-size: 0.925rem;
  font-family: var(--font-sans);
  outline: none;
  padding: 0.5rem 0;
}

.input-wrapper input::placeholder { color: var(--text-muted); }

.input-wrapper button {
  background: var(--accent);
  color: white;
  border: none;
  width: 38px; height: 38px;
  border-radius: 50%;
  cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  transition: all 0.15s ease;
  flex-shrink: 0;
}

.input-wrapper button:hover  { background: var(--accent-hover); transform: scale(1.04); }
.input-wrapper button:active { transform: scale(0.96); }
.input-wrapper button:disabled {
  opacity: 0.4;
  cursor: not-allowed;
  transform: none;
}

.input-wrapper button svg { width: 18px; height: 18px; }

.input-hint {
  text-align: center;
  font-size: 0.7rem;
  color: var(--text-muted);
  margin-top: 0.5rem;
}

/* ══════════════════════════════════════════════════════════════════════
   Pages: Documents, History, Notes
   ══════════════════════════════════════════════════════════════════════ */
.page-content {
  flex: 1;
  overflow-y: auto;
  padding: 1.5rem;
}

.page-content h2 {
  font-size: 1.15rem;
  font-weight: 600;
  margin-bottom: 1rem;
  color: var(--text-primary);
}

/* ── Docs table ──────────────────────────────────────────────────── */
#add-form {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 1rem;
}

#add-input {
  flex: 1;
  background: var(--bg-input);
  border: 1px solid var(--border);
  color: var(--text-primary);
  border-radius: var(--radius-sm);
  padding: 0.6rem 0.75rem;
  font-size: 0.925rem;
  font-family: var(--font-sans);
}

#add-input:focus {
  outline: none;
  border-color: var(--border-focus);
  box-shadow: 0 0 0 3px var(--accent-tint);
}

#add-btn, .btn-primary {
  background: var(--accent);
  color: white;
  border: none;
  padding: 0.6rem 1.25rem;
  border-radius: var(--radius-sm);
  cursor: pointer;
  font-size: 0.9rem;
  font-family: var(--font-sans);
  font-weight: 500;
  transition: background 0.15s;
}

#add-btn:hover, .btn-primary:hover { background: var(--accent-hover); }

#docs-table {
  width: 100%;
  border-collapse: collapse;
}

#docs-table th, #docs-table td {
  text-align: left;
  padding: 0.6rem 0.75rem;
  border-bottom: 1px solid var(--border);
  font-size: 0.9rem;
}

#docs-table th {
  color: var(--text-secondary);
  font-weight: 500;
}

.del-btn {
  background: none;
  border: 1px solid var(--danger);
  color: var(--danger);
  padding: 0.2rem 0.6rem;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.8rem;
  font-family: var(--font-sans);
  transition: all 0.15s;
}

.del-btn:hover { background: var(--danger); color: white; }

/* ── History table ───────────────────────────────────────────────── */
#history-table {
  width: 100%;
  border-collapse: collapse;
}

#history-table th, #history-table td {
  text-align: left;
  padding: 0.6rem 0.75rem;
  border-bottom: 1px solid var(--border);
  font-size: 0.875rem;
}

#history-table th {
  color: var(--text-secondary);
  font-weight: 500;
}

#history-table td { color: var(--text-primary); }

/* ── Notes table ─────────────────────────────────────────────────── */
#notes-table {
  width: 100%;
  border-collapse: collapse;
}

#notes-table th, #notes-table td {
  text-align: left;
  padding: 0.6rem 0.75rem;
  border-bottom: 1px solid var(--border);
  font-size: 0.875rem;
}

#notes-table th {
  color: var(--text-secondary);
  font-weight: 500;
}

/* ══════════════════════════════════════════════════════════════════════
   Scrollbar
   ══════════════════════════════════════════════════════════════════════ */
.messages::-webkit-scrollbar,
.page-content::-webkit-scrollbar { width: 6px; }

.messages::-webkit-scrollbar-track,
.page-content::-webkit-scrollbar-track { background: transparent; }

.messages::-webkit-scrollbar-thumb,
.page-content::-webkit-scrollbar-thumb {
  background: var(--text-muted);
  border-radius: 3px;
}

.messages::-webkit-scrollbar-thumb:hover,
.page-content::-webkit-scrollbar-thumb:hover { background: var(--text-secondary); }

/* ══════════════════════════════════════════════════════════════════════
   Responsive
   ══════════════════════════════════════════════════════════════════════ */
@media (max-width: 700px) {
  .sidebar { display: none; }
  .msg-row.user { max-width: 96%; }
}

@media (min-width: 1200px) {
  .msg-row.user { max-width: 70%; }
}
```

- [ ] **Step 2: Verify no old dark-theme colors or removed identifiers remain**

Run: `grep -nE "#6c5ce7|#4f3cc9|#0d0f14|#a855f7|#1e2230|108, 92, 231|brand-dot|msg-avatar|empty-icon|bg-bubble-assistant|accent-soft|danger-soft|JetBrains|\"Inter\"" itkb/api/web/static/style.css`
Expected: no output (empty grep match = success)

- [ ] **Step 3: Commit**

```bash
git add itkb/api/web/static/style.css
git commit -m "$(cat <<'EOF'
redesign: warm editorial palette in style.css

Replace the violet-on-navy AI-clone palette with a cream/terracotta
design system, add .new-chat-btn and .msg-content styles ahead of the
markup changes that consume them. Markup still references the old
.msg-bubble/.msg-avatar/.brand-dot classes until the next tasks land,
so the page will look partially unstyled until Task 2-4 are applied.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: Update message rendering DOM structure in `app.js`

**Files:**
- Modify: `itkb/api/web/static/app.js:154-224`

**Interfaces:**
- Consumes: `.msg-content` class produced by Task 1's CSS (`.msg-row.user .msg-content`, `.msg-row.assistant .msg-content`).
- Produces: `appendMsg(role, text, streaming)` now returns a `row` element containing a single `.msg-content` child (no `.msg-avatar`) — `renderStreaming(row, fullText)`, `renderAssistantFinal(row, fullText)`, and `showTyping(row)` (called from `sendQuestion` in the untouched lines 92-152) all still take the same `row` argument and internally look up `.msg-content` instead of `.msg-bubble`.

- [ ] **Step 1: Replace lines 154-224 of `itkb/api/web/static/app.js`**

Current code being replaced (for reference, `appendMsg` through `showTyping`):

```js
function appendMsg(role, text, streaming) {
  const row = document.createElement("div");
  row.className = "msg-row " + role + (streaming ? " streaming" : "");

  const avatar = document.createElement("div");
  avatar.className = "msg-avatar";
  avatar.textContent = role === "user" ? "U" : "K";

  const bubble = document.createElement("div");
  bubble.className = "msg-bubble";

  if (role === "assistant" && text) {
    bubble.innerHTML = parseMarkdown(text);
  } else {
    bubble.textContent = text;
  }

  row.appendChild(avatar);
  row.appendChild(bubble);
  chatMessages.appendChild(row);
  chatMessages.scrollTop = chatMessages.scrollHeight;
  return row;
}

function renderStreaming(row, fullText) {
  const bubble = row.querySelector(".msg-bubble");
  // During streaming, show raw markdown — parse happens on [DONE]
  const parsed = parseAssistantResponse(fullText);
  bubble.innerHTML = parseMarkdown(parsed.body);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

function renderAssistantFinal(row, fullText) {
  const bubble = row.querySelector(".msg-bubble");
  const parsed = parseAssistantResponse(fullText);

  // Render body as markdown
  bubble.innerHTML = parseMarkdown(parsed.body);

  // Add sources
  if (parsed.sources) {
    const sourcesDiv = document.createElement("div");
    sourcesDiv.className = "sources";
    sourcesDiv.innerHTML = "<strong>Sources:</strong> " + parsed.sources;
    bubble.appendChild(sourcesDiv);
  }

  // Add follow-up chips
  if (parsed.followups.length) {
    const fuDiv = document.createElement("div");
    fuDiv.className = "followups";
    parsed.followups.forEach(q => {
      const chip = document.createElement("button");
      chip.className = "followup-chip";
      chip.textContent = q;
      chip.addEventListener("click", () => {
        questionInput.value = q;
        sendQuestion();
      });
      fuDiv.appendChild(chip);
    });
    bubble.appendChild(fuDiv);
  }

  chatMessages.scrollTop = chatMessages.scrollHeight;
}

function showTyping(row) {
  const bubble = row.querySelector(".msg-bubble");
  bubble.innerHTML = '<div class="typing-dots"><span></span><span></span><span></span></div>';
}
```

New code:

```js
function appendMsg(role, text, streaming) {
  const row = document.createElement("div");
  row.className = "msg-row " + role + (streaming ? " streaming" : "");

  const content = document.createElement("div");
  content.className = "msg-content";

  if (role === "assistant" && text) {
    content.innerHTML = parseMarkdown(text);
  } else {
    content.textContent = text;
  }

  row.appendChild(content);
  chatMessages.appendChild(row);
  chatMessages.scrollTop = chatMessages.scrollHeight;
  return row;
}

function renderStreaming(row, fullText) {
  const content = row.querySelector(".msg-content");
  // During streaming, show raw markdown — parse happens on [DONE]
  const parsed = parseAssistantResponse(fullText);
  content.innerHTML = parseMarkdown(parsed.body);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

function renderAssistantFinal(row, fullText) {
  const content = row.querySelector(".msg-content");
  const parsed = parseAssistantResponse(fullText);

  // Render body as markdown
  content.innerHTML = parseMarkdown(parsed.body);

  // Add sources
  if (parsed.sources) {
    const sourcesDiv = document.createElement("div");
    sourcesDiv.className = "sources";
    sourcesDiv.innerHTML = "<strong>Sources:</strong> " + parsed.sources;
    content.appendChild(sourcesDiv);
  }

  // Add follow-up chips
  if (parsed.followups.length) {
    const fuDiv = document.createElement("div");
    fuDiv.className = "followups";
    parsed.followups.forEach(q => {
      const chip = document.createElement("button");
      chip.className = "followup-chip";
      chip.textContent = q;
      chip.addEventListener("click", () => {
        questionInput.value = q;
        sendQuestion();
      });
      fuDiv.appendChild(chip);
    });
    content.appendChild(fuDiv);
  }

  chatMessages.scrollTop = chatMessages.scrollHeight;
}

function showTyping(row) {
  const content = row.querySelector(".msg-content");
  content.innerHTML = '<div class="typing-dots"><span></span><span></span><span></span></div>';
}
```

- [ ] **Step 2: Verify JS syntax is valid**

Run: `node --check itkb/api/web/static/app.js`
Expected: no output, exit code 0 (Node isn't otherwise used in this Python project, but `node --check` is a pure syntax linter — if `node` isn't installed, instead run `python3 -c "import subprocess,sys; sys.exit(0)"` is not a substitute; skip this step only if node is genuinely unavailable and rely on Step 3's manual smoke test instead)

- [ ] **Step 3: Verify no remaining references to removed classes**

Run: `grep -n "msg-avatar\|msg-bubble" itkb/api/web/static/app.js`
Expected: no output

- [ ] **Step 4: Commit**

```bash
git add itkb/api/web/static/app.js
git commit -m "$(cat <<'EOF'
redesign: drop avatars, unify message DOM to .msg-content

Assistant replies now render into a plain .msg-content element (styled
bubble-free per Task 1's CSS) instead of .msg-bubble beside a colored
.msg-avatar circle. User messages keep the same .msg-content element,
styled as a bubble via .msg-row.user .msg-content. No change to
streaming/parsing/fetch logic.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: Update chat page markup (`chat.html`)

**Files:**
- Modify: `itkb/api/web/templates/chat.html`

**Interfaces:**
- Consumes: `.new-chat-btn` CSS from Task 1; relies on Task 2's `app.js` to populate `#chat-messages` with `.msg-content`-based rows (no markup changes needed in the messages container itself — it's populated by JS).

- [ ] **Step 1: Replace the sidebar block (lines 11-38) in `itkb/api/web/templates/chat.html`**

Old:

```html
<!-- ── Sidebar ────────────────────────────────────────────── -->
<aside class="sidebar">
  <div class="sidebar-brand">
    <span class="brand-dot"></span> itkb
  </div>
  <nav class="sidebar-nav">
    <a href="/" class="active">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
      Chat
    </a>
    <a href="/docs-ui">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
      Documents
    </a>
    <a href="/history">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
      History
    </a>
    <a href="/notes">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 3v4a1 1 0 0 0 1 1h4"/><path d="M17 21H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h7l5 5v11a2 2 0 0 1-2 2z"/></svg>
      Notes
    </a>
  </nav>
  <div class="sidebar-footer">
    IT Knowledge Base<br>
    Local-first &middot; Ollama
  </div>
</aside>
```

New:

```html
<!-- ── Sidebar ────────────────────────────────────────────── -->
<aside class="sidebar">
  <div class="sidebar-brand">itkb</div>
  <a href="/" class="new-chat-btn">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
    New chat
  </a>
  <nav class="sidebar-nav">
    <a href="/" class="active">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
      Chat
    </a>
    <a href="/docs-ui">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
      Documents
    </a>
    <a href="/history">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
      History
    </a>
    <a href="/notes">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 3v4a1 1 0 0 0 1 1h4"/><path d="M17 21H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h7l5 5v11a2 2 0 0 1-2 2z"/></svg>
      Notes
    </a>
  </nav>
  <div class="sidebar-footer">
    IT Knowledge Base<br>
    Local-first &middot; Ollama
  </div>
</aside>
```

- [ ] **Step 2: Drop the header emoji and empty-state icon**

In the same file, change:

```html
  <div class="chat-header">
    <span class="header-icon">💬</span> Chat
    <div class="header-spacer"></div>
    <span class="model-badge">gemma4</span>
  </div>

  <div class="messages" id="chat-messages">
    <div class="empty-state" id="empty-state">
      <div class="empty-icon">⚡</div>
      <h2>IT Knowledge Base</h2>
```

to:

```html
  <div class="chat-header">
    Chat
    <div class="header-spacer"></div>
    <span class="model-badge">gemma4</span>
  </div>

  <div class="messages" id="chat-messages">
    <div class="empty-state" id="empty-state">
      <h2>IT Knowledge Base</h2>
```

- [ ] **Step 3: Verify removed identifiers are gone**

Run: `grep -n "brand-dot\|header-icon\|empty-icon" itkb/api/web/templates/chat.html`
Expected: no output

- [ ] **Step 4: Commit**

```bash
git add itkb/api/web/templates/chat.html
git commit -m "$(cat <<'EOF'
redesign: update chat page markup for new design system

Drop the gradient brand-dot, add a New chat link, remove the emoji
header icon and empty-state gradient circle icon — matching the
minimal, editorial look from the approved chat-ui-redesign spec.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: Update shared sidebar markup on Documents/History/Notes pages, fix Notes inline styles

**Files:**
- Modify: `itkb/api/web/templates/docs.html` (sidebar block, lines 11-38)
- Modify: `itkb/api/web/templates/history.html` (sidebar block, lines 11-38)
- Modify: `itkb/api/web/templates/notes.html` (sidebar block, lines 35-62; inline `<style>` block, lines 8-31)

**Interfaces:**
- Consumes: `.new-chat-btn`, `--bg-surface`, `--accent` CSS from Task 1.

- [ ] **Step 1: Replace the sidebar block in `itkb/api/web/templates/docs.html`**

Old (lines 11-38):

```html
<!-- ── Sidebar ────────────────────────────────────────────── -->
<aside class="sidebar">
  <div class="sidebar-brand">
    <span class="brand-dot"></span> itkb
  </div>
  <nav class="sidebar-nav">
    <a href="/">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
      Chat
    </a>
    <a href="/docs-ui" class="active">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
      Documents
    </a>
    <a href="/history">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
      History
    </a>
    <a href="/notes">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 3v4a1 1 0 0 0 1 1h4"/><path d="M17 21H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h7l5 5v11a2 2 0 0 1-2 2z"/></svg>
      Notes
    </a>
  </nav>
  <div class="sidebar-footer">
    IT Knowledge Base<br>
    Local-first &middot; Ollama
  </div>
</aside>
```

New:

```html
<!-- ── Sidebar ────────────────────────────────────────────── -->
<aside class="sidebar">
  <div class="sidebar-brand">itkb</div>
  <a href="/" class="new-chat-btn">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
    New chat
  </a>
  <nav class="sidebar-nav">
    <a href="/">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
      Chat
    </a>
    <a href="/docs-ui" class="active">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
      Documents
    </a>
    <a href="/history">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
      History
    </a>
    <a href="/notes">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 3v4a1 1 0 0 0 1 1h4"/><path d="M17 21H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h7l5 5v11a2 2 0 0 1-2 2z"/></svg>
      Notes
    </a>
  </nav>
  <div class="sidebar-footer">
    IT Knowledge Base<br>
    Local-first &middot; Ollama
  </div>
</aside>
```

- [ ] **Step 2: Apply the equivalent sidebar replacement to `itkb/api/web/templates/history.html`**

Same old→new block as Step 1, except keep `<a href="/history" class="active">` (not `/docs-ui`) as the active link — i.e. copy the new sidebar block from Step 1 verbatim but move `class="active"` from the Documents `<a>` to the History `<a>`.

- [ ] **Step 3: Apply the equivalent sidebar replacement to `itkb/api/web/templates/notes.html`**

Same block, but move `class="active"` to the Notes `<a>` (`<a href="/notes" class="active">`). This file's sidebar starts at line 35 (it has an extra inline `<style>` block above it — see Step 4).

- [ ] **Step 4: Fix `notes.html`'s inline `<style>` block to use surviving CSS variables**

Old (lines 8-31):

```html
  <style>
    .notes-list { display: flex; flex-direction: column; gap: 1rem; }
    .note-card {
      background: var(--bg-bubble-assistant);
      border: 1px solid var(--border);
      border-radius: var(--radius-md);
      padding: 1rem;
    }
    .note-body {
      color: var(--text-primary);
      font-size: 0.925rem;
      line-height: 1.6;
      margin-bottom: 0.5rem;
    }
    .note-meta {
      display: flex;
      gap: 2rem;
      font-size: 0.8rem;
      color: var(--text-muted);
    }
    .note-linked   { color: var(--accent-soft); }
    .note-unlinked { color: var(--text-muted); font-style: italic; }
    .note-id       { font-family: var(--font-mono); color: var(--text-muted); }
  </style>
```

New (only `.note-card` background and `.note-linked` color change — `--bg-bubble-assistant` and `--accent-soft` no longer exist after Task 1):

```html
  <style>
    .notes-list { display: flex; flex-direction: column; gap: 1rem; }
    .note-card {
      background: var(--bg-surface);
      border: 1px solid var(--border);
      border-radius: var(--radius-md);
      padding: 1rem;
    }
    .note-body {
      color: var(--text-primary);
      font-size: 0.925rem;
      line-height: 1.6;
      margin-bottom: 0.5rem;
    }
    .note-meta {
      display: flex;
      gap: 2rem;
      font-size: 0.8rem;
      color: var(--text-muted);
    }
    .note-linked   { color: var(--accent); }
    .note-unlinked { color: var(--text-muted); font-style: italic; }
    .note-id       { font-family: var(--font-mono); color: var(--text-muted); }
  </style>
```

- [ ] **Step 5: Verify no removed identifiers remain in any template**

Run: `grep -rn "brand-dot\|bg-bubble-assistant\|accent-soft" itkb/api/web/templates/`
Expected: no output

- [ ] **Step 6: Commit**

```bash
git add itkb/api/web/templates/docs.html itkb/api/web/templates/history.html itkb/api/web/templates/notes.html
git commit -m "$(cat <<'EOF'
redesign: apply new sidebar to Documents/History/Notes pages

Mirror chat.html's sidebar markup (drop brand-dot, add New chat link)
on the other 3 pages, and repoint notes.html's inline <style> block
off the CSS variables removed in the style.css rewrite
(--bg-bubble-assistant, --accent-soft).

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: Manual verification across all pages

**Files:** none (verification only)

- [ ] **Step 1: Start the dev server**

Run: `kb serve --port 8000 &` (or `python -m itkb.cli serve --port 8000 &` if the `kb` entry point isn't installed on PATH)
Expected: log line showing uvicorn listening on `127.0.0.1:8000`

- [ ] **Step 2: Smoke-test all 4 routes return 200 and contain expected new markup**

Run:
```bash
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/docs-ui
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/history
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/notes
curl -s http://127.0.0.1:8000/ | grep -c "new-chat-btn"
```
Expected: four `200` lines, then `1` (chat.html contains exactly one `.new-chat-btn`)

- [ ] **Step 3: Visual QA in a real browser**

Use the `run` skill (or open `http://127.0.0.1:8000/` directly) to confirm, on the Chat page:
- Empty state shows heading/copy/suggestion chips with no leftover gradient icon
- Clicking a suggestion chip sends a question; user message renders as a right-aligned tan bubble with no avatar; assistant reply streams in as plain text with no bubble/avatar, cursor blinks in the accent color while streaming
- Markdown (code blocks, lists, bold) renders correctly inside the assistant's plain-text response
- Sources line and follow-up chips render below the assistant response and are clickable
- Input pill shows a soft focus ring in the terracotta accent when focused, send button is disabled while a reply streams and re-enables after
- If a query happens to trigger the `run_command` tool (pending-command token flow), confirm the `.cmd-block` still renders with the danger-red border/button in the new palette — this is conditional on the model choosing to invoke it, not reproducible on demand

Then check Documents (`/docs-ui`), History (`/history`), and Notes (`/notes`):
- Sidebar shows "New chat" button, correct nav item highlighted with the left accent bar (not a filled pill)
- Documents table, add-document form, and delete buttons are legible on the new light palette
- Notes cards render with a visible card background and readable "linked question" accent color (confirms the Task 4 Step 4 variable fix worked)

- [ ] **Step 4: Responsive check**

Resize the browser window to ~650px wide and confirm the sidebar hides (per the existing `@media (max-width: 700px)` rule) and the chat layout remains usable.

- [ ] **Step 5: Stop the dev server**

Run: `kill %1` (or find and kill the `uvicorn`/`kb serve` process started in Step 1)

- [ ] **Step 6: Run project lint to confirm no Python files were incidentally broken**

Run: `flake8 itkb tests`
Expected: no output (this task touches no `.py` files, so this should already pass — it's a final sanity check per the project's Health Stack in `CLAUDE.md`)

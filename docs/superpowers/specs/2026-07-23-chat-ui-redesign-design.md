# Chat UI Redesign — Design

## Problem

The current chat UI (`itkb/api/web/templates/chat.html`, `static/style.css`, `static/app.js`) was
already restyled once (commit `93c653b`, "redesign chat UI: sidebar layout, modern AI chat
interface") but still reads as generic AI-generated boilerplate: dark navy background, violet
gradient accent, glowing brand dot, colored circle avatars, and bubbles around every message
(user and assistant alike). This is the default "AI SaaS clone" template, not a considered design.

## Goal

Restyle the chat screen and shared shell (sidebar/nav, used by all 4 pages) to read like Claude's
actual chat UI: warm/light, restrained, editorial rather than templated. Pure visual restyle —
no changes to `app.js` logic (SSE streaming, markdown parsing, sources/follow-ups, pending-command
token flow). Documents/History/Notes page-specific content (tables, forms) is out of scope beyond
inheriting the shared shell's new look.

## Scope

- In scope: `chat.html`, shared sidebar/header markup+CSS (used across all templates), `style.css`
  rules for shell + chat + messages + input, minimal DOM structure changes in `app.js` needed to
  support the new message layout (e.g. dropping avatar elements, changing which role gets a bubble
  class) — no changes to fetch/streaming/parsing logic.
- Out of scope: Documents/History/Notes page-specific layouts, backend/API changes, webfont
  loading (system font stack only — tool is local-first/offline), light/dark theme toggle (light
  only for now).

## Design

### Palette & typography
- Background: warm off-white/cream (`#faf9f5`-range), not navy.
- Text: near-black warm ink (`#2d2b26`-range), not gray-blue.
- Single accent: muted terracotta/rust (`#c1653c`-range) for send button, active nav state, links,
  focus rings — replaces the violet/purple used throughout the current CSS. No gradients, no glow
  effects.
- Font stack: system-ui only (`-apple-system, "Segoe UI", sans-serif`), no CDN/webfont fetch, since
  the tool runs fully local/offline against Ollama.

### Shell (sidebar, shared across all pages)
- Remove the glowing gradient brand-dot and emoji icons.
- Plain wordmark; nav icons at reduced opacity with thin strokes.
- Add a "New chat" affordance at the top as a real bordered button (currently absent).
- Active nav state: a subtle left accent bar instead of a filled pill/background.

### Messages (chat.html + app.js DOM structure)
- User messages: keep a bubble (soft tan/cream rounded rect), right-aligned, no avatar.
- Assistant messages: **no bubble, no avatar** — render as plain text directly on the page
  background, left-aligned, matching Claude's actual UI. This is the single biggest change and the
  main fix for the "generic AI clone" feel.
- Code blocks, inline code, sources block, and follow-up chips restyled in the new muted palette;
  no purple hover glow.
- Streaming cursor / typing indicator restyled to the new accent, same behavior.

### Input area
- Large soft-bordered pill, anchored bottom-center, subtle shadow (not a glow ring) on focus.
- Circular terracotta send button, same disabled/hover/active states as today.

### app.js changes (structural only, no logic changes)
- `appendMsg()`: stop creating a `.msg-avatar` element for assistant rows; stop wrapping assistant
  text in a `.msg-bubble` container (render straight into the row, or a plain `.msg-text` element
  with no bubble styling). User rows keep bubble + no avatar (avatar already adds little value here
  and isn't part of the target look).
- All existing selectors used by `renderStreaming`/`renderAssistantFinal`/`showTyping` continue to
  target elements that exist post-change — plan must account for renaming `.msg-bubble` lookups if
  the assistant container's class changes.

## Testing

No automated tests exist for the frontend (pure HTML/CSS/JS, no test harness in this repo). Verify
manually via the `run` skill / dev server:
- Load `/` and confirm empty state, then send a question, confirm streaming renders live,
  sources/follow-up chips render and are clickable, command-token blocks (if triggered) still work.
- Confirm sidebar nav + active state on all 4 pages (`/`, `/docs-ui`, `/history`, `/notes`).
- Resize to mobile width (~700px) to confirm existing responsive sidebar-hide behavior still works.

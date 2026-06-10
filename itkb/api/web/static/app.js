// itkb/api/web/static/app.js
"use strict";

// ── Chat ──────────────────────────────────────────────────────────────
const chatMessages = document.getElementById("chat-messages");
const questionInput = document.getElementById("question-input");
const sendBtn = document.getElementById("send-btn");

if (sendBtn) {
    sendBtn.addEventListener("click", sendQuestion);
    questionInput.addEventListener("keydown", e => {
        if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendQuestion(); }
    });
}

function sendQuestion() {
    const q = questionInput.value.trim();
    if (!q) return;
    questionInput.value = "";
    sendBtn.disabled = true;

    appendMsg("user", q);
    const assistantEl = appendMsg("assistant", "");
    showTyping(assistantEl);

    fetch("/api/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: q }),
    }).then(resp => {
        const reader = resp.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        let fullText = "";
        let firstToken = true;

        function read() {
            reader.read().then(({ done, value }) => {
                if (done) { sendBtn.disabled = false; return; }
                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split("\n");
                buffer = lines.pop();
                for (const line of lines) {
                    if (!line.startsWith("data: ")) continue;
                    const data = line.slice(6).trim();
                    if (data === "[DONE]") { sendBtn.disabled = false; return; }
                    try {
                        const { token } = JSON.parse(data);
                        fullText += token;
                        renderAssistantMsg(assistantEl, fullText);
                        firstToken = false;
                    } catch {}
                }
                read();
            });
        }
        read();
    }).catch(() => { sendBtn.disabled = false; });
}

function showTyping(el) {
    el.textContent = "";
    const div = document.createElement("div");
    div.className = "typing-indicator";
    for (let i = 0; i < 3; i++) {
        const dot = document.createElement("span");
        div.appendChild(dot);
    }
    el.appendChild(div);
}

function renderAssistantMsg(el, text) {
    el.textContent = "";
    const parts = text.split(/(\*\*Follow-up questions:\*\*[\s\S]*$|---\n\*\*Sources:\*\*[\s\S]*?(?=\n\n\*\*Follow|$))/);
    parts.forEach(part => {
        if (part.startsWith("**Follow-up questions:**")) {
            const questions = part.replace("**Follow-up questions:**", "").trim()
                .split("\n").filter(l => l.startsWith("- ")).map(l => l.slice(2));
            const div = document.createElement("div");
            div.className = "followups";
            questions.forEach(q => {
                const chip = document.createElement("button");
                chip.className = "followup-chip";
                chip.textContent = q;
                chip.addEventListener("click", () => {
                    questionInput.value = q;
                    sendQuestion();
                });
                div.appendChild(chip);
            });
            el.appendChild(div);
        } else if (part.includes("**Sources:**")) {
            const div = document.createElement("div");
            div.className = "sources";
            div.textContent = part.replace(/\*\*/g, "").trim();
            el.appendChild(div);
        } else if (part.trim()) {
            const span = document.createElement("span");
            span.textContent = part;
            el.appendChild(span);
        }
    });
}

function appendMsg(role, text) {
    const div = document.createElement("div");
    div.className = "msg " + role;
    div.textContent = text;
    chatMessages.appendChild(div);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    return div;
}

// ── Docs ──────────────────────────────────────────────────────────────
const docsTable = document.getElementById("docs-tbody");
const addInput = document.getElementById("add-input");
const addBtn = document.getElementById("add-btn");

if (docsTable) loadDocs();

if (addBtn) {
    addBtn.addEventListener("click", () => {
        const val = addInput.value.trim();
        if (!val) return;
        const body = val.startsWith("http") ? { url: val } : { path: val };
        fetch("/api/ingest", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
        }).then(() => { addInput.value = ""; loadDocs(); });
    });
}

function loadDocs() {
    fetch("/api/documents").then(r => r.json()).then(docs => {
        docsTable.textContent = "";
        docs.forEach(doc => {
            const tr = document.createElement("tr");
            const cells = [doc.title || doc.source_path, doc.file_type,
                           doc.chunk_count, doc.ingested_at.slice(0, 19)];
            cells.forEach(val => {
                const td = document.createElement("td");
                td.textContent = val;
                tr.appendChild(td);
            });
            const tdDel = document.createElement("td");
            const btn = document.createElement("button");
            btn.className = "del-btn";
            btn.textContent = "Delete";
            btn.addEventListener("click", () => {
                fetch(`/api/documents/${doc.id}`, { method: "DELETE" })
                    .then(() => loadDocs());
            });
            tdDel.appendChild(btn);
            tr.appendChild(tdDel);
            docsTable.appendChild(tr);
        });
    });
}

// ECIL helpdesk - vanilla JS, no deps. Renders chat, light markdown,
// confidence meter, debug panel, and KB stats from /api/health.

const $ = (id) => document.getElementById(id);

const chatWindow      = $("chatWindow");
const chatInput       = $("chatInput");
const sendBtn         = $("sendBtn");
const clearChatBtn    = $("clearChatBtn");
const confidenceFill  = $("confidenceFill");
const confidenceScore = $("confidenceScore");
const confidenceLabel = $("confidenceLabel");
const categoryList    = $("categoryList");
const quickButtons    = $("quickButtons");
const debugIntent     = $("debugIntent");
const debugScore      = $("debugScore");
const debugSource     = $("debugSource");
const debugMatches    = $("debugMatches");
const statDocs        = $("statDocs");
const statFaqs        = $("statFaqs");
const statCats        = $("statCats");

const quickPrompts = [
  "How do I apply for an internship at ECIL?",
  "What is the ECIL HR email?",
  "Tell me about VVPAT and EVM",
  "Where can I find ECIL tenders?",
  "Explain ECIL nuclear systems",
  "Who is the parent department of ECIL?",
];

// ---------- helpers ----------

const escapeHtml = (s) =>
  String(s ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");

// Lightweight markdown: bullets, **bold**, `code`, URLs, paragraph breaks.
function renderMarkdown(text) {
  if (!text) return "";
  const lines = String(text).split(/\r?\n/);
  const blocks = [];
  let buf = [];
  let listBuf = [];

  const flushPara = () => {
    if (buf.length) {
      blocks.push(`<p>${formatInline(buf.join(" "))}</p>`);
      buf = [];
    }
  };
  const flushList = () => {
    if (listBuf.length) {
      blocks.push(
        "<ul>" +
          listBuf.map((it) => `<li>${formatInline(it)}</li>`).join("") +
          "</ul>"
      );
      listBuf = [];
    }
  };

  for (const raw of lines) {
    const line = raw.trim();
    if (!line) {
      flushPara();
      flushList();
      continue;
    }
    if (/^[-*]\s+/.test(line)) {
      flushPara();
      listBuf.push(line.replace(/^[-*]\s+/, ""));
    } else {
      flushList();
      buf.push(line);
    }
  }
  flushPara();
  flushList();
  return blocks.join("");
}

function formatInline(text) {
  let out = escapeHtml(text);
  // **bold**
  out = out.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  // `code`
  out = out.replace(/`([^`]+)`/g, "<code>$1</code>");
  // bare URLs (http/https) - keep simple, no trailing punctuation
  out = out.replace(
    /\b(https?:\/\/[^\s<)]+[^\s<).,;!?])/g,
    '<a href="$1" target="_blank" rel="noopener">$1</a>'
  );
  return out;
}

function linkifySource(src) {
  // Source line shape: "Source: <title> (<url-or-text>)"
  const m = /^Source:\s*(.+?)\s*\((.+)\)\s*$/.exec(src);
  if (m) {
    const title = escapeHtml(m[1]);
    const target = m[2];
    if (/^https?:\/\//i.test(target)) {
      return `Source: ${title} (<a href="${escapeHtml(
        target
      )}" target="_blank" rel="noopener">${escapeHtml(target)}</a>)`;
    }
    return `Source: ${title} (${escapeHtml(target)})`;
  }
  return escapeHtml(src);
}

// ---------- DOM building ----------

function appendUserMessage(text) {
  const row = document.createElement("div");
  row.className = "message-row user-row";
  const bubble = document.createElement("div");
  bubble.className = "message user-message";
  const span = document.createElement("span");
  span.className = "message-text";
  span.textContent = text;
  bubble.appendChild(span);
  row.appendChild(bubble);
  chatWindow.appendChild(row);
  scrollToBottom();
  return row;
}

function appendAssistantMessage({ text, sources = [], html = null }) {
  const row = document.createElement("div");
  row.className = "message-row assistant-row";
  const bubble = document.createElement("div");
  bubble.className = "message assistant-message";
  const span = document.createElement("span");
  span.className = "message-text";
  if (html !== null) {
    span.innerHTML = html;
  } else {
    span.innerHTML = renderMarkdown(text);
  }
  bubble.appendChild(span);

  const actions = document.createElement("div");
  actions.className = "message-actions";

  const sourceLine = document.createElement("div");
  sourceLine.className = "message-source";
  if (sources && sources.length) {
    sourceLine.innerHTML = sources.map(linkifySource).join("<br>");
  } else {
    sourceLine.textContent = "";
  }

  const copyBtn = document.createElement("button");
  copyBtn.className = "copy-btn";
  copyBtn.type = "button";
  copyBtn.textContent = "Copy";
  copyBtn.addEventListener("click", () => {
    const toCopy = text ?? span.innerText;
    navigator.clipboard?.writeText(toCopy).then(
      () => {
        copyBtn.textContent = "Copied";
        copyBtn.classList.add("copied");
        setTimeout(() => {
          copyBtn.textContent = "Copy";
          copyBtn.classList.remove("copied");
        }, 1400);
      },
      () => {
        copyBtn.textContent = "Failed";
      }
    );
  });

  actions.appendChild(sourceLine);
  actions.appendChild(copyBtn);
  bubble.appendChild(actions);
  row.appendChild(bubble);
  chatWindow.appendChild(row);
  scrollToBottom();
  return row;
}

function appendTypingIndicator() {
  const row = document.createElement("div");
  row.className = "message-row assistant-row";
  const bubble = document.createElement("div");
  bubble.className = "message assistant-message";
  bubble.innerHTML =
    '<div class="typing-dots" aria-label="Assistant is typing"><span></span><span></span><span></span></div>';
  row.appendChild(bubble);
  chatWindow.appendChild(row);
  scrollToBottom();
  return row;
}

function removeWelcomeIfPresent() {
  const w = chatWindow.querySelector(".welcome-card");
  if (w) w.remove();
}

function scrollToBottom() {
  chatWindow.scrollTop = chatWindow.scrollHeight;
}

// ---------- confidence + debug panels ----------

function setConfidence(value) {
  if (value == null || value < 0) {
    confidenceFill.style.width = "0%";
    confidenceScore.textContent = "--";
    confidenceLabel.textContent = "awaiting query";
    confidenceLabel.style.color = "";
    return;
  }
  const pct = Math.round(value * 100);
  confidenceFill.style.width = pct + "%";
  confidenceScore.textContent = pct + "%";
  let label, color;
  if (pct >= 75)      { label = "high confidence";   color = "#34d399"; }
  else if (pct >= 45) { label = "medium confidence"; color = "#fbbf24"; }
  else if (pct > 0)   { label = "low confidence";    color = "#f87171"; }
  else                { label = "no match";          color = "#f87171"; }
  confidenceLabel.textContent = label;
  confidenceLabel.style.color = color;
}

function updateDebugPanel({ intent, score, source, matches }) {
  debugIntent.textContent = intent || "--";
  if (typeof score === "number") {
    debugScore.textContent = score.toFixed(2);
  } else {
    debugScore.textContent = "--";
  }
  debugSource.textContent = source || "--";
  debugMatches.textContent = Array.isArray(matches) && matches.length
    ? matches.join(" | ")
    : "--";
}

// ---------- quick prompts + categories ----------

function addQuickPrompts() {
  quickPrompts.forEach((prompt) => {
    const button = document.createElement("button");
    button.className = "quick-button";
    button.type = "button";
    button.textContent = prompt;
    button.addEventListener("click", () => {
      chatInput.value = prompt;
      autoGrow();
      sendQuery(prompt);
    });
    quickButtons.appendChild(button);
  });
}

function renderCategories(categories) {
  categoryList.innerHTML = "";
  categories.forEach((category) => {
    const item = document.createElement("li");
    item.textContent = category;
    item.title = "Click to ask about " + category;
    item.style.cursor = "pointer";
    item.addEventListener("click", () => {
      const q = "Tell me about ECIL " + category;
      chatInput.value = q;
      autoGrow();
      sendQuery(q);
    });
    categoryList.appendChild(item);
  });
}

async function fetchCategories() {
  try {
    const response = await fetch("/api/categories");
    const payload = await response.json();
    renderCategories(payload.categories || []);
    if (statCats) statCats.textContent = (payload.categories || []).length;
  } catch (error) {
    console.warn("Unable to load categories", error);
  }
}

async function fetchStats() {
  try {
    const response = await fetch("/api/health");
    const payload = await response.json();
    if (statDocs)  statDocs.textContent  = payload.documents ?? "--";
    if (statFaqs)  statFaqs.textContent  = payload.faqs ?? "--";
    if (statCats)  statCats.textContent  = payload.categories ?? "--";
  } catch (error) {
    /* ignore */
  }
}

// ---------- send query ----------

async function sendQuery(message) {
  if (!message || !message.trim()) return;
  removeWelcomeIfPresent();
  appendUserMessage(message);
  chatInput.value = "";
  autoGrow();
  setConfidence(-1);
  updateDebugPanel({ intent: "waiting", score: 0, source: "pending", matches: [] });

  const typingRow = appendTypingIndicator();
  setSendBusy(true);

  try {
    const response = await fetch("/api/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
    });
    const payload = await response.json();
    typingRow.remove();

    if (payload.error) {
      appendAssistantMessage({
        text: "I could not process that request. Please try again.",
      });
      updateDebugPanel({ intent: "error", score: 0, source: "none", matches: [] });
      setConfidence(0);
    } else {
      const text = payload.answer ?? payload.response ?? "[NO ANSWER RECEIVED]";
      appendAssistantMessage({ text, sources: payload.sources || [] });
      setConfidence(payload.confidence ?? 0);
      updateDebugPanel({
        intent: payload.intent || "unknown",
        score: typeof payload.debug?.score === "number" ? payload.debug.score : payload.confidence,
        source:
          (payload.sources || []).slice(0, 2).join(" | ") || "local knowledge base",
        matches: payload.debug?.top_matches || [],
      });
    }
  } catch (error) {
    typingRow.remove();
    appendAssistantMessage({
      text: "The local assistant is unavailable. Please try again.",
    });
    updateDebugPanel({ intent: "error", score: 0, source: "network", matches: [] });
    setConfidence(0);
    console.error("[FRONTEND_ERROR]", error);
  } finally {
    setSendBusy(false);
    chatInput.focus();
  }
}

function setSendBusy(busy) {
  sendBtn.disabled = busy;
  sendBtn.style.opacity = busy ? 0.6 : 1;
}

// Auto-grow textarea
function autoGrow() {
  chatInput.style.height = "auto";
  const next = Math.min(180, chatInput.scrollHeight);
  chatInput.style.height = next + "px";
}

// ---------- events ----------

sendBtn.addEventListener("click", () => sendQuery(chatInput.value));

chatInput.addEventListener("input", autoGrow);

chatInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    sendQuery(chatInput.value);
  }
});

clearChatBtn.addEventListener("click", () => {
  chatWindow.innerHTML = "";
  setConfidence(-1);
  updateDebugPanel({ intent: "--", score: undefined, source: "--", matches: [] });
  // Re-add the welcome card.
  const w = document.createElement("div");
  w.className = "welcome-card";
  w.innerHTML = `
    <h3>Conversation cleared.</h3>
    <p>Ask another question or pick a quick topic from the sidebar.</p>`;
  chatWindow.appendChild(w);
});

window.addEventListener("load", () => {
  addQuickPrompts();
  fetchCategories();
  fetchStats();
  setConfidence(-1);
  autoGrow();
  chatInput.focus();
});

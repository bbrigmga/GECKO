/** Grok Portfolio Replicator — frontend */

let currentRun = null;
let eventSource = null;
let sortKey = "score";
let sortAsc = false;
let firmsData = [];
let currentResultsState = null;

// --- Tabs ---
document.querySelectorAll(".tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
    document.querySelectorAll(".panel").forEach((p) => p.classList.remove("active"));
    tab.classList.add("active");
    document.getElementById(`tab-${tab.dataset.tab}`).classList.add("active");
    if (tab.dataset.tab === "history") loadHistory();
  });
});

// --- Settings ---
function updateProviderUI() {
  const provider = document.getElementById("api-provider").value;
  const label = document.getElementById("llm-key-label");
  const modelInput = document.getElementById("model");
  if (provider === "openrouter") {
    label.textContent = "OpenRouter API Key";
    if (modelInput.value === "grok-4.3") modelInput.value = "x-ai/grok-4.3";
  } else {
    label.textContent = "xAI API Key";
    if (modelInput.value === "x-ai/grok-4.3") modelInput.value = "grok-4.3";
  }
}

document.getElementById("api-provider").addEventListener("change", updateProviderUI);

async function loadSettings() {
  const res = await fetch("/api/settings");
  const data = await res.json();
  document.getElementById("api-provider").value = data.api_provider || "xai";
  document.getElementById("model").value = data.model;
  document.getElementById("max-tickers").value = data.max_tickers;
  document.getElementById("concurrency").value = data.concurrency;
  document.getElementById("stocknews-items-per-ticker").value =
    data.stocknews_items_per_ticker ?? 15;
  document.getElementById("stocknews-macro-items").value =
    data.stocknews_macro_items ?? 25;
  updateProviderUI();
  const hints = [];
  if (data.xai_api_key_set) {
    hints.push(data.api_provider === "openrouter" ? "OpenRouter key saved" : "xAI key saved");
  }
  if (data.stocknews_api_key_set) hints.push("Stock News key saved");
  document.getElementById("settings-status").textContent = hints.join(" · ") || "No API keys saved yet";
}

document.getElementById("settings-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const payload = {
    api_provider: document.getElementById("api-provider").value,
    xai_api_key: document.getElementById("xai-key").value,
    stocknews_api_key: document.getElementById("stocknews-key").value,
    model: document.getElementById("model").value,
    max_tickers: parseInt(document.getElementById("max-tickers").value, 10) || 0,
    concurrency: parseInt(document.getElementById("concurrency").value, 10) || 8,
    stocknews_items_per_ticker:
      parseInt(document.getElementById("stocknews-items-per-ticker").value, 10) || 15,
    stocknews_macro_items:
      parseInt(document.getElementById("stocknews-macro-items").value, 10) || 25,
  };
  const res = await fetch("/api/settings", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (res.ok) {
    document.getElementById("settings-status").textContent = "Settings saved.";
    document.getElementById("xai-key").value = "";
    document.getElementById("stocknews-key").value = "";
    loadSettings();
  } else {
    document.getElementById("settings-status").textContent = "Failed to save settings.";
  }
});

// --- Run ---
const btnRun = document.getElementById("btn-run");
const btnResume = document.getElementById("btn-resume");
const btnCancel = document.getElementById("btn-cancel");
const progressCard = document.getElementById("progress-card");
const progressFill = document.getElementById("progress-fill");
const progressStep = document.getElementById("progress-step");
const progressLog = document.getElementById("progress-log");
const statScored = document.getElementById("stat-scored");
const statCost = document.getElementById("stat-cost");
const statRunId = document.getElementById("stat-run-id");

function log(msg) {
  progressLog.textContent += msg + "\n";
  progressLog.scrollTop = progressLog.scrollHeight;
}

function setRunning(running) {
  btnRun.disabled = running;
  btnCancel.disabled = !running;
  progressCard.hidden = !running;
}

function connectSSE() {
  if (eventSource) eventSource.close();
  eventSource = new EventSource("/api/events");
  eventSource.onmessage = (ev) => {
    const data = JSON.parse(ev.data);
    if (data.type === "heartbeat" || data.type === "connected") return;
    handleEvent(data);
  };
  eventSource.onerror = () => {
    // Reconnect after run ends
  };
}

function handleEvent(data) {
  if (data.type === "progress") {
    progressStep.textContent = data.message || data.step;
    if (data.step === "scoring" || data.step === "scored") {
      const done = data.done || 0;
      const total = data.total || 1;
      statScored.textContent = `${done} / ${total}`;
      progressFill.style.width = `${Math.round((done / total) * 100)}%`;
    }
    if (data.cost_usd != null) {
      statCost.textContent = `$${data.cost_usd.toFixed(4)}`;
    }
    if (data.message) log(`[${data.step}] ${data.message}`);
  }
  if (data.type === "complete") {
    setRunning(false);
    log("Run complete.");
    statCost.textContent = `$${(data.total_cost_usd || 0).toFixed(4)}`;
    progressFill.style.width = "100%";
    if (data.state) showResults(data.state);
    if (eventSource) eventSource.close();
    checkResumable();
  }
  if (data.type === "error") {
    setRunning(false);
    log(`Error: ${data.error}`);
    if (eventSource) eventSource.close();
    checkResumable();
  }
  if (data.type === "cancelled") {
    setRunning(false);
    log("Run cancelled.");
    if (eventSource) eventSource.close();
    checkResumable();
  }
}

btnRun.addEventListener("click", () => startRun(false));
btnResume.addEventListener("click", () => startRun(true));

async function startRun(resume) {
  progressLog.textContent = "";
  progressFill.style.width = "0%";
  statScored.textContent = "0 / 0";
  statCost.textContent = "$0.00";
  setRunning(true);
  connectSSE();
  const url = resume ? "/api/run?resume=true" : "/api/run";
  const res = await fetch(url, { method: "POST" });
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const err = await res.json();
      detail = err.detail || JSON.stringify(err);
    } catch {
      detail = await res.text();
    }
    log(`Failed to start: ${detail}`);
    setRunning(false);
    return;
  }
  const data = await res.json();
  currentRun = data.run_id;
  statRunId.textContent = data.run_id;
  log(resume ? `Resumed run ${data.run_id}` : `Started run ${data.run_id}`);
}

async function checkResumable() {
  const res = await fetch("/api/runs");
  const runs = await res.json();
  const resumable = runs.find((r) => ["running", "cancelled"].includes(r.status) && (r.firms_scored || 0) > 0);
  btnResume.hidden = !resumable;
}

btnCancel.addEventListener("click", async () => {
  await fetch("/api/run/cancel", { method: "POST" });
  log("Cancellation requested...");
});

// --- Results ---
function scoreClass(score) {
  if (score >= 70) return "score-high";
  if (score >= 40) return "score-mid";
  return "score-low";
}

function renderScoresTable() {
  const tbody = document.querySelector("#scores-table tbody");
  const sorted = [...firmsData].sort((a, b) => {
    let av = a[sortKey], bv = b[sortKey];
    if (sortKey === "rank") { av = firmsData.indexOf(a); bv = firmsData.indexOf(b); }
    if (typeof av === "string") av = av.toLowerCase();
    if (typeof bv === "string") bv = bv.toLowerCase();
    if (av == null) return 1;
    if (bv == null) return -1;
    const cmp = av < bv ? -1 : av > bv ? 1 : 0;
    return sortAsc ? cmp : -cmp;
  });

  tbody.innerHTML = sorted.map((f, i) => `
    <tr>
      <td>${i + 1}</td>
      <td><strong>${esc(f.ticker)}</strong></td>
      <td>${esc(f.company || "")}</td>
      <td>${esc(f.industry || "")}</td>
      <td><span class="score-pill ${scoreClass(f.score)}">${f.score ?? "—"}</span></td>
      <td><button class="btn btn-secondary btn-sm" data-ticker="${esc(f.ticker)}">View</button></td>
    </tr>
  `).join("");

  tbody.querySelectorAll("button[data-ticker]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const firm = firmsData.find((f) => f.ticker === btn.dataset.ticker);
      if (firm) showModal(`${firm.ticker} — ${firm.company}`, firm.report);
    });
  });
}

document.querySelectorAll("#scores-table th[data-sort]").forEach((th) => {
  th.addEventListener("click", () => {
    const key = th.dataset.sort;
    if (sortKey === key) sortAsc = !sortAsc;
    else { sortKey = key; sortAsc = key !== "score"; }
    renderScoresTable();
  });
});

function parsePortfolioTable(text) {
  if (!text) return [];
  const lines = text.split("\n").filter((line) => line.trim().startsWith("|"));
  if (lines.length < 2) return [];

  const parseRow = (line) =>
    line
      .split("|")
      .slice(1, -1)
      .map((cell) => cell.trim());

  const headers = parseRow(lines[0]).map((h) => h.toLowerCase());
  const weightIdx = headers.findIndex((h) => h.includes("weight"));
  const instrumentIdx = headers.findIndex(
    (h) => h.includes("instrument") || h === "ticker" || h === "symbol"
  );
  const typeIdx = headers.findIndex((h) => h.includes("type"));

  const rows = [];
  for (let i = 1; i < lines.length; i++) {
    const cells = parseRow(lines[i]);
    if (!cells.length || cells.every((c) => /^[-:\s]+$/.test(c))) continue;

    const weight = (weightIdx >= 0 ? cells[weightIdx] : cells[0]) || "";
    const instrument = (instrumentIdx >= 0 ? cells[instrumentIdx] : cells[1]) || "";
    const type = typeIdx >= 0 ? cells[typeIdx] : "";
    if (!instrument || instrument.toLowerCase() === "instrument") continue;

    rows.push({
      weight,
      ticker: instrument.toUpperCase(),
      type,
    });
  }
  return rows;
}

function firmNameForTicker(ticker, firms) {
  const firm = firms?.[ticker];
  if (firm?.company) return firm.company;
  return "";
}

function csvEscape(value) {
  const s = String(value ?? "");
  if (/[",\n\r]/.test(s)) return `"${s.replace(/"/g, '""')}"`;
  return s;
}

function downloadCsv(filename, headerLabels, rows) {
  const lines = [headerLabels.map((h) => csvEscape(h.label)).join(",")];
  for (const row of rows) {
    lines.push(headerLabels.map((h) => csvEscape(row[h.key])).join(","));
  }
  const blob = new Blob(["\ufeff" + lines.join("\r\n")], {
    type: "text/csv;charset=utf-8;",
  });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = filename;
  link.click();
  URL.revokeObjectURL(link.href);
}

function exportPortfolioToExcel() {
  if (!currentResultsState?.portfolio) {
    alert("No portfolio to export.");
    return;
  }

  const holdings = parsePortfolioTable(currentResultsState.portfolio);
  if (!holdings.length) {
    alert("Could not find a portfolio table in the results.");
    return;
  }

  const firms = currentResultsState.firms || {};
  const rows = holdings.map((row) => ({
    ticker: row.ticker,
    company: firmNameForTicker(row.ticker, firms) || (row.type?.toLowerCase() === "etf" ? row.ticker : ""),
    weight: row.weight,
    type: row.type,
  }));

  const runId = currentResultsState.run_id || "portfolio";
  downloadCsv(`${runId}_portfolio.csv`, [
    { key: "ticker", label: "Ticker" },
    { key: "company", label: "Company" },
    { key: "weight", label: "Weight" },
    { key: "type", label: "Type" },
  ], rows);
}

function showResults(state) {
  currentResultsState = state;
  document.getElementById("results-empty").hidden = true;
  document.getElementById("results-content").hidden = false;
  document.getElementById("portfolio-output").textContent = state.portfolio || "(No portfolio generated)";
  document.getElementById("macro-output").textContent = state.macro_report || "(No macro report)";
  firmsData = Object.values(state.firms || {}).filter((f) => f.score != null);
  firmsData.sort((a, b) => b.score - a.score);
  document.getElementById("scores-count").textContent = firmsData.length;
  const exportBtn = document.getElementById("btn-export-portfolio");
  exportBtn.hidden = !parsePortfolioTable(state.portfolio || "").length;
  renderScoresTable();
  document.querySelector('.tab[data-tab="results"]').click();
}

document.getElementById("btn-export-portfolio").addEventListener("click", exportPortfolioToExcel);

// --- History ---
async function loadHistory() {
  const res = await fetch("/api/runs");
  const runs = await res.json();
  const list = document.getElementById("history-list");
  if (!runs.length) {
    list.innerHTML = '<p class="empty-state">No past runs yet.</p>';
    return;
  }
  list.innerHTML = runs.map((r) => {
    const runId = r.run_id || "";
    const errLine = r.error ? `<p class="history-error">${esc(r.error)}</p>` : "";
    return `
    <div class="history-item">
      <div class="history-meta">
        <h4>${esc(runId)}</h4>
        <p>${esc(r.started_at || "")} · ${r.firms_scored || 0} firms · $${(r.total_cost_usd || 0).toFixed(4)}</p>
        ${errLine}
      </div>
      <span class="status-badge status-${esc(r.status || "unknown")}">${esc(r.status || "unknown")}</span>
      <button class="btn btn-secondary" data-run-id="${esc(runId)}" ${runId ? "" : "disabled"}>Load</button>
    </div>
  `;
  }).join("");

  list.querySelectorAll("button[data-run-id]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const runId = btn.dataset.runId;
      if (!runId) return;
      const res = await fetch(`/api/runs/${encodeURIComponent(runId)}`);
      if (res.ok) showResults(await res.json());
    });
  });
}

// --- Modal ---
const modal = document.getElementById("modal");
document.getElementById("modal-close").addEventListener("click", () => { modal.hidden = true; });
modal.addEventListener("click", (e) => { if (e.target === modal) modal.hidden = true; });

function showModal(title, body) {
  document.getElementById("modal-title").textContent = title;
  document.getElementById("modal-body").textContent = body;
  modal.hidden = false;
}

function esc(s) {
  const d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}

// --- Init ---
async function init() {
  try {
    await loadSettings();
    await checkResumable();
    const statusRes = await fetch("/api/status");
    const status = await statusRes.json();
    if (status.is_running) {
      setRunning(true);
      statRunId.textContent = status.current_run_id || "—";
      connectSSE();
    }
  } catch (err) {
    console.error("Init failed:", err);
  }
}
init();

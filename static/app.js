/** Grok PM — frontend */

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
function normalizeModel(model) {
  return (model || "grok-4.3").replace(/^x-ai\//, "");
}

function updateProviderUI() {
  const provider = document.getElementById("api-provider").value;
  const label = document.getElementById("llm-key-label");
  label.textContent = provider === "openrouter" ? "OpenRouter API Key" : "xAI API Key";
}

document.getElementById("api-provider").addEventListener("change", updateProviderUI);

function formatMaxTickers(value) {
  const n = parseInt(value, 10);
  if (!n) return "full S&P 500";
  return `${n} largest by market cap`;
}

function formatMarketCapUsd(value) {
  const n = Number(value);
  if (!n) return "$0";
  if (n >= 1e12) return `$${(n / 1e12).toFixed(1)}T`;
  if (n >= 1e9) return `$${Math.round(n / 1e9)}B`;
  if (n >= 1e6) return `$${Math.round(n / 1e6)}M`;
  return `$${n.toLocaleString()}`;
}

function renderSavedSettingsSummary(data) {
  const el = document.getElementById("settings-saved-summary");
  if (!el) return;
  const provider = data.api_provider === "openrouter" ? "OpenRouter" : "xAI";
  const compliance = data.compliance_mode
    ? ` · compliance ${formatMarketCapUsd(data.compliance_min_market_cap_usd)} floor, top ${data.compliance_stock_candidate_count} stocks`
    : "";
  el.textContent =
    `Saved: ${formatMaxTickers(data.max_tickers)} · concurrency ${data.concurrency} · ` +
    `${normalizeModel(data.model)} (${provider})${compliance}`;
}

async function loadSettings() {
  const res = await fetch("/api/settings");
  const data = await res.json();
  document.getElementById("api-provider").value = data.api_provider || "xai";
  document.getElementById("model").value = normalizeModel(data.model);
  document.getElementById("max-tickers").value = data.max_tickers;
  document.getElementById("concurrency").value = data.concurrency;
  document.getElementById("stocknews-items-per-ticker").value =
    data.stocknews_items_per_ticker ?? 15;
  document.getElementById("stocknews-macro-items").value =
    data.stocknews_macro_items ?? 25;
  document.getElementById("compliance-mode").checked = !!data.compliance_mode;
  document.getElementById("compliance-min-cap").value =
    data.compliance_min_market_cap_usd ?? 200000000000;
  document.getElementById("compliance-candidate-count").value =
    data.compliance_stock_candidate_count ?? 30;
  updateProviderUI();
  renderSavedSettingsSummary(data);
  const hints = [];
  if (data.xai_api_key_set) {
    hints.push(data.api_provider === "openrouter" ? "OpenRouter key saved" : "xAI key saved");
  }
  if (data.stocknews_api_key_set) hints.push("Stock News key saved");
  document.getElementById("settings-status").textContent = hints.join(" · ") || "No API keys saved yet";
}

document.getElementById("settings-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  await saveSettings({ fromKeysForm: true });
});

document.getElementById("run-options-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  await saveSettings({ fromKeysForm: false });
});

async function saveSettings({ fromKeysForm }) {
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
    compliance_mode: document.getElementById("compliance-mode").checked,
    compliance_min_market_cap_usd:
      parseInt(document.getElementById("compliance-min-cap").value, 10) || 200000000000,
    compliance_stock_candidate_count:
      parseInt(document.getElementById("compliance-candidate-count").value, 10) || 30,
  };
  const res = await fetch("/api/settings", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const statusEl = document.getElementById("settings-status");
  const summaryEl = document.getElementById("settings-saved-summary");
  if (res.ok) {
    if (fromKeysForm) {
      statusEl.textContent = "Settings saved.";
      document.getElementById("xai-key").value = "";
      document.getElementById("stocknews-key").value = "";
    } else if (summaryEl) {
      summaryEl.textContent = "Settings saved.";
    }
    loadSettings();
  } else if (fromKeysForm) {
    statusEl.textContent = "Failed to save settings.";
  } else if (summaryEl) {
    summaryEl.textContent = "Failed to save settings.";
  }
}

// --- Run ---
const btnRun = document.getElementById("btn-run");
const btnResume = document.getElementById("btn-resume");
const btnPortfolio = document.getElementById("btn-portfolio");
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
  btnPortfolio.disabled = running;
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
    if (data.step === "scoring" || data.step === "scored" || data.step === "grok") {
      const done = data.done || 0;
      const total = data.total || 1;
      statScored.textContent = `${done} / ${total}`;
      if (data.step === "scoring" && total > 1) {
        progressFill.style.width = `${Math.round((done / total) * 100)}%`;
      }
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
btnPortfolio.addEventListener("click", () => startPortfolioRun());

function portfolioSourceRunId() {
  if (currentResultsState?.top30?.length && currentResultsState.run_id) {
    return currentResultsState.run_id;
  }
  return null;
}

async function startPortfolioRun() {
  progressLog.textContent = "";
  progressFill.style.width = "0%";
  statScored.textContent = "—";
  statCost.textContent = "$0.00";
  setRunning(true);
  connectSSE();

  const sourceRunId = portfolioSourceRunId();
  const url = sourceRunId
    ? `/api/run/portfolio?source_run_id=${encodeURIComponent(sourceRunId)}`
    : "/api/run/portfolio";
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
  log(
    `Portfolio-only run ${data.run_id} (model: ${data.model}, source: ${data.source_run_id})`
  );
  progressFill.style.width = "50%";
}

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
  if (resume) {
    if (!data.resumed) {
      log("Resume failed — no partial run found. Start a new run instead.");
      setRunning(false);
      return;
    }
    const already = data.already_scored ?? 0;
    const pending = data.pending ?? 0;
    const total = data.total ?? already + pending;
    statScored.textContent = `${already} / ${total}`;
    progressFill.style.width = `${Math.round((already / Math.max(total, 1)) * 100)}%`;
    log(
      `Resumed ${data.run_id}: ${already}/${total} scored, ${pending} to retry. ` +
        `Watch for [grok] lines — those are OpenRouter calls.`
    );
  } else {
    log(`Started run ${data.run_id}`);
  }
}

async function checkResumable() {
  const res = await fetch("/api/runs");
  const runs = await res.json();
  const resumable = runs.find((r) => r.resumable);
  if (resumable) {
    const scored = resumable.firms_scored || 0;
    const total = resumable.universe_count || resumable.firms_attempted || "?";
    btnResume.textContent = `Resume Run (${scored}/${total} scored)`;
    btnResume.hidden = false;
  } else {
    btnResume.textContent = "Resume Interrupted Run";
    btnResume.hidden = true;
  }
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

function parseMarkdownTableRow(line) {
  return line
    .split("|")
    .slice(1, -1)
    .map((cell) => cell.trim());
}

function parsePortfolioTable(text) {
  if (!text) return [];
  const lines = text.split("\n").filter((line) => line.trim().startsWith("|"));
  if (lines.length < 2) return [];

  const headers = parseMarkdownTableRow(lines[0]).map((h) => h.toLowerCase());
  const weightIdx = headers.findIndex((h) => h.includes("weight"));
  const instrumentIdx = headers.findIndex(
    (h) => h.includes("instrument") || h === "ticker" || h === "symbol"
  );
  const typeIdx = headers.findIndex((h) => h.includes("type"));

  const rows = [];
  for (let i = 1; i < lines.length; i++) {
    const cells = parseMarkdownTableRow(lines[i]);
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

function stripMdInline(text) {
  return String(text || "")
    .replace(/\*\*(.*?)\*\*/g, "$1")
    .replace(/__(.*?)__/g, "$1")
    .replace(/`(.*?)`/g, "$1")
    .trim();
}

/** Split portfolio markdown into Word-doc-like sections. */
function parsePortfolioReport(text) {
  const raw = String(text || "").replace(/\r\n/g, "\n").trim();
  if (!raw) {
    return { title: "15-Asset Portfolio", intro: "", holdings: [], rationale: "" };
  }

  const lines = raw.split("\n");
  const tableStart = lines.findIndex((line) => line.trim().startsWith("|"));
  const before = (tableStart >= 0 ? lines.slice(0, tableStart) : lines).join("\n").trim();
  let after = "";
  const holdings = [];

  if (tableStart >= 0) {
    const tableLines = [];
    let i = tableStart;
    for (; i < lines.length; i++) {
      if (!lines[i].trim().startsWith("|")) break;
      tableLines.push(lines[i]);
    }
    after = lines.slice(i).join("\n").trim();

    if (tableLines.length >= 2) {
      const headers = parseMarkdownTableRow(tableLines[0]).map((h) => h.toLowerCase());
      const idx = (names) => headers.findIndex((h) => names.some((n) => h.includes(n)));
      const weightIdx = idx(["weight"]);
      const instrumentIdx = idx(["instrument", "ticker", "symbol"]);
      const typeIdx = idx(["type"]);
      const thesisIdx = idx(["thesis"]);
      const edgeIdx = idx(["edge"]);
      const riskIdx = idx(["risk"]);

      for (let r = 1; r < tableLines.length; r++) {
        const cells = parseMarkdownTableRow(tableLines[r]);
        if (!cells.length || cells.every((c) => /^[-:\s]+$/.test(c))) continue;
        const instrument = (instrumentIdx >= 0 ? cells[instrumentIdx] : cells[1]) || "";
        if (!instrument || instrument.toLowerCase() === "instrument") continue;
        holdings.push({
          weight: (weightIdx >= 0 ? cells[weightIdx] : cells[0]) || "",
          instrument: instrument.toUpperCase(),
          type: typeIdx >= 0 ? cells[typeIdx] || "" : "",
          thesis: thesisIdx >= 0 ? cells[thesisIdx] || "" : "",
          edge: edgeIdx >= 0 ? cells[edgeIdx] || "" : "",
          risk: riskIdx >= 0 ? cells[riskIdx] || "" : "",
        });
      }
    }
  }

  const beforeLines = before.split("\n").map((l) => l.trim()).filter(Boolean);
  let title = "15-Asset Portfolio";
  let introStart = 0;
  if (beforeLines.length) {
    title = stripMdInline(beforeLines[0]);
    introStart = 1;
  }
  const intro = beforeLines.slice(introStart).map(stripMdInline).join("\n\n");
  const rationale = after
    .split("\n")
    .map((l) => stripMdInline(l.replace(/^[-*]\s+/, "• ")))
    .filter(Boolean)
    .filter((l) => !/^construction rationale/i.test(l))
    .join("\n");

  return { title, intro, holdings, rationale };
}

function firmNameForTicker(ticker, stateOrFirms) {
  const firms = stateOrFirms?.firms ?? stateOrFirms;
  const firm = firms?.[ticker];
  if (firm?.company) return firm.company;
  const fromTop30 = (stateOrFirms?.top30 || []).find((f) => f.ticker === ticker);
  return fromTop30?.company || "";
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

  const runId = currentResultsState.run_id || "portfolio";
  const rows = holdings.map((row) => ({
    run_id: runId,
    ticker: row.ticker,
    company: firmNameForTicker(row.ticker, currentResultsState) || (row.type?.toLowerCase() === "etf" ? row.ticker : ""),
    weight: row.weight,
    type: row.type,
  }));

  downloadCsv(`${runId}_portfolio.csv`, [
    { key: "run_id", label: "Run ID" },
    { key: "ticker", label: "Ticker" },
    { key: "company", label: "Company" },
    { key: "weight", label: "Weight" },
    { key: "type", label: "Type" },
  ], rows);
}

function paragraphsToHtml(text) {
  return String(text || "")
    .split(/\n{2,}/)
    .map((block) => block.trim())
    .filter(Boolean)
    .map((block) => {
      const lines = block.split("\n").map((l) => esc(l)).join("<br>");
      return `<p>${lines}</p>`;
    })
    .join("\n");
}

function exportPortfolioReportPdf() {
  if (!currentResultsState?.portfolio) {
    alert("No portfolio to export.");
    return;
  }

  const report = parsePortfolioReport(currentResultsState.portfolio);
  if (!report.holdings.length) {
    alert("Could not find a portfolio table in the results.");
    return;
  }

  const runId = currentResultsState.run_id || "portfolio";
  const holdingsHtml = report.holdings
    .map(
      (row) => `<tr>
      <td>${esc(row.weight)}</td>
      <td><strong>${esc(row.instrument)}</strong></td>
      <td>${esc(row.type)}</td>
      <td>${esc(row.thesis)}</td>
      <td>${esc(row.edge)}</td>
      <td>${esc(row.risk)}</td>
    </tr>`
    )
    .join("\n");

  const html = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>${esc(runId)}_portfolio_report</title>
  <style>
    @page { size: landscape; margin: 0.35in; }
    * { box-sizing: border-box; }
    body {
      font-family: "Calibri", "Segoe UI", Arial, sans-serif;
      color: #1a1a1a;
      font-size: 8pt;
      line-height: 1.2;
      margin: 0;
      padding: 0.2in;
    }
    h1 {
      font-size: 14pt;
      margin: 0 0 0.05em;
      font-weight: 700;
    }
    .subtitle {
      font-size: 9pt;
      color: #333;
      margin: 0 0 0.35em;
    }
    .meta {
      font-size: 7.5pt;
      color: #666;
      margin-bottom: 0.4em;
    }
    h2 {
      font-size: 9.5pt;
      margin: 0.55em 0 0.2em;
      border-bottom: 1px solid #ccc;
      padding-bottom: 0.1em;
    }
    p { margin: 0 0 0.35em; }
    table {
      width: 100%;
      border-collapse: collapse;
      margin: 0.3em 0 0.45em;
      font-size: 6.5pt;
      line-height: 1.15;
    }
    th, td {
      border: 1px solid #bbb;
      padding: 2px 4px;
      vertical-align: top;
      text-align: left;
    }
    th {
      background: #f0f0f0;
      font-weight: 700;
    }
    td:nth-child(1) { white-space: nowrap; width: 3.5em; }
    td:nth-child(2) { white-space: nowrap; width: 4.5em; }
    td:nth-child(3) { white-space: nowrap; width: 3.5em; }
    .no-print { margin: 0 0 1em; }
    @media print {
      .no-print { display: none !important; }
      body { padding: 0; }
    }
  </style>
</head>
<body>
  <p class="no-print">Use your browser’s print dialog → <strong>Save as PDF</strong>.</p>
  <h1>15-Asset Portfolio</h1>
  <p class="subtitle">${esc(report.title)}</p>
  <p class="meta">Run ${esc(runId)}</p>
  ${paragraphsToHtml(report.intro)}
  <table>
    <thead>
      <tr>
        <th>Weight</th>
        <th>Instrument</th>
        <th>Type</th>
        <th>Thesis</th>
        <th>Edge</th>
        <th>Risk</th>
      </tr>
    </thead>
    <tbody>
      ${holdingsHtml}
    </tbody>
  </table>
  ${report.rationale ? `<h2>Construction rationale (regime fit)</h2>${paragraphsToHtml(report.rationale)}` : ""}
</body>
</html>`;

  const win = window.open("", "_blank");
  if (!win) {
    alert("Pop-up blocked. Allow pop-ups for this site to export the PDF report.");
    return;
  }
  win.document.open();
  win.document.write(html);
  win.document.close();
  // ponytail: browser print→PDF; avoid PDF libs until we need server-side files
  setTimeout(() => {
    win.focus();
    win.print();
  }, 250);
}

function runModeLabel(state) {
  if (state.mode !== "portfolio_only") return "";
  const source = state.source_run_id ? ` from ${state.source_run_id}` : "";
  const model = state.settings?.model ? ` · ${state.settings.model}` : "";
  return `Portfolio only${source}${model}`;
}

function renderComplianceBanner(state) {
  const banner = document.getElementById("compliance-banner");
  if (!banner) return;
  const comp = state.compliance;
  if (!comp?.enabled) {
    banner.hidden = true;
    banner.innerHTML = "";
    return;
  }

  const cap = formatMarketCapUsd(comp.min_market_cap_usd);
  const count = comp.stock_candidate_count ?? comp.candidate_tickers?.length ?? "—";
  const universe = comp.eligible_universe_count != null
    ? `${comp.eligible_universe_count} stocks scored in universe`
    : null;
  const status = comp.portfolio_status;
  const issues = comp.portfolio_issues || [];

  let statusLine = "Compliance screening enabled.";
  if (status === "compliant") {
    statusLine = "Portfolio passed compliance validation.";
    banner.className = "compliance-banner compliant";
  } else if (status === "non_compliant") {
    statusLine = "Portfolio may violate compliance rules — review before trading.";
    banner.className = "compliance-banner non-compliant";
  } else {
    banner.className = "compliance-banner";
  }

  const parts = [
    `<div class="compliance-title">${esc(statusLine)}</div>`,
    `<div>${esc(cap)} minimum market cap · top ${esc(String(count))} stock candidates` +
      (universe ? ` · ${esc(universe)}` : "") +
      `</div>`,
  ];
  if (issues.length) {
    parts.push(
      `<ul>${issues.map((issue) => `<li>${esc(issue)}</li>`).join("")}</ul>`
    );
  }
  if (comp.disclaimer) {
    parts.push(`<div class="field-hint">${esc(comp.disclaimer)}</div>`);
  }
  banner.innerHTML = parts.join("\n");
  banner.hidden = false;
}

function showResults(state) {
  currentResultsState = state;
  document.getElementById("results-empty").hidden = true;
  document.getElementById("results-content").hidden = false;
  const runLabel = document.getElementById("results-run-label");
  const label = runModeLabel(state);
  if (label) {
    runLabel.textContent = label;
    runLabel.hidden = false;
  } else {
    runLabel.hidden = true;
  }
  renderComplianceBanner(state);
  document.getElementById("portfolio-output").textContent = state.portfolio || "(No portfolio generated)";
  document.getElementById("macro-output").textContent = state.macro_report || "(No macro report)";
  firmsData = state.allocation_candidates?.length
    ? [...state.allocation_candidates]
    : state.top30?.length
      ? [...state.top30]
      : Object.values(state.firms || {}).filter((f) => f.score != null);
  firmsData.sort((a, b) => b.score - a.score);
  document.getElementById("scores-count").textContent = firmsData.length;
  const hasPortfolio = !!parsePortfolioTable(state.portfolio || "").length;
  const excelBtn = document.getElementById("btn-export-portfolio");
  const pdfBtn = document.getElementById("btn-export-pdf");
  if (excelBtn) excelBtn.hidden = !hasPortfolio;
  if (pdfBtn) pdfBtn.hidden = !hasPortfolio;
  renderScoresTable();
  document.querySelector('.tab[data-tab="results"]').click();
}

document.getElementById("btn-export-portfolio").addEventListener("click", exportPortfolioToExcel);
document.getElementById("btn-export-pdf").addEventListener("click", exportPortfolioReportPdf);

// --- History favorites ---
const FAVORITES_KEY = "gecko-favorite-runs";

function getFavoriteRuns() {
  try {
    const raw = localStorage.getItem(FAVORITES_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed.filter((id) => typeof id === "string") : [];
  } catch {
    return [];
  }
}

function toggleFavoriteRun(runId) {
  if (!runId) return false;
  const favorites = getFavoriteRuns();
  const idx = favorites.indexOf(runId);
  if (idx >= 0) favorites.splice(idx, 1);
  else favorites.push(runId);
  localStorage.setItem(FAVORITES_KEY, JSON.stringify(favorites));
  return favorites.includes(runId);
}

// --- History ---
async function loadHistory() {
  const res = await fetch("/api/runs");
  const runs = await res.json();
  const list = document.getElementById("history-list");
  if (!runs.length) {
    list.innerHTML = '<p class="empty-state">No past runs yet.</p>';
    return;
  }

  const favorites = new Set(getFavoriteRuns());
  const sorted = [...runs].sort((a, b) => {
    const aFav = favorites.has(a.run_id) ? 1 : 0;
    const bFav = favorites.has(b.run_id) ? 1 : 0;
    return bFav - aFav;
  });

  list.innerHTML = sorted.map((r) => {
    const runId = r.run_id || "";
    const favorited = favorites.has(runId);
    const errLine = r.error ? `<p class="history-error">${esc(r.error)}</p>` : "";
    const modeLine =
      r.mode === "portfolio_only"
        ? `<p class="history-mode">Portfolio only · from ${esc(r.source_run_id || "unknown")}</p>`
        : "";
    return `
    <div class="history-item${favorited ? " favorited" : ""}">
      <button type="button" class="btn-star${favorited ? " is-favorite" : ""}" data-star-id="${esc(runId)}"
        aria-label="${favorited ? "Unfavorite" : "Favorite"} run" title="${favorited ? "Remove favorite" : "Add to favorites"}"
        ${runId ? "" : "disabled"}>${favorited ? "★" : "☆"}</button>
      <div class="history-meta">
        <h4>${esc(runId)}</h4>
        <p>${esc(r.started_at || "")} · ${r.firms_scored || 0} firms · $${(r.total_cost_usd || 0).toFixed(4)}</p>
        ${modeLine}
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

  list.querySelectorAll("button[data-star-id]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const runId = btn.dataset.starId;
      if (!runId) return;
      toggleFavoriteRun(runId);
      loadHistory();
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

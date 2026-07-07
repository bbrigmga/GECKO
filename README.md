# Grok Portfolio Replicator

A local web app that replicates the monthly investment pipeline described in **The Grok Portfolio White Paper**:

1. **Macro analysis** — general market news (Stock News API), Wikipedia current events, and a Grok macro report with live web search (Exhibit 2D)
2. **Firm scoring** — every S&P 500 company scored 1–100 via Grok using financials (Yahoo Finance), firm news, and the macro report (Exhibit 1)
3. **Top 30 pre-selection** — highest-scoring firms
4. **Portfolio allocation** — Grok builds a 15-asset monthly portfolio with weights, thesis, edge, and risk (Exhibit 2E)

## Quick start

```bash
cd "u:\Code Hero\moon-machine-lite"
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8765
```

Or in PowerShell from the project folder:

```powershell
.\run.bat
```

Open **http://localhost:8765**, go to **Settings**, and enter:

- **xAI API key** — from [console.x.ai](https://console.x.ai), **or**
- **OpenRouter API key** — from [openrouter.ai](https://openrouter.ai) (select **OpenRouter** as provider in Settings; model `x-ai/grok-4.3`)
- **Stock News API key** — from [stocknewsapi.com](https://stocknewsapi.com)

Then click **Run Monthly Analysis**.

## Options

| Setting | Default | Description |
|---------|---------|-------------|
| Model | `grok-4.3` | xAI model for all Grok calls |
| Max Tickers | `0` | `0` = full S&P 500; set to e.g. `10` for cheap test runs |
| Concurrency | `8` | Parallel firm scoring requests |
| News articles per ticker | `15` | Articles returned per ticker (max 50). **Does not change API call count** — still 1 call per ticker |
| Macro news articles | `25` | Articles for general market news (1 API call per run) |

### Stock News API usage

Stock News bills by **HTTP request**, not by articles returned. Each full run uses roughly:

**1** (macro) **+ N** (one per ticker scored)

Examples on a Basic plan (~20,000 calls/month):

| Max tickers | Calls per run | Full runs/month |
|-------------|---------------|-----------------|
| 10 | ~11 | ~1,800 |
| 50 | ~51 | ~390 |
| 503 (full S&P) | ~504 | ~39 |

Without a `date` filter (Basic plan), we still make only **one call per ticker** — lowering article count trims Grok prompt size, not Stock News quota. Use **Max Tickers** to control monthly API burn.

## Cost & runtime

A full S&P 500 run (~503 Grok calls + macro + allocation) typically takes **20–40 minutes** and costs a **few dollars** in xAI API usage. Progress and running cost are shown live in the UI. Each run is checkpointed to `runs/` so you can resume after interruption (already-scored firms are skipped).

## Project layout

```
app/
  main.py          # FastAPI server
  pipeline.py      # Monthly pipeline orchestration
  grok.py          # xAI client
  prompts.py       # White paper exhibit prompts
  config.py        # Settings (.env)
  sources/
    stocknews.py   # Stock News API
    yahoo.py       # yfinance financials + S&P 500 list
    wikipedia.py   # Current events pages
static/            # Dashboard UI
runs/              # Saved monthly runs (gitignored)
```

## Data sources (per white paper)

- **News**: [stocknewsapi.com](https://stocknewsapi.com) — firm and general market news, past 7 days
- **Financials**: [finance.yahoo.com](https://finance.yahoo.com) via `yfinance` — Exhibit 2B variables
- **Macro context**: Wikipedia current-events pages + Stock News general market news
- **AI**: [xAI Grok API](https://docs.x.ai) — scoring, macro report (with web/X search), portfolio allocation

"""Gecko PM monthly pipeline orchestration."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from app.config import RUNS_DIR, Settings, load_settings
from app.grok import GrokClient, parse_score
from app.sources.stocknews import StockNewsClient
from app.sources.wikipedia import fetch_wikipedia_context
from app.sources.yahoo import (
    fetch_sp500_tickers,
    format_financials,
    get_company_name,
    get_industry,
    get_ticker_info,
)

ProgressCallback = Callable[[dict[str, Any]], Any]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_dir(run_id: str) -> Path:
    month = run_id[:7]  # YYYY-MM
    return RUNS_DIR / month / run_id


def _save_run(run_id: str, data: dict[str, Any]) -> None:
    path = _run_dir(run_id)
    path.mkdir(parents=True, exist_ok=True)
    (path / "run.json").write_text(json.dumps(data, indent=2), encoding="utf-8")


def _safe_settings(settings: Settings) -> dict[str, Any]:
    data = settings.model_dump()
    if data.get("xai_api_key"):
        data["xai_api_key"] = "***"
    if data.get("stocknews_api_key"):
        data["stocknews_api_key"] = "***"
    return data


def _redact_run(data: dict[str, Any]) -> dict[str, Any]:
    """Remove secrets before returning run data to the client."""
    out = dict(data)
    settings = out.get("settings")
    if isinstance(settings, dict):
        redacted = dict(settings)
        if redacted.get("xai_api_key"):
            redacted["xai_api_key"] = "***"
        if redacted.get("stocknews_api_key"):
            redacted["stocknews_api_key"] = "***"
        out["settings"] = redacted
    return out


def load_run(run_id: str) -> dict[str, Any] | None:
    file = _run_dir(run_id) / "run.json"
    if not file.exists():
        return None
    return json.loads(file.read_text(encoding="utf-8"))


def list_runs() -> list[dict[str, Any]]:
    if not RUNS_DIR.exists():
        return []
    runs: list[dict[str, Any]] = []
    for month_dir in sorted(RUNS_DIR.iterdir(), reverse=True):
        if not month_dir.is_dir():
            continue
        for run_dir in sorted(month_dir.iterdir(), reverse=True):
            file = run_dir / "run.json"
            if file.exists():
                data = json.loads(file.read_text(encoding="utf-8"))
                runs.append(
                    {
                        "run_id": data.get("run_id", run_dir.name),
                        "status": data.get("status"),
                        "started_at": data.get("started_at"),
                        "completed_at": data.get("completed_at"),
                        "total_cost_usd": data.get("total_cost_usd", 0),
                        "firms_scored": sum(
                            1
                            for f in data.get("firms", {}).values()
                            if f.get("score") is not None
                        ),
                        "firms_attempted": len(data.get("firms", {})),
                        "portfolio_preview": (data.get("portfolio") or "")[:200],
                        "error": data.get("error"),
                    }
                )
    return runs


class PipelineRunner:
    def __init__(self) -> None:
        self._task: asyncio.Task[None] | None = None
        self._cancel = asyncio.Event()
        self._listeners: list[asyncio.Queue[dict[str, Any]]] = []
        self.current_run_id: str | None = None
        self.is_running = False

    def subscribe(self) -> asyncio.Queue[dict[str, Any]]:
        q: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._listeners.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue[dict[str, Any]]) -> None:
        if q in self._listeners:
            self._listeners.remove(q)

    async def _emit(self, event: dict[str, Any]) -> None:
        for q in list(self._listeners):
            await q.put(event)

    def cancel(self) -> None:
        self._cancel.set()

    def find_resumable_run(self) -> str | None:
        for entry in list_runs():
            if entry.get("status") in ("running", "cancelled") and entry.get("firms_scored", 0) > 0:
                return entry["run_id"]
        return None

    async def start(self, settings: Settings | None = None, resume_run_id: str | None = None) -> str:
        if self.is_running:
            raise RuntimeError("A run is already in progress")
        settings = settings or load_settings()
        if not settings.xai_api_key:
            raise ValueError("LLM API key is required (xAI or OpenRouter)")
        if not settings.stocknews_api_key:
            raise ValueError("Stock News API key is required")

        run_id = resume_run_id or datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S")
        self.current_run_id = run_id
        self._cancel.clear()
        self.is_running = True

        self._task = asyncio.create_task(self._run_pipeline(run_id, settings, resume=bool(resume_run_id)))
        return run_id

    async def _run_pipeline(self, run_id: str, settings: Settings, resume: bool = False) -> None:
        if resume:
            loaded = load_run(run_id)
            if not loaded:
                raise ValueError(f"Run {run_id} not found")
            state = loaded
            state["status"] = "running"
            state["error"] = None
            _save_run(run_id, state)
        else:
            state = {
                "run_id": run_id,
                "status": "running",
                "started_at": _utc_now(),
                "settings": _safe_settings(settings),
                "macro_news_raw": "",
                "wikipedia_context": "",
                "macro_report": "",
                "firms": {},
                "top30": [],
                "portfolio": "",
                "total_cost_usd": 0.0,
                "error": None,
            }
            _save_run(run_id, state)

        async def progress(step: str, **extra: Any) -> None:
            payload = {"type": "progress", "step": step, "run_id": run_id, **extra}
            await self._emit(payload)

        try:
            stocknews = StockNewsClient(settings.stocknews_api_key)
            grok = GrokClient(
                settings.xai_api_key,
                settings.model,
                provider=settings.api_provider,
            )
            if resume:
                grok.total_cost_usd = float(state.get("total_cost_usd", 0.0))

            # Step 1 — macro news inputs
            if not state.get("macro_news_raw"):
                await progress("macro_news", message="Fetching general market news...")
                general_news = await stocknews.get_general_market_news(
                    items=settings.stocknews_macro_items
                )
                state["macro_news_raw"] = general_news
                _save_run(run_id, state)
            else:
                general_news = state["macro_news_raw"]

            if not state.get("wikipedia_context"):
                await progress("wikipedia", message="Fetching Wikipedia current events...")
                wiki_ctx = await fetch_wikipedia_context()
                state["wikipedia_context"] = wiki_ctx
                _save_run(run_id, state)
            else:
                wiki_ctx = state["wikipedia_context"]

            macro_context = (
                f"General market news (past week):\n{general_news}\n\n"
                f"Wikipedia current events:\n{wiki_ctx}"
            )

            # Step 2 — macro report (Exhibit 2D)
            if not state.get("macro_report"):
                await progress("macro_report", message="Generating macro report with Grok...")
                if self._cancel.is_set():
                    raise asyncio.CancelledError()
                macro_result = grok.generate_macro_report(macro_context)
                state["macro_report"] = macro_result.text
                state["total_cost_usd"] = grok.total_cost_usd
                _save_run(run_id, state)
                await progress(
                    "macro_report_done",
                    message="Macro report complete",
                    cost_usd=grok.total_cost_usd,
                )

            # Step 3 — S&P 500 universe
            await progress("universe", message="Loading S&P 500 constituents...")
            universe = fetch_sp500_tickers()
            if settings.max_tickers > 0:
                universe = universe[: settings.max_tickers]
            total = len(universe)
            state["universe_count"] = total
            _save_run(run_id, state)

            macro_for_firms = state["macro_report"] or macro_context
            sem = asyncio.Semaphore(settings.concurrency)
            scored_lock = asyncio.Lock()

            async def score_one(entry: dict[str, str], index: int) -> None:
                if self._cancel.is_set():
                    return
                ticker = entry["ticker"]
                if ticker in state["firms"] and state["firms"][ticker].get("score") is not None:
                    return

                async with sem:
                    if self._cancel.is_set():
                        return
                    await progress(
                        "scoring",
                        ticker=ticker,
                        index=index + 1,
                        total=total,
                        message=f"Scoring {ticker} ({index + 1}/{total})",
                    )
                    try:
                        info = await asyncio.to_thread(get_ticker_info, ticker)
                        company = get_company_name(info, ticker)
                        industry = get_industry(info)
                        financials = format_financials(info)
                        news = await stocknews.get_ticker_news(
                            ticker, items=settings.stocknews_items_per_ticker
                        )

                        result = await asyncio.to_thread(
                            grok.score_firm,
                            ticker,
                            company,
                            industry,
                            macro_for_firms,
                            financials,
                            news,
                        )
                        score = parse_score(result.text)
                        firm_data = {
                            "ticker": ticker,
                            "company": company,
                            "industry": industry,
                            "report": result.text,
                            "score": score,
                            "cost_usd": result.cost_usd,
                        }
                    except Exception as exc:  # noqa: BLE001
                        firm_data = {
                            "ticker": ticker,
                            "company": entry.get("name", ticker),
                            "industry": entry.get("sector", "Unknown"),
                            "report": f"Error scoring {ticker}: {exc}",
                            "score": None,
                            "cost_usd": 0.0,
                            "error": str(exc),
                        }

                    async with scored_lock:
                        state["firms"][ticker] = firm_data
                        state["total_cost_usd"] = grok.total_cost_usd
                        _save_run(run_id, state)
                        done = sum(
                            1 for f in state["firms"].values() if f.get("score") is not None
                        )
                    await progress(
                        "scored",
                        ticker=ticker,
                        score=firm_data.get("score"),
                        done=done,
                        total=total,
                        cost_usd=grok.total_cost_usd,
                    )

            await asyncio.gather(*(score_one(e, i) for i, e in enumerate(universe)))

            if self._cancel.is_set():
                raise asyncio.CancelledError()

            scored_count = sum(
                1 for f in state["firms"].values() if f.get("score") is not None
            )
            state["firms_scored"] = scored_count
            if scored_count == 0:
                sample_errors = [
                    f"{t}: {d.get('error', d.get('report', ''))[:80]}"
                    for t, d in list(state["firms"].items())[:3]
                ]
                raise RuntimeError(
                    "No firms were successfully scored. "
                    f"All {len(state['firms'])} attempts failed. "
                    f"Samples: {' | '.join(sample_errors)}"
                )

            # Step 4 — top 30
            await progress("top30", message="Selecting top 30 firms...")
            ranked = sorted(
                [
                    f
                    for f in state["firms"].values()
                    if f.get("score") is not None
                ],
                key=lambda x: x["score"],
                reverse=True,
            )
            state["top30"] = ranked[:30]
            _save_run(run_id, state)

            if not state["top30"]:
                raise RuntimeError("Top-30 selection is empty; cannot build portfolio.")

            # Step 5 — final allocation (Exhibit 2E)
            if not state.get("portfolio"):
                await progress("allocation", message="Generating 15-asset portfolio...")
                top_reports = "\n\n---\n\n".join(
                    f"Ticker: {f['ticker']} | Company: {f['company']} | Score: {f['score']}\n{f['report']}"
                    for f in state["top30"]
                )
                alloc_result = await asyncio.to_thread(grok.generate_allocation, top_reports)
                state["portfolio"] = alloc_result.text
                state["total_cost_usd"] = grok.total_cost_usd
            state["status"] = "completed"
            state["completed_at"] = _utc_now()
            _save_run(run_id, state)

            await self._emit(
                {
                    "type": "complete",
                    "run_id": run_id,
                    "total_cost_usd": grok.total_cost_usd,
                    "state": state,
                }
            )

        except asyncio.CancelledError:
            state["status"] = "cancelled"
            state["completed_at"] = _utc_now()
            _save_run(run_id, state)
            await self._emit({"type": "cancelled", "run_id": run_id})
        except Exception as exc:  # noqa: BLE001
            state["status"] = "failed"
            state["error"] = str(exc)
            state["completed_at"] = _utc_now()
            _save_run(run_id, state)
            await self._emit({"type": "error", "run_id": run_id, "error": str(exc)})
        finally:
            self.is_running = False
            self.current_run_id = None


runner = PipelineRunner()

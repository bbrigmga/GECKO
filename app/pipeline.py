"""Gecko PM monthly pipeline orchestration."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from app.config import RUNS_DIR, Settings, load_settings
from app.grok import GrokClient, parse_score
from app.prompts import strip_firm_macro_outlook
from app.sources.stocknews import StockNewsClient
from app.sources.wikipedia import fetch_wikipedia_context
from app.sources.yahoo import (
    fetch_sp500_tickers,
    format_financials,
    get_company_name,
    get_industry,
    get_sector,
    get_ticker_info,
    sort_tickers_by_market_cap,
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


# Soft sector diversity for allocation candidates
_TOP_BY_SCORE = 20
_CANDIDATE_TARGET = 35
_SECTOR_CAP = 5


def _firm_sector(firm: dict[str, Any]) -> str:
    return (firm.get("sector") or firm.get("industry") or "Unknown").strip() or "Unknown"


def select_diversified_candidates(
    ranked: list[dict[str, Any]],
    *,
    top_by_score: int = _TOP_BY_SCORE,
    target: int = _CANDIDATE_TARGET,
    sector_cap: int = _SECTOR_CAP,
) -> list[dict[str, Any]]:
    """Build allocation candidates with soft sector diversity.

    Walks score order under a sector cap to seed ~top_by_score names, then fills
    missing sectors and remaining slots up to target. Cap relaxes only if the
    universe is too narrow to fill otherwise.
    """
    if not ranked:
        return []
    if len(ranked) <= min(top_by_score, target):
        return list(ranked)

    selected: list[dict[str, Any]] = []
    selected_tickers: set[str] = set()
    sector_counts: dict[str, int] = {}

    def try_add(firm: dict[str, Any], *, respect_cap: bool) -> bool:
        ticker = firm.get("ticker")
        if not ticker or ticker in selected_tickers:
            return False
        sector = _firm_sector(firm)
        if respect_cap and sector_counts.get(sector, 0) >= sector_cap:
            return False
        selected.append(firm)
        selected_tickers.add(ticker)
        sector_counts[sector] = sector_counts.get(sector, 0) + 1
        return True

    # Seed with best names under the sector cap
    for firm in ranked:
        if len(selected) >= top_by_score:
            break
        try_add(firm, respect_cap=True)

    # Prefer best remaining name from sectors not yet represented
    for firm in ranked:
        if len(selected) >= target:
            break
        if sector_counts.get(_firm_sector(firm), 0) == 0:
            try_add(firm, respect_cap=True)

    # Fill remaining slots under the sector cap
    for firm in ranked:
        if len(selected) >= target:
            break
        try_add(firm, respect_cap=True)

    # Relax cap only if still short
    for firm in ranked:
        if len(selected) >= target:
            break
        try_add(firm, respect_cap=False)

    return selected


def _top_reports_from_candidates(candidates: list[dict[str, Any]]) -> str:
    """Build firm-only candidate packets (macro outlook sections stripped)."""
    return "\n\n---\n\n".join(
        f"Ticker: {f['ticker']} | Company: {f['company']} | "
        f"Sector: {_firm_sector(f)} | Score: {f['score']}\n"
        f"{strip_firm_macro_outlook(f.get('report', ''))}"
        for f in candidates
    )


async def _generate_portfolio(state: dict[str, Any], grok: GrokClient) -> None:
    candidates = state.get("allocation_candidates") or state.get("top30") or []
    top_reports = _top_reports_from_candidates(candidates)
    macro_report = state.get("macro_report") or ""
    alloc_result = await asyncio.to_thread(
        grok.generate_allocation, macro_report, top_reports
    )
    state["portfolio"] = alloc_result.text
    state["total_cost_usd"] = grok.total_cost_usd


def find_latest_run_with_top30() -> str | None:
    entries = list_runs()
    for entry in entries:
        if entry.get("status") != "completed":
            continue
        data = load_run(entry["run_id"])
        if data and data.get("top30"):
            return entry["run_id"]
    for entry in entries:
        data = load_run(entry["run_id"])
        if data and data.get("top30"):
            return entry["run_id"]
    return None


def is_resumable_run(data: dict[str, Any]) -> bool:
    """True when a run has partial progress and no finished portfolio yet."""
    if data.get("mode") == "portfolio_only":
        return False
    if data.get("portfolio"):
        return False
    scored = sum(
        1 for f in data.get("firms", {}).values() if f.get("score") is not None
    )
    if scored <= 0:
        return False
    return data.get("status") in ("running", "cancelled", "failed")


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
                scored = sum(
                    1
                    for f in data.get("firms", {}).values()
                    if f.get("score") is not None
                )
                runs.append(
                    {
                        "run_id": data.get("run_id", run_dir.name),
                        "status": data.get("status"),
                        "started_at": data.get("started_at"),
                        "completed_at": data.get("completed_at"),
                        "total_cost_usd": data.get("total_cost_usd", 0),
                        "firms_scored": data.get("firms_scored") or scored,
                        "firms_attempted": len(data.get("firms", {})),
                        "portfolio_preview": (data.get("portfolio") or "")[:200],
                        "error": data.get("error"),
                        "mode": data.get("mode", "full"),
                        "source_run_id": data.get("source_run_id"),
                        "universe_count": data.get("universe_count"),
                        "resumable": is_resumable_run(data),
                    }
                )
    return runs


async def _build_scoring_universe(
    state: dict[str, Any],
    settings: Settings,
    resume: bool,
    progress: ProgressCallback,
) -> list[dict[str, str]]:
    """Load tickers to score. On resume, keep the run's original scope (snapshot max_tickers)."""
    snap = state.get("settings") or {}
    max_tickers = int(snap.get("max_tickers") or 0) if resume else settings.max_tickers

    if resume and state.get("universe_tickers"):
        tickers = list(state["universe_tickers"])
        await progress(
            "universe",
            message=f"Resuming original universe ({len(tickers)} tickers)...",
        )
    else:
        await progress("universe", message="Loading S&P 500 constituents...")
        all_tickers = fetch_sp500_tickers()
        await progress(
            "universe",
            message=f"Sorting {len(all_tickers)} tickers by market cap...",
        )
        sorted_entries = await asyncio.to_thread(sort_tickers_by_market_cap, all_tickers)
        if max_tickers > 0:
            sorted_entries = sorted_entries[:max_tickers]
            await progress(
                "universe",
                message=(
                    f"Using top {len(sorted_entries)} by market cap "
                    f"(max_tickers={max_tickers})"
                ),
            )
        tickers = [e["ticker"] for e in sorted_entries]
        state["universe_tickers"] = tickers

    sp500 = await asyncio.to_thread(fetch_sp500_tickers)
    by_ticker = {e["ticker"]: e for e in sp500}

    universe: list[dict[str, str]] = []
    seen: set[str] = set()
    firms = state.get("firms") or {}
    for ticker in tickers:
        if ticker in by_ticker:
            universe.append(by_ticker[ticker])
        elif ticker in firms:
            firm = firms[ticker]
            universe.append(
                {
                    "ticker": ticker,
                    "name": firm.get("company", ticker),
                    "sector": firm.get("sector") or firm.get("industry") or "Unknown",
                }
            )
        seen.add(ticker)

    if resume:
        for ticker, firm in firms.items():
            if firm.get("score") is None and ticker not in seen:
                if ticker in by_ticker:
                    universe.append(by_ticker[ticker])
                else:
                    universe.append(
                        {
                            "ticker": ticker,
                            "name": firm.get("company", ticker),
                            "sector": firm.get("sector") or firm.get("industry") or "Unknown",
                        }
                    )
                seen.add(ticker)

    return universe


def _pending_scoring_entries(
    state: dict[str, Any], universe: list[dict[str, str]]
) -> list[dict[str, str]]:
    """Tickers that still need a Grok score (failed or never attempted)."""
    firms = state.get("firms") or {}
    pending: list[dict[str, str]] = []
    for entry in universe:
        ticker = entry["ticker"]
        if ticker not in firms or firms[ticker].get("score") is None:
            pending.append(entry)
    return pending


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
            if entry.get("resumable"):
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

    async def start_portfolio_only(
        self, source_run_id: str | None = None, settings: Settings | None = None
    ) -> tuple[str, str, str]:
        if self.is_running:
            raise RuntimeError("A run is already in progress")
        settings = settings or load_settings()
        if not settings.xai_api_key:
            raise ValueError("LLM API key is required (xAI or OpenRouter)")

        resolved_source = source_run_id or find_latest_run_with_top30()
        if not resolved_source:
            raise ValueError("No run with top-30 firm reports found")
        source = load_run(resolved_source)
        if not source or not source.get("top30"):
            raise ValueError(f"Run {resolved_source} has no top-30 data")

        run_id = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S")
        self.current_run_id = run_id
        self._cancel.clear()
        self.is_running = True

        self._task = asyncio.create_task(
            self._run_portfolio_only(run_id, settings, source, resolved_source)
        )
        return run_id, resolved_source, settings.model

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

            # Step 3 — S&P 500 universe (largest market cap first; resume keeps original scope)
            universe = await _build_scoring_universe(state, settings, resume, progress)
            total = len(universe)
            state["universe_count"] = total
            _save_run(run_id, state)

            to_score = _pending_scoring_entries(state, universe)
            already_scored = total - len(to_score)
            if resume and to_score:
                await progress(
                    "scoring",
                    message=(
                        f"Resuming: {already_scored} already scored, "
                        f"{len(to_score)} to retry (Yahoo + news, then Grok)..."
                    ),
                    done=already_scored,
                    total=total,
                )
            elif resume and not to_score:
                await progress(
                    "scoring",
                    message=f"All {total} firms already scored — moving to portfolio...",
                    done=total,
                    total=total,
                )

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
                        index=already_scored + index + 1,
                        total=total,
                        message=f"Fetching data for {ticker} ({already_scored + index + 1}/{total})",
                    )
                    try:
                        info = await asyncio.to_thread(get_ticker_info, ticker)
                        company = get_company_name(info, ticker)
                        industry = get_industry(info)
                        sector = get_sector(info) or entry.get("sector") or "Unknown"
                        financials = format_financials(info)
                        news = await stocknews.get_ticker_news(
                            ticker, items=settings.stocknews_items_per_ticker
                        )

                        await progress(
                            "grok",
                            ticker=ticker,
                            message=f"Calling {settings.model} ({settings.api_provider}) for {ticker}...",
                        )
                        result = await asyncio.to_thread(
                            grok.score_firm,
                            ticker,
                            company,
                            industry,
                            financials,
                            news,
                        )
                        score = parse_score(result.text)
                        firm_data = {
                            "ticker": ticker,
                            "company": company,
                            "industry": industry,
                            "sector": sector,
                            "report": result.text,
                            "score": score,
                            "cost_usd": result.cost_usd,
                        }
                    except Exception as exc:  # noqa: BLE001
                        firm_data = {
                            "ticker": ticker,
                            "company": entry.get("name", ticker),
                            "industry": entry.get("sector", "Unknown"),
                            "sector": entry.get("sector", "Unknown"),
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
                    scored_msg = f"Scored {ticker}: {firm_data.get('score')}"
                    if firm_data.get("error"):
                        scored_msg = f"Failed {ticker}: {firm_data['error'][:120]}"
                    await progress(
                        "scored",
                        ticker=ticker,
                        score=firm_data.get("score"),
                        done=done,
                        total=total,
                        cost_usd=grok.total_cost_usd,
                        message=scored_msg,
                        error=firm_data.get("error"),
                    )

            await asyncio.gather(*(score_one(e, i) for i, e in enumerate(to_score)))

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

            # Step 4 — ranked top + soft sector-diversified allocation candidates
            await progress(
                "top30",
                message="Selecting top firms with soft sector diversity...",
            )
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
            state["allocation_candidates"] = select_diversified_candidates(ranked)
            _save_run(run_id, state)

            if not state["allocation_candidates"]:
                raise RuntimeError("Candidate selection is empty; cannot build portfolio.")

            # Step 5 — final allocation (Exhibit 2E)
            if not state.get("portfolio"):
                await progress("allocation", message="Generating 15-asset portfolio...")
                if self._cancel.is_set():
                    raise asyncio.CancelledError()
                await _generate_portfolio(state, grok)
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

    async def _run_portfolio_only(
        self,
        run_id: str,
        settings: Settings,
        source: dict[str, Any],
        source_run_id: str,
    ) -> None:
        top30 = list(source.get("top30") or [])
        candidates = list(source.get("allocation_candidates") or [])
        if not candidates:
            ranked = sorted(
                [
                    f
                    for f in (source.get("firms") or {}).values()
                    if f.get("score") is not None
                ],
                key=lambda x: x["score"],
                reverse=True,
            )
            candidates = select_diversified_candidates(ranked) if ranked else top30

        state: dict[str, Any] = {
            "run_id": run_id,
            "status": "running",
            "started_at": _utc_now(),
            "mode": "portfolio_only",
            "source_run_id": source_run_id,
            "settings": _safe_settings(settings),
            "macro_news_raw": "",
            "wikipedia_context": "",
            "macro_report": source.get("macro_report", ""),
            "firms": {},
            "top30": top30,
            "allocation_candidates": candidates,
            "portfolio": "",
            "total_cost_usd": 0.0,
            "error": None,
            "universe_count": source.get("universe_count"),
            "firms_scored": source.get("firms_scored"),
        }
        _save_run(run_id, state)

        async def progress(step: str, **extra: Any) -> None:
            payload = {"type": "progress", "step": step, "run_id": run_id, **extra}
            await self._emit(payload)

        try:
            grok = GrokClient(
                settings.xai_api_key,
                settings.model,
                provider=settings.api_provider,
            )
            await progress(
                "allocation",
                message=f"Generating 15-asset portfolio from {source_run_id}...",
            )
            if self._cancel.is_set():
                raise asyncio.CancelledError()
            await _generate_portfolio(state, grok)
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

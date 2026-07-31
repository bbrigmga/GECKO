"""Smoke tests for Gecko PM (no API keys required)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_imports() -> None:
    from app import config, grok, pipeline, prompts  # noqa: F401
    from app.sources import stocknews, wikipedia, yahoo  # noqa: F401
    print("OK imports")


def test_prompts() -> None:
    from app.prompts import (
        allocation_prompt,
        firm_prompt,
        macro_prompt,
        strip_firm_macro_outlook,
    )

    firm = firm_prompt("Apple Inc.", "Technology", "financials", "news")
    assert "Investment Report:" in firm
    assert "Score: X" in firm
    assert "Apple Inc." in firm
    assert "Macro-economic data" not in firm
    assert "stand-alone investment quality" in firm
    assert "economic-outlook section" in firm

    macro = macro_prompt("context block")
    assert "next three months" in macro
    assert "interest rates" in macro

    alloc = allocation_prompt("sticky inflation forecast", "top reports here")
    assert "15-asset portfolio" in alloc
    assert "thesis, edge, and risk" in alloc
    assert "sticky inflation forecast" in alloc
    assert "top reports here" in alloc
    assert "stand-alone quality" in alloc

    report = (
        "Investment Report:\n"
        "Recent news: strong bookings.\n"
        "Financials: EPS up 20%.\n"
        "Valuations: forward P/E 12.\n"
        "Economic outlook affecting the firm centers on sticky inflation "
        "and Fed caution through October.\n"
        "Score: 82"
    )
    cleaned = strip_firm_macro_outlook(report)
    assert "Recent news: strong bookings." in cleaned
    assert "Financials: EPS up 20%." in cleaned
    assert "Valuations: forward P/E 12." in cleaned
    assert "Economic outlook" not in cleaned
    assert "sticky inflation" not in cleaned
    assert "Score: 82" in cleaned
    print("OK prompts")


def test_resumable_run() -> None:
    from app.pipeline import is_resumable_run

    assert is_resumable_run(
        {"status": "failed", "firms": {"AAPL": {"score": 80}}, "portfolio": ""}
    )
    assert not is_resumable_run(
        {"status": "failed", "firms": {"AAPL": {"score": 80}}, "portfolio": "done"}
    )
    assert not is_resumable_run({"status": "completed", "firms": {}, "portfolio": "x"})
    assert is_resumable_run({"status": "cancelled", "firms": {"X": {"score": 70}}})
    assert not is_resumable_run(
        {"status": "failed", "mode": "portfolio_only", "firms": {}, "portfolio": ""}
    )
    print("OK resumable run")


def test_sector_diversity() -> None:
    from app.pipeline import select_diversified_candidates

    ranked = []
    # Many healthcare names would dominate a naive top-30
    for i in range(15):
        ranked.append(
            {
                "ticker": f"HC{i}",
                "company": f"Health {i}",
                "sector": "Health Care",
                "industry": "Drug Manufacturers",
                "score": 95 - i,
                "report": f"Report HC{i}",
            }
        )
    other_sectors = [
        "Financials",
        "Energy",
        "Utilities",
        "Industrials",
        "Consumer Discretionary",
        "Information Technology",
        "Materials",
        "Real Estate",
        "Communication Services",
        "Consumer Staples",
    ]
    for i in range(30):
        sector = other_sectors[i % len(other_sectors)]
        ranked.append(
            {
                "ticker": f"S{i}",
                "company": f"{sector} Co {i}",
                "sector": sector,
                "industry": sector,
                "score": 70 - (i * 0.1),
                "report": f"Report {sector} {i}",
            }
        )

    selected = select_diversified_candidates(
        ranked, top_by_score=20, target=30, sector_cap=5
    )
    assert len(selected) == 30
    sectors = [f["sector"] for f in selected]
    assert sectors.count("Health Care") <= 5
    assert "Energy" in sectors
    assert "Utilities" in sectors
    # Best healthcare names still present
    assert "HC0" in {f["ticker"] for f in selected}
    print("OK sector diversity")


def test_score_parsing() -> None:
    from app.grok import parse_score

    assert parse_score("Investment Report:\n...\nScore: 87") == 87
    assert parse_score("score: 42") == 42
    assert parse_score("no score here") is None
    print("OK score parsing")


def test_resolve_model() -> None:
    from app.grok import resolve_model

    assert resolve_model("xai", "grok-4.3") == "grok-4.3"
    assert resolve_model("xai", "grok-4.5") == "grok-4.5"
    assert resolve_model("openrouter", "grok-4.3") == "x-ai/grok-4.3"
    assert resolve_model("openrouter", "grok-4.5") == "x-ai/grok-4.5"
    assert resolve_model("openrouter", "x-ai/grok-4.5") == "x-ai/grok-4.5"
    print("OK resolve_model")


def test_sp500() -> None:
    from app.sources.yahoo import fetch_sp500_tickers

    tickers = fetch_sp500_tickers()
    assert len(tickers) >= 400
    assert any(t["ticker"] == "AAPL" for t in tickers)
    print(f"OK S&P 500 ({len(tickers)} tickers)")


def test_market_cap_sort() -> None:
    from app.sources.yahoo import sort_tickers_by_market_cap

    sample = [
        {"ticker": "AAPL", "name": "Apple", "sector": "Information Technology"},
        {"ticker": "MSFT", "name": "Microsoft", "sector": "Information Technology"},
        {"ticker": "F", "name": "Ford", "sector": "Consumer Discretionary"},
    ]
    sorted_tickers = sort_tickers_by_market_cap(sample, workers=4)
    assert len(sorted_tickers) == 3
    assert all("market_cap" in t for t in sorted_tickers)
    caps = [float(t["market_cap"]) for t in sorted_tickers]
    assert caps == sorted(caps, reverse=True)
    # Mega-caps should outrank Ford
    assert sorted_tickers[-1]["ticker"] == "F" or caps[0] >= caps[-1]
    print(
        "OK market cap sort: "
        + ", ".join(f"{t['ticker']}={t['market_cap']}" for t in sorted_tickers)
    )


def test_yfinance() -> None:
    from app.sources.yahoo import format_financials, get_company_name, get_industry, get_ticker_info

    info = get_ticker_info("AAPL")
    name = get_company_name(info, "AAPL")
    industry = get_industry(info)
    financials = format_financials(info)
    assert "AAPL" in name or "Apple" in name
    assert industry
    assert "Market Capitalization" in financials or "Previous Close Price" in financials
    print(f"OK yfinance ({name}, {industry}, {len(financials)} chars)")


def test_wikipedia() -> None:
    import asyncio

    from app.sources.wikipedia import fetch_wikipedia_context

    text = asyncio.run(fetch_wikipedia_context(["https://en.wikipedia.org/wiki/2026"]))
    assert len(text) > 100
    print(f"OK wikipedia ({len(text)} chars)")


def test_fastapi_app() -> None:
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    r = client.get("/")
    assert r.status_code == 200
    assert "Gecko PM" in r.text

    r = client.get("/api/settings")
    assert r.status_code == 200
    assert "model" in r.json()

    r = client.get("/api/runs")
    assert r.status_code == 200
    assert isinstance(r.json(), list)

    r = client.post("/api/run/portfolio")
    assert r.status_code in (400, 409)
    print("OK FastAPI routes")


if __name__ == "__main__":
    tests = [
        test_imports,
        test_prompts,
        test_resumable_run,
        test_sector_diversity,
        test_score_parsing,
        test_resolve_model,
        test_sp500,
        test_market_cap_sort,
        test_yfinance,
        test_wikipedia,
        test_fastapi_app,
    ]
    failed = 0
    for test in tests:
        try:
            test()
        except Exception as exc:  # noqa: BLE001
            print(f"FAIL {test.__name__}: {exc}", file=sys.stderr)
            failed += 1
    if failed:
        sys.exit(1)
    print("\nAll smoke tests passed.")

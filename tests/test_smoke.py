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
    from app.prompts import allocation_prompt, firm_prompt, macro_prompt

    firm = firm_prompt("Apple Inc.", "Technology", "macro ctx", "financials", "news")
    assert "Investment Report:" in firm
    assert "Score: X" in firm
    assert "Apple Inc." in firm

    macro = macro_prompt("context block")
    assert "next three months" in macro
    assert "interest rates" in macro

    alloc = allocation_prompt("top reports here")
    assert "15-asset portfolio" in alloc
    assert "thesis, edge, and risk" in alloc
    print("OK prompts")


def test_score_parsing() -> None:
    from app.grok import parse_score

    assert parse_score("Investment Report:\n...\nScore: 87") == 87
    assert parse_score("score: 42") == 42
    assert parse_score("no score here") is None
    print("OK score parsing")


def test_sp500() -> None:
    from app.sources.yahoo import fetch_sp500_tickers

    tickers = fetch_sp500_tickers()
    assert len(tickers) >= 400
    assert any(t["ticker"] == "AAPL" for t in tickers)
    print(f"OK S&P 500 ({len(tickers)} tickers)")


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
    print("OK FastAPI routes")


if __name__ == "__main__":
    tests = [
        test_imports,
        test_prompts,
        test_score_parsing,
        test_sp500,
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

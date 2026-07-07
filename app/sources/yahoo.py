"""Yahoo Finance data via yfinance (Exhibits 2B, S&P 500 universe)."""

from __future__ import annotations

import io
from typing import Any

import httpx
import pandas as pd
import yfinance as yf

# Exhibit 2B — human label -> yfinance info key
FINANCIAL_FIELDS: list[tuple[str, str]] = [
    ("Previous Close Price", "previousClose"),
    ("Opening Price", "open"),
    ("Lowest Price of the Day", "dayLow"),
    ("Highest Price of the Day", "dayHigh"),
    ("Previous Close Price (Regular Market)", "regularMarketPreviousClose"),
    ("Opening Price (Regular Market)", "regularMarketOpen"),
    ("Lowest Price of the Day (Regular Market)", "regularMarketDayLow"),
    ("Highest Price of the Day (Regular Market)", "regularMarketDayHigh"),
    ("Annual Dividend Rate", "dividendRate"),
    ("Dividend Yield", "dividendYield"),
    ("Payout Ratio (Dividend Payout as Percentage of Earnings)", "payoutRatio"),
    ("Five-Year Average Dividend Yield", "fiveYearAvgDividendYield"),
    ("Beta (Volatility Measure)", "beta"),
    ("Price-to-Earnings Ratio (Trailing 12 Months)", "trailingPE"),
    ("Price-to-Earnings Ratio (Forward 12 Months)", "forwardPE"),
    ("Daily Volume of Shares Traded", "volume"),
    ("Daily Volume of Shares Traded (Regular Market)", "regularMarketVolume"),
    ("Average Volume of Shares Traded", "averageVolume"),
    ("Average Volume of Shares Traded (Last 10 Days)", "averageDailyVolume10Day"),
    ("Average Daily Volume of Shares Traded (Last 10 Days)", "averageDailyVolume10Day"),
    ("Bid Price", "bid"),
    ("Ask Price", "ask"),
    ("Bid Size (Number of Shares)", "bidSize"),
    ("Ask Size (Number of Shares)", "askSize"),
    ("Market Capitalization", "marketCap"),
    ("52-Week Low Price", "fiftyTwoWeekLow"),
    ("52-Week High Price", "fiftyTwoWeekHigh"),
    ("Price-to-Sales Ratio (Trailing 12 Months)", "priceToSalesTrailing12Months"),
    ("50-Day Moving Average Price", "fiftyDayAverage"),
    ("200-Day Moving Average Price", "twoHundredDayAverage"),
    ("Annual Dividend Rate (Trailing 12 Months)", "trailingAnnualDividendRate"),
    ("Dividend Yield (Trailing 12 Months)", "trailingAnnualDividendYield"),
    ("Trading Currency", "currency"),
    ("Enterprise Value", "enterpriseValue"),
    ("Profit Margins", "profitMargins"),
    ("Float Shares (Shares Available to Public)", "floatShares"),
    ("Shares Outstanding", "sharesOutstanding"),
    ("Shares Sold Short", "sharesShort"),
    ("Shares Sold Short in the Previous Month", "sharesShortPriorMonth"),
    ("Short Interest Date of Previous Month", "dateShortInterest"),
    ("Most Recent Short Interest Date", "dateShortInterest"),
    ("Short Interest as Percentage of Outstanding Shares", "shortPercentOfFloat"),
    ("Insider Holdings Percentage", "heldPercentInsiders"),
    ("Institutional Holdings Percentage", "heldPercentInstitutions"),
    ("Short Ratio (Days to Cover Short Positions)", "shortRatio"),
    ("Short Interest as Percentage of Float", "shortPercentOfFloat"),
    ("Implied Shares Outstanding", "impliedSharesOutstanding"),
    ("Book Value per Share", "bookValue"),
    ("Price-to-Book Ratio", "priceToBook"),
    ("Last Fiscal Year End Date", "lastFiscalYearEnd"),
    ("Next Fiscal Year End Date", "nextFiscalYearEnd"),
    ("Most Recent Quarter Date", "mostRecentQuarter"),
    ("Earnings Growth (Quarterly)", "earningsQuarterlyGrowth"),
    ("Net Income to Common Stockholders", "netIncomeToCommon"),
    ("Earnings per Share (Trailing 12 Months)", "trailingEps"),
    ("Earnings per Share (Forward 12 Months)", "forwardEps"),
    ("Price/Earnings to Growth (PEG) Ratio", "pegRatio"),
    ("Last Stock Split Factor", "lastSplitFactor"),
    ("Last Stock Split Date", "lastSplitDate"),
    ("Enterprise Value to Revenue Ratio", "enterpriseToRevenue"),
    ("Enterprise Value to EBITDA Ratio", "enterpriseToEbitda"),
    ("52-Week Price Change Percentage", "52WeekChange"),
    ("S&P 500 52-Week Price Change Percentage", "SandP52WeekChange"),
    ("Last Dividend Value", "lastDividendValue"),
    ("Last Dividend Payment Date", "lastDividendDate"),
    ("Highest Target Price (Analyst Forecast)", "targetHighPrice"),
    ("Lowest Target Price (Analyst Forecast)", "targetLowPrice"),
    ("Mean Target Price (Analyst Forecast)", "targetMeanPrice"),
    ("Median Target Price (Analyst Forecast)", "targetMedianPrice"),
    ("Recommendation Mean (Analyst Consensus)", "recommendationMean"),
    ("Recommendation Key (Analyst Rating)", "recommendationKey"),
    ("Number of Analyst Opinions", "numberOfAnalystOpinions"),
    ("Total Cash", "totalCash"),
    ("Cash per Share", "totalCashPerShare"),
    ("EBITDA (Earnings Before Interest, Taxes, Depreciation, and Amortization)", "ebitda"),
    ("Total Debt", "totalDebt"),
    ("Quick Ratio (Liquidity Measure)", "quickRatio"),
    ("Current Ratio (Liquidity Measure)", "currentRatio"),
    ("Total Revenue", "totalRevenue"),
    ("Debt-to-Equity Ratio", "debtToEquity"),
    ("Revenue per Share", "revenuePerShare"),
    ("Return on Assets (ROA)", "returnOnAssets"),
    ("Return on Equity (ROE)", "returnOnEquity"),
    ("Free Cash Flow", "freeCashflow"),
    ("Operating Cash Flow", "operatingCashflow"),
    ("Earnings Growth Rate", "earningsGrowth"),
    ("Revenue Growth Rate", "revenueGrowth"),
    ("Gross Profit Margins", "grossMargins"),
    ("EBITDA Margins", "ebitdaMargins"),
    ("Operating Margins", "operatingMargins"),
    ("Financial Currency", "financialCurrency"),
    ("Price/Earnings to Growth (PEG) Ratio (Trailing)", "trailingPegRatio"),
    ("Audit Risk Level", "auditRisk"),
    ("Board Risk Level", "boardRisk"),
    ("Compensation Risk Level", "compensationRisk"),
    ("Shareholder Rights Risk Level", "shareHolderRightsRisk"),
    ("Overall Risk Level", "overallRisk"),
]

_SEEN_KEYS: set[str] = set()
_UNIQUE_FIELDS: list[tuple[str, str]] = []
for label, key in FINANCIAL_FIELDS:
    if key not in _SEEN_KEYS:
        _SEEN_KEYS.add(key)
        _UNIQUE_FIELDS.append((label, key))


def _format_value(value: Any) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, float):
        if value != value:  # NaN
            return "N/A"
        return f"{value:,.6g}"
    return str(value)


def format_financials(info: dict[str, Any]) -> str:
    lines: list[str] = []
    for label, key in _UNIQUE_FIELDS:
        value = info.get(key)
        if value is not None and not (isinstance(value, float) and value != value):
            lines.append(f"{label}: {_format_value(value)}")
    if not lines:
        return "No financial data available."
    return "\n".join(lines)


def get_ticker_info(ticker: str) -> dict[str, Any]:
    t = yf.Ticker(ticker)
    info = t.info or {}
    if not info.get("longName") and not info.get("shortName"):
        # yfinance sometimes needs a history pull to populate info
        try:
            t.history(period="5d")
            info = t.info or {}
        except Exception:  # noqa: BLE001
            pass
    return info


def get_company_name(info: dict[str, Any], ticker: str) -> str:
    return (
        info.get("longName")
        or info.get("shortName")
        or info.get("displayName")
        or ticker
    )


def get_industry(info: dict[str, Any]) -> str:
    return info.get("industry") or info.get("sector") or "Unknown"


def fetch_sp500_tickers() -> list[dict[str, str]]:
    """Return S&P 500 constituents from a public dataset (Wikipedia fallback)."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        )
    }

    # Primary: stable CSV mirror (avoids Wikipedia 403 blocks)
    csv_url = (
        "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/"
        "master/data/constituents.csv"
    )
    try:
        resp = httpx.get(csv_url, headers=headers, timeout=60.0, follow_redirects=True)
        resp.raise_for_status()
        df = pd.read_csv(io.StringIO(resp.text))
        tickers: list[dict[str, str]] = []
        for _, row in df.iterrows():
            symbol = str(row["Symbol"]).replace(".", "-")
            name = str(row.get("Name", symbol))
            sector = str(row.get("Sector", ""))
            tickers.append({"ticker": symbol, "name": name, "sector": sector})
        if tickers:
            return tickers
    except Exception:  # noqa: BLE001
        pass

    # Fallback: Wikipedia table scrape
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    resp = httpx.get(url, headers=headers, timeout=60.0, follow_redirects=True)
    resp.raise_for_status()
    tables = pd.read_html(io.StringIO(resp.text))
    df = tables[0]
    tickers = []
    for _, row in df.iterrows():
        symbol = str(row["Symbol"]).replace(".", "-")
        name = str(row.get("Security", row.get("Company", symbol)))
        sector = str(row.get("GICS Sector", ""))
        tickers.append({"ticker": symbol, "name": name, "sector": sector})
    return tickers

"""Employer-style portfolio compliance: large-cap stocks + plain ETFs."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable

from app.sources.yahoo import get_instrument_info

# Obvious inverse / leveraged / vol products — fail closed on name/symbol match.
_INELIGIBLE_ETF_RE = re.compile(
    r"(?i)(?:"
    r"\b2x\b|\b3x\b|\bultra\s*pro\b|\bleveraged\b|\binverse\b|"
    r"\bshort\s+vix\b|\bshort\s+volatility\b|\bvolatility\b|\bvix\b|"
    r"\bbear\s*\d|\bbull\s*\d|\b-ultra\b|\bproshares\s+short\b"
    r")"
)


@dataclass
class InstrumentInfo:
    ticker: str
    quote_type: str
    market_cap: float
    name: str
    eligible: bool
    reason: str


def is_eligible_plain_etf(info: InstrumentInfo) -> tuple[bool, str]:
    """True for verified long-only, unleveraged ETFs."""
    if info.quote_type != "ETF":
        return False, f"not classified as ETF (quoteType={info.quote_type or 'unknown'})"
    haystack = f"{info.ticker} {info.name}"
    if _INELIGIBLE_ETF_RE.search(haystack):
        return False, "inverse, leveraged, or volatility ETF"
    return True, "eligible plain ETF"


def instrument_from_yahoo(ticker: str) -> InstrumentInfo:
    raw = get_instrument_info(ticker)
    quote_type = (raw.get("quote_type") or "").upper()
    market_cap = float(raw.get("market_cap") or 0.0)
    name = raw.get("name") or ticker
    eligible = False
    reason = "unclassified instrument"
    if quote_type == "EQUITY":
        eligible = market_cap > 0
        reason = "common stock" if eligible else "missing market cap"
    elif quote_type == "ETF":
        probe = InstrumentInfo(ticker, quote_type, market_cap, name, False, "")
        eligible, reason = is_eligible_plain_etf(probe)
    else:
        reason = f"unsupported quoteType={quote_type or 'unknown'}"
    return InstrumentInfo(ticker, quote_type, market_cap, name, eligible, reason)


def stock_meets_cap(info: InstrumentInfo | dict[str, Any], min_cap: float) -> bool:
    if isinstance(info, InstrumentInfo):
        cap = info.market_cap
    else:
        cap = float(info.get("market_cap") or 0.0)
    return cap >= min_cap


def filter_entries_by_market_cap(
    entries: list[dict[str, str]],
    min_cap: float,
) -> list[dict[str, str]]:
    """Keep universe rows at or above min_cap (requires market_cap on entries)."""
    out: list[dict[str, str]] = []
    for entry in entries:
        cap = float(entry.get("market_cap") or 0.0)
        if cap >= min_cap:
            out.append(entry)
    return out


def select_compliant_stock_candidates(
    ranked: list[dict[str, Any]],
    *,
    count: int,
    min_cap: float,
) -> list[dict[str, Any]]:
    """Top-N scored firms that meet the market-cap floor."""
    eligible: list[dict[str, Any]] = []
    for firm in ranked:
        cap = float(firm.get("market_cap") or 0.0)
        if cap >= min_cap:
            eligible.append(firm)
        if len(eligible) >= count:
            break
    return eligible


def enrich_firms_market_cap(firms: list[dict[str, Any]]) -> None:
    """Attach market_cap to firm dicts in place (Yahoo lookup when missing)."""
    for firm in firms:
        if firm.get("market_cap"):
            continue
        info = instrument_from_yahoo(str(firm.get("ticker") or ""))
        firm["market_cap"] = info.market_cap


def enrich_until_eligible(
    ranked: list[dict[str, Any]],
    *,
    min_cap: float,
    needed: int,
) -> list[dict[str, Any]]:
    """Walk score order, enriching caps lazily until `needed` eligible firms."""
    eligible: list[dict[str, Any]] = []
    for firm in ranked:
        cap = float(firm.get("market_cap") or 0.0)
        if cap <= 0.0:
            info = instrument_from_yahoo(str(firm.get("ticker") or ""))
            cap = info.market_cap
            firm["market_cap"] = cap
        if cap >= min_cap:
            eligible.append(firm)
        if len(eligible) >= needed:
            break
    return eligible


def compliance_summary(
    *,
    enabled: bool,
    min_market_cap_usd: int,
    stock_candidate_count: int,
    eligible_universe_count: int | None = None,
    candidate_tickers: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "enabled": enabled,
        "min_market_cap_usd": min_market_cap_usd,
        "stock_candidate_count": stock_candidate_count,
        "eligible_universe_count": eligible_universe_count,
        "candidate_tickers": candidate_tickers or [],
        "portfolio_status": None,
        "portfolio_issues": [],
        "disclaimer": (
            "Screening aid only — Yahoo data may be stale or incomplete. "
            "Your employer compliance system is the final authority."
        ),
    }


def _parse_table_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.split("|")[1:-1]]


def parse_portfolio_table(text: str) -> list[dict[str, str]]:
    """Extract holdings from a markdown portfolio table."""
    if not text:
        return []
    lines = [ln for ln in text.split("\n") if ln.strip().startswith("|")]
    if len(lines) < 2:
        return []

    headers = [h.lower() for h in _parse_table_row(lines[0])]
    weight_idx = next((i for i, h in enumerate(headers) if "weight" in h), 0)
    instrument_idx = next(
        (i for i, h in enumerate(headers) if h in ("instrument", "ticker", "symbol")
         or "instrument" in h),
        1,
    )
    type_idx = next((i for i, h in enumerate(headers) if "type" in h), -1)

    rows: list[dict[str, str]] = []
    for line in lines[1:]:
        cells = _parse_table_row(line)
        if not cells or all(re.fullmatch(r"[-:\s]+", c or "") for c in cells):
            continue
        instrument = (cells[instrument_idx] if instrument_idx < len(cells) else "").strip()
        if not instrument or instrument.lower() == "instrument":
            continue
        ticker = re.sub(r"[^A-Za-z0-9.\-]", "", instrument).upper().replace(".", "-")
        row_type = cells[type_idx].strip() if type_idx >= 0 and type_idx < len(cells) else ""
        weight = cells[weight_idx].strip() if weight_idx < len(cells) else ""
        rows.append({"ticker": ticker, "type": row_type, "weight": weight})
    return rows


def validate_portfolio(
    holdings: list[dict[str, str]],
    allowed_stock_tickers: set[str],
    *,
    etf_checker: Callable[[str], tuple[bool, str]] | None = None,
) -> tuple[bool, list[str]]:
    """Every holding must be an allowed stock or an eligible plain ETF."""
    issues: list[str] = []
    checker = etf_checker or (lambda t: is_eligible_plain_etf(instrument_from_yahoo(t)))

    for row in holdings:
        ticker = (row.get("ticker") or "").upper()
        if not ticker:
            issues.append("empty instrument row in portfolio table")
            continue

        declared = (row.get("type") or "").lower()
        if ticker in allowed_stock_tickers:
            if declared and "etf" in declared and "stock" not in declared:
                issues.append(f"{ticker}: listed as ETF but is a stock candidate")
            continue

        ok, reason = checker(ticker)
        if ok:
            continue
        if declared and "stock" in declared and "etf" not in declared:
            issues.append(f"{ticker}: declared stock but not in candidate list")
        else:
            issues.append(f"{ticker}: ineligible ({reason})")

    return (len(issues) == 0, issues)


def etf_checker_from_cache(
    cache: dict[str, InstrumentInfo],
) -> Callable[[str], tuple[bool, str]]:
    def check(ticker: str) -> tuple[bool, str]:
        key = ticker.upper()
        if key not in cache:
            cache[key] = instrument_from_yahoo(key)
        info = cache[key]
        return is_eligible_plain_etf(info)

    return check

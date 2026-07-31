"""Verbatim prompts from The Grok Portfolio White Paper exhibits."""

from __future__ import annotations

import re

# Exhibit 2A — news outlets (used for client-side filtering when API allows)
NEWS_SOURCES = [
    "24/7 Wall Street",
    "Accesswire",
    "After Earnings",
    "Barrons",
    "Benzinga",
    "Bloomberg Markets and Finance",
    "Bloomberg Technology",
    "Business Insider",
    "Business Wire",
    "CNBC",
    "CNBC International TV",
    "CNBC Television",
    "CNET",
    "CNN",
    "CNN Business",
    "Cheddar Videos",
    "Deadline",
    "Digital Trends",
    "Discount The Obvious",
    "ETF Trends",
    "ETF.com",
    "Engadget",
    "Fast Company",
    "Finbold",
    "Forbes",
    "Fox Business",
    "FreightWaves",
    "FXEmpire",
    "GeekWire",
    "Globe News Wire",
    "Green Stock News",
    "GuruFocus",
    "Huffington Post",
    "InsiderTrades",
    "Investopedia",
    "Investor Place",
    "Investors Business Daily",
    "Invezz",
    "Kiplinger",
    "Kitco",
    "Marijuana Stocks",
    "Market Watch",
    "Mcap MediaWire",
    "Millennial Money",
    "Morningstar Inc.",
    "New York Times",
    "New York Post",
    "Newsfile Corp",
    "MarketBeat",
    "MCAP MediaWire",
    "Penny Stocks",
    "Proactive Investors",
    "PYMNTS.com",
    "PR Newswire",
    "Pulse2",
    "Reuters",
    "Schaeffers Research",
    "Schwab Network",
    "See It Market",
    "Seeking Alpha",
    "Skynews",
    "Stock Market.com",
    "TechCrunch",
    "TechXplore",
    "The Dog of Wall Street",
    "The Financial News",
    "The Guardian",
    "The Motley Fool",
    "The Street",
    "The Verge",
    "VentureBeat",
    "Wall Street Journal",
    "Yahoo Finance",
    "Zacks Investment Research",
]

WIKIPEDIA_URLS = [
    "https://en.wikipedia.org/wiki/2026",
    "https://en.wikipedia.org/wiki/2025_in_the_United_States",
    "https://en.wikipedia.org/wiki/2026_in_the_United_States",
]


def firm_prompt(company_name: str, industry: str, financials: str, news: str) -> str:
    """Firm-native scoring prompt (quality / valuation / momentum / news).

    Macro regime is intentionally excluded here so ranking is not biased toward
    the current forecast. Macro is applied later in allocation_prompt.
    """
    return (
        "Pretend you are a financial expert with stock recommendation experience.\n"
        "Speak in the third person.\n"
        "You do not mention your credentials.\n"
        f"Financial data for {company_name}:\n{financials}\n"
        f"Recent news headlines for {company_name}:\n{news}\n"
        "Based on the financial data and news headlines only,"
        " please assign a score (from 1 to 100) reflecting the firm's"
        " stand-alone investment quality for the next month — emphasizing"
        " business quality, financial strength, valuation attractiveness,"
        " and recent price or earnings momentum."
        f" Score company {company_name} in the {industry} industry.\n"
        "Do not condition the score on macroeconomic forecasts, Fed policy,"
        " tariffs, geopolitics, or broad market regime views.\n"
        "First, write a short investment report about the firm situation.\n"
        "Include sections of recent news, financials, valuations, and"
        " company-specific catalysts or risks.\n"
        "Do not include a macroeconomic or economic-outlook section.\n"
        "Do not recommend alternatives.\n"
        "Do not mention the word 'provided' instead use 'recent' or 'latest'.\n"
        "Do not speak directly to investors nor recommend actions.\n"
        "Start with 'Investment Report:'\n"
        "Finally, in a new line, output Score: X."
    )


def macro_prompt(context: str) -> str:
    """Exhibit 2D — macroeconomic DeeperSearch-style prompt."""
    return (
        "Here are some events and context to update your knowledge information cutoff.\n"
        f"{context}\n"
        "Provide a complete expected timeline of the most important economic and "
        "political events for the next three months in the USA. Not only the "
        "scheduled events and known forecasts. Also, provide your best expectations "
        "about the realization of these events. Pay special attention to the next "
        "month. I also want a table with your forecast for interest rates, "
        "inflation, tariffs, and other economic events for the next month and "
        "quarter. Not only what analysts and the market expect. Provide your "
        "expectations based on your research and compare them with the market's "
        "expectations."
    )


_FIRM_MACRO_OUTLOOK_RE = re.compile(
    r"(?is)(?:^|\n)\s*Economic\s+[Oo]utlook\b.*?(?=\n\s*Score\s*:|\Z)"
)


def strip_firm_macro_outlook(report: str) -> str:
    """Remove per-firm economic/macro outlook sections from an investment report.

    Newer firm scores omit that section. Kept for older runs that still have it,
    so allocation sees firm thesis plus one shared macro block.
    """
    cleaned = _FIRM_MACRO_OUTLOOK_RE.sub("", report or "")
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned


def allocation_prompt(macro_report: str, top_reports: str) -> str:
    """Exhibit 2E — final 15-asset portfolio allocation prompt.

    Macro forecast is provided once up front. Candidate firm packets are
    firm-quality scores (macro applied here, not at scoring time).
    """
    macro = (macro_report or "").strip() or "(No macro report available.)"
    return (
        "Now, I want a 15-asset portfolio where we will invest for the next month "
        "(rebalancing in one month) in a table with weight, instrument type, "
        "thesis, edge, and risk. Weight this portfolio to perform positively "
        "given the market conditions and to beat the S&P 500.\n\n"
        "Here is the macroeconomic forecast and context to use for regime, "
        "sector tilt, and ETF/bond decisions:\n"
        f"{macro}\n\n"
        "We have the following firm-level reports for stocks scored highest on "
        "stand-alone quality (financials, valuation, momentum, company news) — "
        "not on macro fit. The candidate set is also lightly diversified across "
        "sectors. Use these for company-specific thesis, edge, and name "
        "selection. Rely on the macro forecast above for market conditions:\n"
        f"{top_reports}\n\n"
        "However, we can also invest in most ETFs (except short, leveraged, or vol "
        "because of the monthly horizon), including but not limited to market, "
        "sectors, TIPS, and long and short-term bonds. You decide the weights; do "
        "not have to include any or all of the stocks or instruments mentioned. "
        "Use the macro forecast for regime positioning and the firm reports for "
        "security selection. You may underweight or omit names that do not fit "
        "the regime. Remember, a 15-asset portfolio where we will invest for the "
        "next month (rebalancing in one month) in a table with weight, instrument "
        "type, thesis, edge, and risk."
    )

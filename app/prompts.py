"""Verbatim prompts from The Grok Portfolio White Paper exhibits."""

from __future__ import annotations

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


def firm_prompt(company_name: str, industry: str, macro_news: str, financials: str, news: str) -> str:
    """Exhibit 1 — firm scoring prompt."""
    return (
        "Pretend you are a financial expert with stock recommendation experience.\n"
        "Speak in the third person.\n"
        "You do not mention your credentials.\n"
        f"Macro-economic data for context:\n{macro_news}\n"
        f"Financial data for {company_name}:\n{financials}\n"
        f"Recent news headlines for {company_name}:\n{news}\n"
        "Based on the provided financial data and news headlines,"
        " please assign a score (from 1 to 100) reflecting the potential"
        " investment value of"
        f" company {company_name} in the {industry} industry for the next month.\n"
        "First, write a short investment report about the firm situation.\n"
        "Include sections of recent news, financials, valuations, and"
        " economic outlook affecting the firm.\n"
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


def allocation_prompt(top_reports: str) -> str:
    """Exhibit 2E — final 15-asset portfolio allocation prompt."""
    return (
        "Now, I want a 15-asset portfolio where we will invest for the next month "
        "(rebalancing in one month) in a table with weight, thesis, edge, and risk. "
        "Weight this portfolio to perform positively given the market conditions "
        "and to beat the S&P 500. We have the following reports for the stocks that "
        "were scored the highest:\n"
        f"{top_reports}\n"
        "However, we can also invest in most ETFs (except short, leveraged, or vol "
        "because of the monthly horizon), including but not limited to market, "
        "sectors, TIPS, and long and short-term bonds. You decide the weights do "
        "not have to include any or all of the stocks or instruments mentioned. "
        "Remember, a 15-asset portfolio where we will invest for the next month "
        "(rebalancing in one month) in a table with weight, instrument type, "
        "thesis, edge, and risk. You can use both the stock info and your macro "
        "expectations, as well as reasoning about the future and markets."
    )

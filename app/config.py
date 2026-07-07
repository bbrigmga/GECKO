"""Application settings persisted to .env."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import dotenv_values, set_key
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT / ".env"
RUNS_DIR = ROOT / "runs"


class Settings(BaseModel):
    api_provider: str = Field(default="xai", description="xai or openrouter")
    xai_api_key: str = ""
    stocknews_api_key: str = ""
    model: str = "grok-4.3"
    max_tickers: int = Field(default=0, description="0 = full S&P 500")
    concurrency: int = Field(default=8, ge=1, le=32)
    stocknews_items_per_ticker: int = Field(
        default=15,
        ge=1,
        le=50,
        description="Max articles returned per ticker (1 API call per ticker)",
    )
    stocknews_macro_items: int = Field(
        default=25,
        ge=1,
        le=50,
        description="Max articles for general market news (1 API call)",
    )


def load_settings() -> Settings:
    if ENV_PATH.exists():
        values = dotenv_values(ENV_PATH)
    else:
        values = {}
    return Settings(
        api_provider=values.get("API_PROVIDER", os.getenv("API_PROVIDER", "xai")),
        xai_api_key=values.get("XAI_API_KEY", os.getenv("XAI_API_KEY", "")),
        stocknews_api_key=values.get(
            "STOCKNEWS_API_KEY", os.getenv("STOCKNEWS_API_KEY", "")
        ),
        model=values.get("MODEL", os.getenv("MODEL", "grok-4.3")),
        max_tickers=int(values.get("MAX_TICKERS", os.getenv("MAX_TICKERS", "0")) or 0),
        concurrency=int(values.get("CONCURRENCY", os.getenv("CONCURRENCY", "8")) or 8),
        stocknews_items_per_ticker=int(
            values.get(
                "STOCKNEWS_ITEMS_PER_TICKER",
                os.getenv("STOCKNEWS_ITEMS_PER_TICKER", "15"),
            )
            or 15
        ),
        stocknews_macro_items=int(
            values.get(
                "STOCKNEWS_MACRO_ITEMS",
                os.getenv("STOCKNEWS_MACRO_ITEMS", "25"),
            )
            or 25
        ),
    )


def save_settings(settings: Settings) -> None:
    ENV_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not ENV_PATH.exists():
        ENV_PATH.touch()
    set_key(str(ENV_PATH), "API_PROVIDER", settings.api_provider)
    set_key(str(ENV_PATH), "XAI_API_KEY", settings.xai_api_key)
    set_key(str(ENV_PATH), "STOCKNEWS_API_KEY", settings.stocknews_api_key)
    set_key(str(ENV_PATH), "MODEL", settings.model)
    set_key(str(ENV_PATH), "MAX_TICKERS", str(settings.max_tickers))
    set_key(str(ENV_PATH), "CONCURRENCY", str(settings.concurrency))
    set_key(
        str(ENV_PATH),
        "STOCKNEWS_ITEMS_PER_TICKER",
        str(settings.stocknews_items_per_ticker),
    )
    set_key(str(ENV_PATH), "STOCKNEWS_MACRO_ITEMS", str(settings.stocknews_macro_items))

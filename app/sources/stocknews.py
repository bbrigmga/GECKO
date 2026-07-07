"""Stock News API client (Exhibits 2A, 2C)."""

from __future__ import annotations

import re
from typing import Any

import httpx

from app.prompts import NEWS_SOURCES

BASE_URL = "https://stocknewsapi.com/api/v1"
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}

_SOURCE_KEYS = {re.sub(r"[^a-z0-9]", "", s.lower()): s for s in NEWS_SOURCES}


def _normalize_source(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (name or "").lower())


def _matches_source(source: str) -> bool:
    key = _normalize_source(source)
    if not key:
        return False
    for norm in _SOURCE_KEYS:
        if norm in key or key in norm:
            return True
    return False


def _format_article(item: dict[str, Any]) -> str:
    title = item.get("title") or item.get("headline") or ""
    text = item.get("text") or item.get("summary") or item.get("description") or ""
    source = item.get("source_name") or item.get("source") or item.get("news_url", "")
    date = item.get("date") or item.get("published") or ""
    return f"- [{source}] {date}: {title}\n  {text}".strip()


def _extract_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    data = payload.get("data")
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("news", "articles", "items"):
            if isinstance(data.get(key), list):
                return data[key]
    for key in ("news", "articles", "items"):
        if isinstance(payload.get(key), list):
            return payload[key]
    return []


def _response_error_detail(resp: httpx.Response) -> str:
    try:
        body = resp.json()
        if isinstance(body, dict):
            return str(body.get("message") or body.get("error") or body)
    except Exception:  # noqa: BLE001
        pass
    return resp.text[:200] if resp.text else resp.reason_phrase


class StockNewsClient:
    def __init__(self, api_key: str, timeout: float = 60.0) -> None:
        self.api_key = api_key.strip()
        self.timeout = timeout

    async def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        if not self.api_key:
            raise ValueError("Stock News API key is missing")
        params = {**params, "token": self.api_key}
        url = f"{BASE_URL}{path}" if path else BASE_URL
        async with httpx.AsyncClient(timeout=self.timeout, headers=_HEADERS) as client:
            resp = await client.get(url, params=params)
            if resp.status_code >= 400:
                detail = _response_error_detail(resp)
                raise httpx.HTTPStatusError(
                    f"Stock News API {resp.status_code}: {detail}",
                    request=resp.request,
                    response=resp,
                )
            return resp.json()

    def _filter_articles(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        filtered = []
        for item in items:
            source = (
                item.get("source_name")
                or item.get("source")
                or item.get("news_source")
                or ""
            )
            if _matches_source(str(source)):
                filtered.append(item)
        return filtered if filtered else items

    def _format_articles(self, articles: list[dict[str, Any]], items: int) -> str:
        if not articles:
            return ""
        return "\n\n".join(_format_article(a) for a in articles[:items])

    async def get_ticker_news(self, ticker: str, items: int = 50) -> str:
        """Per-ticker news. Tries without date filter first (Basic plan compatibility)."""
        count = min(items, 50)
        attempts: list[dict[str, Any]] = [
            {"tickers": ticker.upper(), "items": count},
            {"tickers": ticker.upper(), "items": count, "date": "last7days"},
        ]
        last_error = ""
        for params in attempts:
            try:
                payload = await self._get("", params)
                articles = self._filter_articles(_extract_items(payload))
                text = self._format_articles(articles, count)
                if text:
                    return text
            except httpx.HTTPStatusError as exc:
                last_error = str(exc)
        if last_error:
            return (
                f"No recent news returned for {ticker}. "
                f"(Stock News API: {last_error})"
            )
        return f"No news found for {ticker}."

    async def get_general_market_news(self, items: int = 50) -> str:
        """Fetch general market news with fallbacks if the category endpoint fails."""
        count = min(items, 50)
        attempts: list[tuple[str, dict[str, Any]]] = [
            ("/category", {"section": "general", "items": count}),
            ("/category", {"section": "general", "items": count, "date": "last7days"}),
            ("", {"tickers": "SPY,QQQ,DIA", "items": count}),
            ("", {"tickers": "SPY,QQQ,DIA", "items": count, "date": "last7days"}),
        ]
        errors: list[str] = []
        for path, params in attempts:
            try:
                payload = await self._get(path, params)
                articles = self._filter_articles(_extract_items(payload))
                text = self._format_articles(articles, count)
                if text:
                    return text
            except httpx.HTTPStatusError as exc:
                errors.append(str(exc))
        hint = (
            "Verify your Stock News API key at stocknewsapi.com and ensure your plan "
            "includes General Market News."
        )
        raise RuntimeError(
            f"Could not fetch market news from Stock News API. {' | '.join(errors)}. {hint}"
        )

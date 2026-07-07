"""Wikimedia / Wikipedia current-events fetcher (Exhibit 2C)."""

from __future__ import annotations

import re
from datetime import datetime, timezone

import httpx
from bs4 import BeautifulSoup

from app.prompts import WIKIPEDIA_URLS

# Official Wikimedia API host — often reachable when en.wikipedia.org blocks bots.
WIKIMEDIA_CORE = "https://api.wikimedia.org/core/v1/wikipedia/en/page"
WIKIMEDIA_FEED = "https://api.wikimedia.org/feed/v1/wikipedia/en/featured"

_HEADERS = {
    "User-Agent": (
        "GrokPortfolioReplicator/1.0 "
        "(https://localhost:8765; monthly portfolio research tool)"
    ),
    "Accept": "application/json, text/html",
}


def _page_slug_from_url(url: str) -> str:
    """Wikipedia URL slug, e.g. 2025_in_the_United_States."""
    return url.rstrip("/").split("/")[-1]


def _page_title_from_slug(slug: str) -> str:
    return slug.replace("_", " ")


def _clean_wikipedia_html(html: str, max_chars: int = 12000) -> str:
    soup = BeautifulSoup(html, "lxml")
    content = soup.find("div", {"id": "mw-content-text"}) or soup.find(
        "div", class_="mw-parser-output"
    )
    if not content:
        return BeautifulSoup(html, "lxml").get_text("\n", strip=True)[:max_chars]
    for tag in content.find_all(["script", "style", "table", "sup", "img", "nav"]):
        tag.decompose()
    text = content.get_text("\n", strip=True)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text[:max_chars]


async def _fetch_page_html(client: httpx.AsyncClient, slug: str) -> str:
    """Fetch article HTML via Wikimedia Core API."""
    resp = await client.get(f"{WIKIMEDIA_CORE}/{slug}/html")
    resp.raise_for_status()
    return _clean_wikipedia_html(resp.text)


def _html_to_text(html: str) -> str:
    return BeautifulSoup(html, "lxml").get_text(" ", strip=True)


async def _fetch_portal_news(client: httpx.AsyncClient) -> str:
    """Wikipedia Portal:Current events style headlines from Wikifeeds."""
    now = datetime.now(timezone.utc)
    path = f"{WIKIMEDIA_FEED}/{now:%Y/%m/%d}"
    resp = await client.get(path)
    resp.raise_for_status()
    data = resp.json()
    news = data.get("news") or []
    if not news:
        return ""
    lines: list[str] = []
    for item in news:
        story = item.get("story") or item.get("text") or ""
        if story:
            lines.append(f"- {_html_to_text(story)}")
            continue
        links = item.get("links") or []
        if links:
            link = links[0]
            title = link.get("titles", {}).get("normalized") or link.get("title", "")
            extract = link.get("extract") or ""
            line = f"- {title}"
            if extract:
                line += f": {_html_to_text(extract)}"
            lines.append(line)
    return "\n".join(lines)


async def fetch_wikipedia_context(urls: list[str] | None = None) -> str:
    urls = urls or WIKIPEDIA_URLS
    sections: list[str] = []

    async with httpx.AsyncClient(
        timeout=60.0,
        headers=_HEADERS,
        follow_redirects=True,
    ) as client:
        # Portal current events (Wikifeeds)
        try:
            news = await _fetch_portal_news(client)
            if news:
                sections.append(f"## Wikipedia Portal — Current Events\n{news}")
        except Exception as exc:  # noqa: BLE001
            sections.append(f"## Wikipedia Portal — Current Events\n(Failed to fetch: {exc})")

        # Exhibit 2C year / country pages via Wikimedia Core API
        for url in urls:
            slug = _page_slug_from_url(url)
            title = _page_title_from_slug(slug)
            try:
                text = await _fetch_page_html(client, slug)
                if text:
                    sections.append(f"## {title}\n{text}")
                else:
                    sections.append(f"## {title}\n(No content returned)")
            except Exception as exc:  # noqa: BLE001
                sections.append(f"## {title}\n(Failed to fetch: {exc})")

    return "\n\n".join(sections) if sections else "No Wikipedia context available."

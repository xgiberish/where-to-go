"""Wikivoyage + Wikipedia scraper for real destination content.

Fetches plain-text page extracts from the Wikivoyage MediaWiki API
(primary) and falls back to the Wikipedia API if the destination has
no Wikivoyage page.  No authentication required.

API reference: https://www.mediawiki.org/wiki/API:Extracts
"""
import asyncio

import httpx
import structlog

from data_processing.config import get_config
from data_processing.utils.rate_limiter import RateLimiter

log = structlog.get_logger()

_HEADERS = {
    "User-Agent": "WhereToGoApp/1.0 (educational project; contact: student@uni.edu)",
}

_MEDIAWIKI_PARAMS = {
    "action": "query",
    "prop": "extracts",
    "explaintext": "1",
    "format": "json",
    "redirects": "1",
}

_MIN_USEFUL_LENGTH = 200  # chars — below this the page is basically empty


class WikivoyageScraper:
    """Async scraper that returns destination text as a list of paragraphs.

    Each paragraph is treated as a "review" by the downstream labeler —
    it is a meaningful, coherent chunk of travel content about the destination.
    """

    def __init__(self) -> None:
        cfg = get_config()
        self._wikivoyage_url = cfg.WIKIVOYAGE_API
        self._wikipedia_url = cfg.WIKIPEDIA_API
        self._min_para_len = cfg.MIN_PARAGRAPH_LENGTH
        self._max_paragraphs = cfg.MAX_PARAGRAPHS
        self._rate_limiter = RateLimiter(requests_per_second=1.0)
        self._client: httpx.AsyncClient | None = None

    # ── Context manager ────────────────────────────────────────────────────────

    async def __aenter__(self) -> "WikivoyageScraper":
        self._client = httpx.AsyncClient(headers=_HEADERS, timeout=30.0)
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    # ── Public API ─────────────────────────────────────────────────────────────

    async def fetch_reviews(self, destination_name: str, country: str) -> list[str]:
        """Return destination content as a list of paragraph-sized text chunks.

        Tries (in order):
          1. Wikivoyage — exact destination name
          2. Wikivoyage — country-qualified name (e.g. "Galle, Sri Lanka")
          3. Wikipedia  — exact destination name

        Returns an empty list if all attempts fail.
        """
        client = self._client or httpx.AsyncClient(headers=_HEADERS, timeout=30.0)

        candidates = [
            (self._wikivoyage_url, destination_name),
            (self._wikivoyage_url, f"{destination_name}, {country}"),
            (self._wikipedia_url, destination_name),
        ]

        for api_url, title in candidates:
            extract = await self._fetch_extract(client, api_url, title)
            if extract and len(extract) >= _MIN_USEFUL_LENGTH:
                paragraphs = self._split_to_paragraphs(extract)
                log.info(
                    "content_fetched",
                    destination=destination_name,
                    source="wikivoyage" if "wikivoyage" in api_url else "wikipedia",
                    title_used=title,
                    paragraphs=len(paragraphs),
                )
                return paragraphs

        log.warning("no_content", destination=destination_name, country=country)
        return []

    # ── Internals ──────────────────────────────────────────────────────────────

    async def _fetch_extract(
        self,
        client: httpx.AsyncClient,
        api_url: str,
        title: str,
    ) -> str:
        await self._rate_limiter.acquire()
        params = {**_MEDIAWIKI_PARAMS, "titles": title}
        try:
            resp = await client.get(api_url, params=params)
            resp.raise_for_status()
            data = resp.json()
            pages = data.get("query", {}).get("pages", {})
            for page in pages.values():
                # pageid == -1 means "page not found"
                if page.get("pageid", -1) != -1 and "extract" in page:
                    return page["extract"].strip()
        except httpx.HTTPError as exc:
            log.warning("http_error", url=api_url, title=title, error=str(exc))
        except Exception as exc:
            log.warning("fetch_error", url=api_url, title=title, error=str(exc))
        return ""

    def _split_to_paragraphs(self, extract: str) -> list[str]:
        """Split plain-text extract into meaningful paragraph chunks.

        MediaWiki explaintext returns sections separated by double newlines.
        Single-newline lines are section headers — we keep them only if
        they're long enough to be actual content.
        """
        raw = extract.split("\n\n")
        paragraphs: list[str] = []
        for chunk in raw:
            chunk = chunk.strip()
            # Skip short chunks (section headers, navigation fragments)
            if len(chunk) < self._min_para_len:
                continue
            # Replace remaining single newlines with spaces to form clean sentences
            chunk = chunk.replace("\n", " ")
            paragraphs.append(chunk)
        return paragraphs[: self._max_paragraphs]

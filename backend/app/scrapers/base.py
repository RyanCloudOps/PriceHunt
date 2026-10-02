import logging
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import ClassVar

import httpx

from app.config import Settings

log = logging.getLogger(__name__)

CENT = Decimal("0.01")

# "1.234,56 €", "€ 71,90", "183€95", "49.99", "2.299€"
_PRICE_RE = re.compile(r"(\d{1,3}(?:[.\s ]\d{3})+|\d+)(?:\s*[,.€]\s*(\d{2})(?!\d))?")
_BLOCK_MARKERS = ("captcha", "/_sec/verify", "bm-verify", "cf-chl", "access denied")


def parse_price(text: str | None) -> Decimal | None:
    if not text:
        return None
    m = _PRICE_RE.search(text.replace(" ", " "))
    if not m:
        return None
    whole = re.sub(r"[.\s ]", "", m.group(1))
    cents = m.group(2) or "00"
    try:
        return Decimal(f"{whole}.{cents}").quantize(CENT)
    except InvalidOperation:
        return None


@dataclass
class ScrapedItem:
    external_id: str
    title: str
    url: str
    price: Decimal
    original_price: Decimal | None = None
    image_url: str | None = None
    currency: str = "EUR"
    description: str | None = None  # solo para clasificar cuando el título es solo el modelo

    @property
    def discount_pct(self) -> float:
        if not self.original_price or self.original_price <= self.price:
            return 0.0
        return round(float((1 - self.price / self.original_price) * 100), 1)


class ScraperError(Exception):
    pass


class BlockedError(ScraperError):
    """La tienda ha devuelto un captcha / challenge anti-bot."""


class Scraper(ABC):
    key: ClassVar[str]

    def __init__(self, settings: Settings, client: httpx.Client | None = None):
        self.settings = settings
        self.client = client or httpx.Client(
            timeout=settings.http_timeout_seconds,
            follow_redirects=True,
            headers={
                "User-Agent": settings.user_agent,
                "Accept-Language": "es-ES,es;q=0.9",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
        )
        self._last_request = 0.0

    @classmethod
    def available(cls, settings: Settings) -> bool:
        return True

    @abstractmethod
    def search(self, query: str) -> list[ScrapedItem]: ...

    def fetch(self, url: str, **kwargs) -> str:
        # Peticiones educadas: una cada `scrape_delay_seconds` como mínimo
        wait = self.settings.scrape_delay_seconds - (time.monotonic() - self._last_request)
        if wait > 0:
            time.sleep(wait)
        self._last_request = time.monotonic()
        try:
            resp = self.client.get(url, **kwargs)
        except httpx.HTTPError as exc:
            raise ScraperError(f"{self.key}: error de red {exc!r}") from exc
        if resp.status_code in (403, 429, 503):
            raise BlockedError(f"{self.key}: HTTP {resp.status_code} en {url}")
        if resp.status_code >= 400:
            raise ScraperError(f"{self.key}: HTTP {resp.status_code} en {url}")
        head = resp.text[:4000].lower()
        if len(resp.text) < 5000 and any(m in head for m in _BLOCK_MARKERS):
            raise BlockedError(f"{self.key}: challenge anti-bot en {url}")
        return resp.text

    def close(self) -> None:
        self.client.close()

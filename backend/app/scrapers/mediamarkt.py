import json
import re
from decimal import Decimal
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from app.scrapers.base import ScrapedItem, Scraper, parse_price

_AMOUNT_RE = re.compile(r"\d{1,3}(?:\.\d{3})*,\d{2}\s*€")
_ID_RE = re.compile(r"-(\d+)\.html")


class MediaMarktScraper(Scraper):
    """Precio actual desde JSON-LD; precio tachado desde la tarjeta de producto."""

    key = "mediamarkt"
    base = "https://www.mediamarkt.es"

    def search(self, query: str) -> list[ScrapedItem]:
        # Entre comillas: una marca exacta sin comillas redirige a su landing (/es/brand/x),
        # que no tiene listado. Así se obtienen productos de todas las categorías.
        items: list[ScrapedItem] = []
        seen: set[str] = set()
        for page in range(1, self.settings.max_pages + 1):
            params: dict[str, str | int] = {"query": f'"{query}"'}
            if page > 1:
                params["page"] = page
            batch = [
                i
                for i in self.parse(self.fetch(f"{self.base}/es/search.html", params=params))
                if i.external_id not in seen
            ]
            if not batch:
                break
            seen.update(i.external_id for i in batch)
            items.extend(batch)
        return items

    @classmethod
    def parse(cls, html: str) -> list[ScrapedItem]:
        soup = BeautifulSoup(html, "html.parser")

        originals: dict[str, Decimal] = {}
        for card in soup.select('[data-test="mms-product-card"]'):
            link = card.select_one("a[href]")
            if not link:
                continue
            amounts = {parse_price(a) for a in _AMOUNT_RE.findall(card.get_text(" "))}
            amounts.discard(None)
            if len(amounts) >= 2:
                originals[urljoin(cls.base, link["href"])] = max(amounts)

        items: list[ScrapedItem] = []
        for script in soup.select('script[type="application/ld+json"]'):
            try:
                data = json.loads(script.string or "")
            except json.JSONDecodeError:
                continue
            if data.get("@type") != "ItemList":
                continue
            for entry in data.get("itemListElement", []):
                product = entry.get("item") or {}
                offer = product.get("offers") or {}
                url = product.get("url")
                if not (url and product.get("name") and offer.get("price") is not None):
                    continue
                m = _ID_RE.search(url)
                price = Decimal(str(offer["price"])).quantize(Decimal("0.01"))
                original = originals.get(url)
                items.append(
                    ScrapedItem(
                        external_id=m.group(1) if m else url,
                        title=product["name"],
                        url=url,
                        price=price,
                        original_price=original if original and original > price else None,
                        image_url=product.get("image"),
                        currency=offer.get("priceCurrency", "EUR"),
                    )
                )
        return items

import json
import re
from decimal import Decimal
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from app.scrapers.base import BlockedError, ScrapedItem, Scraper, ScraperError

_NEXT_DATA_RE = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)

# Categorías de la tienda oficial (las páginas /c/ traen hasta 24 productos ya renderizados;
# la búsqueda solo trae 6 y el resto se carga desde el navegador, así que no sirve).
CATEGORIES = (
    "gaming-furniture/gaming-desks",
    "gaming-furniture/gaming-chairs",
    "gaming-furniture",
    "gaming-computers",
    "monitors",
    "keyboards",
    "gaming-mouse",
    "gaming-headsets",
    "mousepads",
    "memory",
    "pc-cases",
    "psu",
    "cpu-coolers",
    "case-fans",
)


class CorsairScraper(Scraper):
    """Tienda oficial de Corsair: escritorios, sillas y periféricos de su propio catálogo."""

    key = "corsair"
    base = "https://www.corsair.com"
    brand = "corsair"

    def search(self, query: str) -> list[ScrapedItem]:
        # Es una tienda de una sola marca: solo tiene sentido con el término "corsair"
        if query.lower() != self.brand:
            return []
        items: dict[str, ScrapedItem] = {}
        errors: list[ScraperError] = []
        for category in CATEGORIES:
            try:
                html = self.fetch(f"{self.base}/es/es/c/{category}")
            except BlockedError:
                raise
            except ScraperError as exc:
                errors.append(exc)
                continue
            for item in self.parse(html):
                items.setdefault(item.external_id, item)
        if not items and errors:
            raise errors[0]
        return list(items.values())

    @classmethod
    def parse(cls, html: str) -> list[ScrapedItem]:
        m = _NEXT_DATA_RE.search(html)
        if not m:
            return []
        try:
            products = _find_products(json.loads(m.group(1)))
        except ValueError:
            return []
        links = _product_links(html)
        items: list[ScrapedItem] = []
        for p in products:
            sku = p.get("sku")
            price = ((p.get("price_range") or {}).get("minimum_price")) or {}
            final = (price.get("final_price") or {}).get("value")
            regular = (price.get("regular_price") or {}).get("value")
            if not (sku and p.get("name") and final) or p.get("stock_status") != "IN_STOCK":
                continue
            title = p["name"]
            # Muchos títulos no llevan la marca ("Silla para juegos TC100"): hace falta para
            # que pasen el filtro de marca del refresco.
            if cls.brand not in title.lower():
                title = f"Corsair {title}"
            # La búsqueda devuelve miniaturas de 96 px: se pide el mismo recurso a 400 px
            image = ((p.get("image") or {}).get("url") or "").replace("w_96", "w_400") or None
            items.append(
                ScrapedItem(
                    external_id=str(sku),
                    title=title,
                    url=links.get(str(sku).lower()) or f"{cls.base}/es/es/search?q={sku}",
                    price=_money(final),
                    original_price=_money(regular) if regular else None,
                    image_url=image,
                    description=_description(p),
                )
            )
        return items


def _money(value) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"))


def _find_products(node) -> list[dict]:
    """Localiza la lista `items` del resultado (la ruta cambia entre búsqueda y categoría)."""
    if isinstance(node, dict):
        if isinstance(node.get("items"), list) and "page_info" in node:
            return node["items"]
        for value in node.values():
            if found := _find_products(value):
                return found
    elif isinstance(node, list):
        for value in node:
            if found := _find_products(value):
                return found
    return []


def _product_links(html: str) -> dict[str, str]:
    """sku (minúsculas) → URL de ficha. El slug de la URL no sale del JSON, solo del HTML."""
    links: dict[str, str] = {}
    for a in BeautifulSoup(html, "html.parser").select('a[href*="/es/es/p/"]'):
        href = a["href"].split("?")[0]
        parts = href.rstrip("/").split("/")
        if "p" in parts and len(parts) > parts.index("p") + 2:
            sku = parts[parts.index("p") + 2].lower()
            links.setdefault(sku, urljoin(CorsairScraper.base, href))
    return links


def _html_text(html: str | None) -> str | None:
    if not html:
        return None
    return BeautifulSoup(html, "html.parser").get_text(" ", strip=True) or None


def _description(product: dict) -> str | None:
    """Categoría de la tienda + texto: títulos como "Embrace" solo se clasifican por ahí."""
    cats = " ".join(c["name"] for c in product.get("categories") or [] if c.get("name"))
    text = _html_text((product.get("description") or {}).get("html"))
    return " ".join(part for part in (cats, text) if part) or None

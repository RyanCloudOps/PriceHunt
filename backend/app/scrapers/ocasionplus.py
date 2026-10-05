import json
import re
from decimal import Decimal, InvalidOperation

from app.scrapers.base import ScrapedItem, Scraper, ScraperError

MAX_PAGES = 15  # 20 coches por página; a 2 s por petición son ~30 s por marca
_LD_JSON_RE = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.S)


class OcasionPlusScraper(Scraper):
    """OcasionPlus (concesionarios propios): coches de ocasión baratos, rebajados o no.

    Su robots.txt permite el listado por marca y `?page=N`, pero prohíbe los filtros por
    parámetro (precio, km, `sort`…). Por eso se pagina el listado de cada marca y el límite
    de precio y de kilómetros se aplican aquí, en local.
    """

    key = "ocasionplus"
    base = "https://www.ocasionplus.com"

    def search(self, query: str) -> list[ScrapedItem]:
        slug = re.sub(r"[^a-z0-9]+", "-", query.lower()).strip("-")
        items: dict[str, ScrapedItem] = {}
        seen: set[str] = set()
        for page in range(1, min(MAX_PAGES, self.settings.max_pages) + 1):
            url = f"{self.base}/coches-segunda-mano/{slug}" + (f"?page={page}" if page > 1 else "")
            try:
                found, listed = self.parse(
                    self.fetch(url), self.settings.car_max_price, self.settings.car_max_km
                )
            except ScraperError as exc:
                if page == 1 and "HTTP 404" in str(exc):
                    return []  # marca que OcasionPlus no tiene
                raise
            items.update((i.external_id, i) for i in found)
            fresh = listed - seen
            seen |= listed
            # Sin coches nuevos (página vacía o repetida): no hay más listado
            if not fresh:
                break
        return list(items.values())

    @classmethod
    def parse(
        cls, html: str, max_price: int, max_km: int = 0
    ) -> tuple[list[ScrapedItem], set[str]]:
        """Devuelve los coches dentro de presupuesto y los ids de todos los listados."""
        out: list[ScrapedItem] = []
        listed: set[str] = set()
        for block in _LD_JSON_RE.findall(html):
            try:
                data = json.loads(block)
            except ValueError:
                continue
            if data.get("@type") != "ItemList":
                continue
            for entry in data.get("itemListElement", []):
                try:
                    listed.add(cls._external_id(entry))
                    item = cls._parse_vehicle(entry, max_price, max_km)
                except (KeyError, TypeError, ValueError, InvalidOperation):
                    continue
                if item:
                    out.append(item)
        return out, listed

    @staticmethod
    def _external_id(entry: dict) -> str:
        return entry["offers"]["url"].rstrip("/").rsplit("-", 1)[-1]

    @classmethod
    def _parse_vehicle(cls, entry: dict, max_price: int, max_km: int) -> ScrapedItem | None:
        offer = entry["offers"]
        price = Decimal(str(offer["price"]))
        if not 0 < price <= max_price or "InStock" not in offer.get("availability", "InStock"):
            return None
        url = offer["url"]
        brand = entry["brand"]["name"]
        model = entry.get("model") or entry["name"]
        title = model if model.lower().startswith(brand.lower()) else f"{brand} {model}"
        km = entry.get("mileageFromOdometer", {}).get("value")
        if max_km and km and km > max_km:
            return None
        year = (entry.get("productionDate") or "")[:4]
        details = [year, f"{km:,} km".replace(",", ".") if km else None, entry.get("fuelType")]
        title = " · ".join([title, *[d for d in details if d]])
        return ScrapedItem(
            external_id=cls._external_id(entry),
            title=title,
            url=url,
            price=price,
            image_url=entry.get("image"),
            category=f"Hasta {max_price:,} €".replace(",", "."),
            curated=True,
        )

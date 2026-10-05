import json
from decimal import Decimal, InvalidOperation
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from app.scrapers.base import ScrapedItem, Scraper, ScraperError

# Marcas del grupo con coches de ocasión en Das WeltAuto (concesionarios oficiales).
BRANDS = ("seat", "cupra", "skoda", "volkswagen", "audi")
PAGE_SIZE = 23
# La web usa "Todo terreno", "Suv"…: unificamos nombres para que los filtros queden limpios
BODY_TYPES = {"todo terreno": "SUV", "suv": "SUV", "monovolumen": "Monovolumen"}
MAX_PAGES = 5


class DasWeltAutoScraper(Scraper):
    """Das WeltAuto (red oficial de concesionarios del grupo VW): solo coches rebajados.

    La web permite este tipo de acceso en su robots.txt. Filtra con `descuento_desde=1`
    (la propia web marca esos coches como rebajados) pero no publica el precio anterior;
    ese lo reconstruye el refresco a partir del historial de precios.
    """

    key = "dasweltauto"
    base = "https://www.dasweltauto.es"

    def search(self, query: str) -> list[ScrapedItem]:
        brand = query.lower()
        if brand not in BRANDS:
            return []
        items: dict[str, ScrapedItem] = {}
        for page in range(1, MAX_PAGES + 1):
            url = (
                f"{self.base}/esp/coches-seleccion/{brand}"
                f"?condicion%5Bdescuento_desde%5D=1&pagina={page}"
            )
            found = self.parse(self.fetch(url))
            new = [i for i in found if i.external_id not in items]
            items.update((i.external_id, i) for i in new)
            # La web repite la última página en vez de dar error: paramos al no ver nada nuevo
            if len(found) < PAGE_SIZE or not new:
                break
        return list(items.values())

    @classmethod
    def parse(cls, html: str) -> list[ScrapedItem]:
        soup = BeautifulSoup(html, "html.parser")
        out: list[ScrapedItem] = []
        for card in soup.select("article[data-car-id]"):
            try:
                item = cls._parse_card(card)
            except (ValueError, KeyError, InvalidOperation, ScraperError):
                continue
            if item:
                out.append(item)
        return out

    @staticmethod
    def _body_type(cfg: dict) -> str:
        name = (cfg.get("BodyType", {}).get("Name") or "").strip()
        return BODY_TYPES.get(name.lower()) or name.capitalize() or "Coches"

    @classmethod
    def _parse_card(cls, card) -> ScrapedItem | None:
        cfg = json.loads(card["data-configuration"])
        price = Decimal(cfg["Budget"]["Price"]["price"])
        link = card.select_one("a.enlaceficha[href]")
        if price <= 0 or link is None:
            return None
        vehicle = cfg.get("Vehicle", {})
        if vehicle.get("Sold") == "true" or vehicle.get("Reserved") == "true":
            return None

        brand = cfg["VehicleManufacturer"]
        name = cfg["Model"]["Name"]
        title = name if name.lower().startswith(brand.lower()) else f"{brand} {name}"
        details = [
            cfg.get("Production", {}).get("Year"),
            vehicle.get("Milage"),
            cfg.get("Engine", {}).get("FuelType", {}).get("Main"),
        ]
        title = " · ".join([title, *[d for d in details if d]])

        image = None
        source = card.select_one("picture source[data-srcset]")
        if source:
            image = source["data-srcset"].split(" ")[0].replace("&amp;", "&")
        return ScrapedItem(
            external_id=str(card["data-car-id"]),
            title=title,
            url=urljoin(cls.base, link["href"]),
            price=price,
            image_url=image,
            category=cls._body_type(cfg),
            curated=True,
        )

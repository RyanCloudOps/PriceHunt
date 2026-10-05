"""Datos sintéticos para CI, demos y desarrollo offline (DEMO_MODE=true).

Los precios cambian cada día (semilla = fecha), así se puede ver en local cómo
el refresco diario actualiza y caduca ofertas sin tocar webs reales.
"""

import hashlib
import random
from datetime import date
from decimal import Decimal
from urllib.parse import quote_plus

from app.config import Settings
from app.scrapers.base import ScrapedItem, Scraper

CATALOG: dict[str, list[tuple[str, int]]] = {
    "corsair": [
        ("Corsair K70 RGB PRO Teclado mecánico Cherry MX Red", 159),
        ("Corsair K65 PLUS WIRELESS Teclado gaming 75%", 159),
        ("Corsair M75 AIR Ratón gaming inalámbrico 26000 DPI", 149),
        ("Corsair SABRE v2 PRO Ratón ultraligero", 139),
        ("Corsair HS80 MAX Auriculares inalámbricos", 179),
        ("Corsair VIRTUOSO PRO Auriculares streaming", 199),
        ("Corsair MM700 RGB Alfombrilla extendida", 69),
        ("Corsair iCUE H150i ELITE Refrigeración líquida 360 mm", 239),
        ("Corsair RM850e Fuente de alimentación 80 Plus Gold", 129),
        ("Corsair Vengeance RGB DDR5 32GB 6000MHz Memoria", 139),
        ("Corsair 4000D Airflow Caja torre ATX", 109),
        ("Corsair Platform:6 Escritorio gaming con bastidores", 299),
        ("Corsair Platform:4 Escritorio gaming regulable", 249),
        ("Corsair Platform:6 Extensión de escritorio madera", 79),
        ("Corsair Multi Frame Panel perforado para escritorio", 49),
        ("Corsair TC100 RELAXED Silla gaming tela", 249),
        ("Corsair TC500 Silla gaming ergonómica", 599),
    ],
    "logitech": [
        ("Logitech G PRO X SUPERLIGHT 2 Ratón gaming", 169),
        ("Logitech G915 X Teclado mecánico inalámbrico", 249),
        ("Logitech G PRO X 2 Auriculares LIGHTSPEED", 259),
        ("Logitech MX Master 3S Ratón", 119),
        ("Logitech G640 Alfombrilla", 39),
    ],
    "razer": [
        ("Razer DeathAdder V3 Pro Ratón gaming", 169),
        ("Razer BlackWidow V4 Teclado mecánico", 179),
        ("Razer BlackShark V2 Pro Auriculares", 199),
        ("Razer Seiren V3 Micrófono streaming", 129),
    ],
    "steelseries": [
        ("SteelSeries Apex Pro TKL Teclado gaming", 239),
        ("SteelSeries Arctis Nova Pro Auriculares", 349),
        ("SteelSeries Aerox 5 Ratón", 89),
    ],
    "hyperx": [
        ("HyperX Cloud III Wireless Auriculares", 169),
        ("HyperX Alloy Origins 65 Teclado mecánico", 99),
        ("HyperX Pulsefire Haste 2 Ratón", 59),
    ],
}

# (título, precio de lista, carrocería)
CARS: dict[str, list[tuple[str, int, str]]] = {
    "seat": [
        ("SEAT Ateca 1.0 TSI Style 115 CV · 2024 · 18.400 km · Gasolina", 24900, "SUV"),
        ("SEAT Arona 1.0 TSI FR 110 CV · 2023 · 22.100 km · Gasolina", 19800, "SUV"),
        ("SEAT Ibiza 1.0 TSI Style 95 CV · 2023 · 15.300 km · Gasolina", 15900, "Utilitario"),
        ("SEAT León 1.5 eTSI FR 150 CV · 2024 · 9.800 km · Híbrido", 24500, "Compacto"),
    ],
    "cupra": [
        ("CUPRA Formentor 1.5 TSI 150 CV · 2023 · 21.000 km · Gasolina", 29900, "SUV"),
        ("CUPRA Born 58 kWh 204 CV · 2023 · 12.700 km · Eléctrico", 31900, "Compacto"),
        ("CUPRA León 1.5 eTSI 150 CV · 2024 · 7.500 km · Híbrido", 27800, "Compacto"),
    ],
    "skoda": [
        ("Skoda Octavia 2.0 TDI Style 116 CV · 2023 · 31.000 km · Diésel", 25900, "Familiar"),
        ("Skoda Kodiaq 2.0 TDI 150 CV · 2022 · 44.000 km · Diésel", 32500, "SUV"),
        ("Skoda Fabia 1.0 TSI Style 95 CV · 2024 · 6.400 km · Gasolina", 16900, "Utilitario"),
    ],
    "volkswagen": [
        ("Volkswagen Golf 1.5 eTSI Life 130 CV · 2023 · 19.800 km · Híbrido", 25900, "Compacto"),
        ("Volkswagen T-Roc 1.0 TSI Advance 110 CV · 2023 · 25.600 km · Gasolina", 23500, "SUV"),
        ("Volkswagen ID.3 Pro 58 kWh 204 CV · 2023 · 14.200 km · Eléctrico", 28900, "Compacto"),
    ],
    "audi": [
        ("Audi A3 Sportback 30 TFSI 110 CV · 2023 · 17.000 km · Gasolina", 28900, "Compacto"),
        ("Audi Q3 35 TDI S line 150 CV · 2022 · 39.500 km · Diésel", 36900, "SUV"),
    ],
}


class DemoScraper(Scraper):
    key = "demo"

    def __init__(self, settings: Settings, store_slug: str = "demo", search_url: str | None = None):
        super().__init__(settings)
        self.store_slug = store_slug
        self.search_url = search_url

    def search(self, query: str) -> list[ScrapedItem]:
        rng = random.Random(f"{self.store_slug}:{query}:{date.today().isoformat()}")
        cars = {t: (b, body) for t, b, body in CARS.get(query.lower(), [])}
        products = [(t, b) for t, (b, _) in cars.items()] or CATALOG.get(query.lower(), [])
        picked = rng.sample(products, k=min(len(products), rng.randint(2, 5)))
        items = []
        for title, base in picked:
            original = Decimal(base) + Decimal("0.99") - 1
            choices = (
                [4, 6, 8, 10, 12] if title in cars else [8, 10, 12, 15, 18, 20, 25, 30, 35, 40, 45]
            )
            discount = Decimal(rng.choice(choices))
            price = (original * (100 - discount) / 100).quantize(Decimal("0.01"))
            url = (
                self.search_url.format(query=quote_plus(title))
                if self.search_url
                else f"https://example.com/{quote_plus(title)}"
            )
            items.append(
                ScrapedItem(
                    external_id="demo-" + hashlib.sha1(title.encode()).hexdigest()[:12],
                    title=title,
                    url=url,
                    price=price,
                    original_price=original,
                    category=cars[title][1] if title in cars else None,
                )
            )
        return items

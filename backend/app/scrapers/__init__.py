from app.config import Settings
from app.models import Store
from app.scrapers.amazon import AmazonPaapiScraper
from app.scrapers.base import BlockedError, ScrapedItem, Scraper, ScraperError, parse_price
from app.scrapers.demo import DemoScraper
from app.scrapers.ldlc import LdlcScraper
from app.scrapers.mediamarkt import MediaMarktScraper

REGISTRY: dict[str, type[Scraper]] = {
    cls.key: cls for cls in (AmazonPaapiScraper, LdlcScraper, MediaMarktScraper)
}


def build_scraper(store: Store, settings: Settings) -> Scraper | None:
    """Devuelve el scraper de la tienda, o None si es solo acceso directo / no configurado."""
    if not store.scraper:
        return None
    if settings.demo_mode:
        return DemoScraper(settings, store_slug=store.slug, search_url=store.search_url)
    cls = REGISTRY.get(store.scraper)
    if cls is None or not cls.available(settings):
        return None
    return cls(settings)


__all__ = [
    "REGISTRY",
    "BlockedError",
    "ScrapedItem",
    "Scraper",
    "ScraperError",
    "build_scraper",
    "parse_price",
]

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Store, WatchTerm

DEFAULT_STORES = [
    {
        "slug": "amazon",
        "name": "Amazon.es",
        "base_url": "https://www.amazon.es",
        "shortcut_url": "https://www.amazon.es/gp/goldbox",
        "search_url": "https://www.amazon.es/s?k={query}",
        "accent_color": "#ff9900",
        "scraper": "amazon",
    },
    {
        "slug": "ldlc",
        "name": "LDLC",
        "base_url": "https://www.ldlc.com/es-es/",
        "shortcut_url": "https://www.ldlc.com/es-es/",
        "search_url": "https://www.ldlc.com/es-es/buscar/{query}/",
        "accent_color": "#1d6fb8",
        "scraper": "ldlc",
    },
    {
        "slug": "mediamarkt",
        "name": "MediaMarkt",
        "base_url": "https://www.mediamarkt.es",
        "shortcut_url": "https://www.mediamarkt.es/es/",
        "search_url": "https://www.mediamarkt.es/es/search.html?query={query}",
        "accent_color": "#df0000",
        "scraper": "mediamarkt",
    },
    {
        "slug": "pccomponentes",
        "name": "PcComponentes",
        "base_url": "https://www.pccomponentes.com",
        "shortcut_url": "https://www.pccomponentes.com/",
        "search_url": "https://www.pccomponentes.com/buscar/?query={query}",
        "accent_color": "#ff6000",
        "scraper": None,
    },
    {
        "slug": "coolmod",
        "name": "Coolmod",
        "base_url": "https://www.coolmod.com",
        "shortcut_url": "https://www.coolmod.com",
        "search_url": None,
        "accent_color": "#00a0e3",
        "scraper": None,
    },
    {
        "slug": "alternate",
        "name": "Alternate",
        "base_url": "https://www.alternate.es",
        "shortcut_url": "https://www.alternate.es/",
        "search_url": "https://www.alternate.es/listing.xhtml?q={query}",
        "accent_color": "#d4002a",
        "scraper": None,
    },
    {
        "slug": "corsair",
        "name": "Corsair Store",
        "base_url": "https://www.corsair.com/es/es/",
        "shortcut_url": "https://www.corsair.com/es/es/",
        "search_url": None,
        "accent_color": "#ece81a",
        "scraper": None,
    },
]

DEFAULT_TERMS = ["corsair", "logitech", "razer", "steelseries", "hyperx"]


def seed_defaults(session: Session) -> None:
    """Idempotente: solo inserta si las tablas están vacías."""
    if not session.scalar(select(func.count()).select_from(Store)):
        session.add_all(Store(**data) for data in DEFAULT_STORES)
    if not session.scalar(select(func.count()).select_from(WatchTerm)):
        session.add_all(WatchTerm(query=q) for q in DEFAULT_TERMS)
    session.commit()

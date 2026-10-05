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
        "scraper": "alternate",
    },
    {
        "slug": "corsair",
        "name": "Corsair Store",
        "base_url": "https://www.corsair.com/es/es/",
        "shortcut_url": "https://www.corsair.com/es/es/",
        "search_url": "https://www.corsair.com/es/es/search?q={query}",
        "accent_color": "#ece81a",
        "scraper": "corsair",
    },
]

DEFAULT_TERMS = ["corsair", "logitech", "razer", "steelseries", "hyperx"]

CAR_STORES = [
    {
        "slug": "dasweltauto",
        "name": "Das WeltAuto",
        "base_url": "https://www.dasweltauto.es",
        "shortcut_url": "https://www.dasweltauto.es/esp/coches-oportunidad",
        "search_url": "https://www.dasweltauto.es/esp/coches-seleccion/{query}",
        "accent_color": "#00a1e0",
        "scraper": "dasweltauto",
        "vertical": "cars",
    },
    {
        "slug": "ocasionplus",
        "name": "OcasionPlus",
        "base_url": "https://www.ocasionplus.com",
        "shortcut_url": "https://www.ocasionplus.com/coches-segunda-mano",
        "search_url": "https://www.ocasionplus.com/coches-segunda-mano/{query}",
        "accent_color": "#0b8f5a",
        "scraper": "ocasionplus",
        "vertical": "cars",
    },
    {
        # robots.txt del portal: Disallow / para todos los bots, así que solo es un acceso directo
        "slug": "subastas-boe",
        "name": "Subastas BOE (vehículos)",
        "base_url": "https://subastas.boe.es",
        "shortcut_url": "https://subastas.boe.es/",
        "search_url": None,
        "accent_color": "#8a1c1c",
        "scraper": None,
        "vertical": "cars",
    },
]

CAR_TERMS = ["seat", "cupra", "skoda", "volkswagen", "audi"]
# Marcas con muchos coches de ocasión baratos (OcasionPlus)
CAR_TERMS_BUDGET = [
    "toyota",
    "renault",
    "dacia",
    "citroen",
    "peugeot",
    "opel",
    "ford",
    "fiat",
    "kia",
    "hyundai",
    "nissan",
]


def seed_defaults(session: Session) -> None:
    """Idempotente: solo inserta si las tablas están vacías."""
    if not session.scalar(select(func.count()).select_from(Store)):
        session.add_all(Store(**data) for data in DEFAULT_STORES)
    else:
        _enable_new_scrapers(session)
    if not session.scalar(select(func.count()).select_from(WatchTerm)):
        session.add_all(WatchTerm(query=q) for q in DEFAULT_TERMS)
    _add_car_defaults(session)
    session.commit()


def _add_car_defaults(session: Session) -> None:
    """Bases de datos anteriores al modo coches: añade sus tiendas y marcas una sola vez."""
    slugs = set(session.scalars(select(Store.slug)))
    session.add_all(Store(**data) for data in CAR_STORES if data["slug"] not in slugs)
    # Solo la primera vez que se añade cada tienda: si el usuario borra marcas, no reaparecen
    queries = set(session.scalars(select(WatchTerm.query)))
    wanted = [
        *(CAR_TERMS if "dasweltauto" not in slugs else []),
        *(CAR_TERMS_BUDGET if "ocasionplus" not in slugs else []),
    ]
    session.add_all(WatchTerm(query=q, vertical="cars") for q in wanted if q not in queries)


def _enable_new_scrapers(session: Session) -> None:
    """Bases de datos anteriores: las tiendas que eran solo acceso directo y ahora tienen
    scraper lo reciben. Solo se toca `scraper`/`search_url` si estaban vacíos."""
    existing = {s.slug: s for s in session.scalars(select(Store))}
    for data in DEFAULT_STORES:
        store = existing.get(data["slug"])
        if store is None or store.scraper or not data["scraper"]:
            continue
        store.scraper = data["scraper"]
        store.search_url = store.search_url or data["search_url"]

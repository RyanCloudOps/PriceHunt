import json
from datetime import UTC, datetime
from decimal import Decimal

import httpx
import pytest
import respx

from app.config import Settings
from app.scrapers import BlockedError, build_scraper, parse_price
from app.scrapers.alternate import AlternateScraper
from app.scrapers.amazon import AmazonPaapiScraper, sigv4_headers
from app.scrapers.corsair import CATEGORIES, CorsairScraper
from app.scrapers.dasweltauto import DasWeltAutoScraper
from app.scrapers.demo import DemoScraper
from app.scrapers.ldlc import LdlcScraper
from app.scrapers.mediamarkt import MediaMarktScraper
from app.scrapers.ocasionplus import OcasionPlusScraper
from app.services.classify import categorize, matches_brand


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("1.234,56 €", "1234.56"),
        ("€ 71,90", "71.90"),
        ("183€95", "183.95"),
        ("99€<sup>90</sup>", "99.90"),
        ("49.99", "49.99"),
        ("2.299€", "2299.00"),
        ("1234,50", "1234.50"),
        ("sin precio", None),
        ("", None),
    ],
)
def test_parse_price(text, expected):
    result = parse_price(text.replace("<sup>", "").replace("</sup>", ""))
    assert result == (Decimal(expected) if expected else None)


LDLC_HTML = """
<ul>
<li class="pdt-item" data-id="AR1">
  <div class="pic"><a href="/es-es/ficha/PB1.html"><img src="https://media.ldlc.com/a.jpg"></a></div>
  <h3 class="title-3"><a href="/es-es/ficha/PB1.html">Corsair 5000D RGB Airflow (Blanco)</a></h3>
  <div class="price"><div class="old-price">183€<sup>95</sup></div><div class="new-price">99€<sup>90</sup></div></div>
</li>
<li class="pdt-item" data-id="AR2">
  <h3 class="title-3"><a href="/es-es/ficha/PB2.html">Corsair RM850e</a></h3>
  <p class="desc">Fuente de alimentación modular ATX 850W</p>
  <div class="price">121€<sup>95</sup></div>
</li>
<li class="pdt-item"><h3 class="title-3"><a href="/x">Sin id</a></h3></li>
</ul>
"""


def test_ldlc_parse():
    items = LdlcScraper.parse(LDLC_HTML)
    assert len(items) == 2
    deal, normal = items
    assert deal.external_id == "AR1"
    assert deal.url == "https://www.ldlc.com/es-es/ficha/PB1.html"
    assert deal.price == Decimal("99.90")
    assert deal.original_price == Decimal("183.95")
    assert deal.discount_pct == pytest.approx(45.7, abs=0.1)
    assert normal.original_price is None and normal.discount_pct == 0
    assert deal.description is None
    assert normal.description == "Fuente de alimentación modular ATX 850W"


MM_HTML = """
<script type="application/ld+json">{"@context":"https://schema.org","@type":"ItemList","itemListElement":[
 {"@type":"ListItem","position":1,"item":{"@type":"Product","name":"Ratón gaming - Corsair Harpoon V2",
  "image":"https://assets.mmsrg.com/x","offers":{"@type":"Offer","price":49.99,"priceCurrency":"EUR"},
  "url":"https://www.mediamarkt.es/es/product/_raton-corsair-harpoon-1672263.html"}},
 {"@type":"ListItem","position":2,"item":{"@type":"Product","name":"Teclado Corsair K65",
  "offers":{"@type":"Offer","price":99.0,"priceCurrency":"EUR"},
  "url":"https://www.mediamarkt.es/es/product/_teclado-k65-555.html"}}
]}</script>
<script type="application/ld+json">{"@type":"BreadcrumbList"}</script>
<div data-test="mms-product-card">
  <a href="/es/product/_raton-corsair-harpoon-1672263.html">x</a>
  <span>-28%</span><span>69,99 €</span><span>49,99 €</span>
</div>
<div data-test="mms-product-card"><a href="/es/product/_teclado-k65-555.html">x</a><span>99,00 €</span></div>
"""


def test_mediamarkt_parse():
    items = MediaMarktScraper.parse(MM_HTML)
    assert [i.external_id for i in items] == ["1672263", "555"]
    assert items[0].price == Decimal("49.99")
    assert items[0].original_price == Decimal("69.99")
    assert items[1].original_price is None


def test_amazon_parse_v1_and_v2():
    data = {
        "SearchResult": {
            "Items": [
                {
                    "ASIN": "B0TEST1",
                    "DetailPageURL": "https://www.amazon.es/dp/B0TEST1?tag=x",
                    "ItemInfo": {"Title": {"DisplayValue": "Corsair K70"}},
                    "Images": {"Primary": {"Large": {"URL": "https://m.media-amazon.com/i.jpg"}}},
                    "Offers": {
                        "Listings": [{"Price": {"Amount": 99.9}, "SavingBasis": {"Amount": 149.99}}]
                    },
                },
                {
                    "ASIN": "B0TEST2",
                    "ItemInfo": {"Title": {"DisplayValue": "Corsair M75"}},
                    "OffersV2": {
                        "Listings": [
                            {
                                "Price": {
                                    "Money": {"Amount": 80},
                                    "SavingBasis": {"Money": {"Amount": 100}},
                                }
                            }
                        ]
                    },
                },
                {"ASIN": "B0NOPRICE", "ItemInfo": {"Title": {"DisplayValue": "Sin oferta"}}},
            ]
        }
    }
    items = AmazonPaapiScraper.parse(data)
    assert [i.external_id for i in items] == ["B0TEST1", "B0TEST2"]
    assert items[0].original_price == Decimal("149.99")
    assert items[1].discount_pct == 20.0
    assert items[1].url == "https://www.amazon.es/dp/B0TEST2"


def test_sigv4_headers_shape():
    headers = sigv4_headers(
        access_key="AKID",
        secret_key="secret",
        host="webservices.amazon.es",
        region="eu-west-1",
        body="{}",
        now=datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC),
    )
    auth = headers["Authorization"]
    assert auth.startswith(
        "AWS4-HMAC-SHA256 Credential=AKID/20260102/eu-west-1/ProductAdvertisingAPI"
    )
    assert "SignedHeaders=content-encoding;content-type;host;x-amz-date;x-amz-target" in auth
    assert headers["x-amz-date"] == "20260102T030405Z"


@respx.mock
def test_blocked_detection():
    respx.get("https://www.ldlc.com/es-es/buscar/corsair/").mock(
        return_value=httpx.Response(200, text="<html>captcha bm-verify</html>")
    )
    scraper = LdlcScraper(Settings(scrape_delay_seconds=0))
    with pytest.raises(BlockedError):
        scraper.search("corsair")


@respx.mock
def test_http_403_is_blocked():
    respx.get(url__startswith="https://www.mediamarkt.es/").mock(return_value=httpx.Response(403))
    with pytest.raises(BlockedError):
        MediaMarktScraper(Settings(scrape_delay_seconds=0)).search("corsair")


def test_build_scraper_rules(db):
    from sqlalchemy import select

    from app.models import Store

    stores = {s.slug: s for s in db.scalars(select(Store))}
    settings = Settings()
    assert build_scraper(stores["pccomponentes"], settings) is None  # solo acceso directo
    assert build_scraper(stores["amazon"], settings) is None  # sin credenciales PA-API
    assert isinstance(build_scraper(stores["ldlc"], settings), LdlcScraper)
    assert isinstance(build_scraper(stores["alternate"], settings), AlternateScraper)
    assert isinstance(build_scraper(stores["corsair"], settings), CorsairScraper)
    assert isinstance(build_scraper(stores["amazon"], Settings(demo_mode=True)), DemoScraper)


def test_demo_is_stable_within_a_day():
    a = DemoScraper(Settings(), "ldlc").search("corsair")
    b = DemoScraper(Settings(), "ldlc").search("corsair")
    assert [(i.external_id, i.price) for i in a] == [(i.external_id, i.price) for i in b]
    assert all(i.discount_pct > 0 for i in a)


@pytest.mark.parametrize(
    ("title", "category"),
    [
        ("Corsair K70 RGB PRO Teclado mecánico", "Teclados"),
        ("Ratón gaming - Corsair Harpoon V2", "Ratones"),
        ("Corsair RM850e (2025)", "Fuentes"),
        ("Corsair Vengeance DDR5 32GB", "Memoria"),
        ("Corsair 5000D RGB Airflow caja", "Cajas"),
        ("Corsair iCUE H150i Refrigeración líquida", "Refrigeración"),
        ("Refrigerador CPU - CORSAIR CW-9060078-WW", "Refrigeración"),
        ("Refrigerador del chasis - CORSAIR iCUE LINK QX120 RGB", "Refrigeración"),
        ("Tarjeta gráfica - MSI GeForce RTX 5070", "Componentes"),
        ("Corsair 5000D RGB Airflow (Blanco)", "Cajas"),
        ("Lavadora carga frontal - Samsung WW90", "Electrodomésticos"),
        ('TV Mini LED 65" - Samsung QN90', "Televisores"),
        ("Tablet - Samsung Galaxy Tab S10", "Tablets"),
        ("Samsung Galaxy A57, Azul, 256 GB", "Smartphones"),
        ("Monitor gaming - Samsung Odyssey G5", "Monitores"),
        ("Portátil gaming - ASUS con teclado RGB", "Portátiles"),
        ("Volante - Logitech G G923", "Consolas y gaming"),
        ("Ratón gaming Logitech G Pro LIGHTSPEED", "Ratones"),
        ("Apple AirPods 4 (2024 4ª gen), Inalámbricos", "Auriculares"),
        ("Samsung Galaxy Buds3 Pro", "Auriculares"),
        ("Apple MacBook Air 13 M4", "Portátiles"),
        ("Apple Mac mini M4", "Ordenadores"),
        ("Apple Watch Series 11 GPS 46 mm", "Wearables"),
        ("Corsair Platform:6 Escritorio elevable", "Escritorios"),
        ("Lámpara de escritorio LED", "Iluminación"),
        ("Algo raro", "Otros"),
    ],
)
def test_categorize(title, category):
    assert categorize(title) == category


@pytest.mark.parametrize(
    ("title", "description", "category"),
    [
        # El título manda; la descripción solo cuenta si el título no dice nada
        ("Corsair K70 RGB Teclado", "Compatible con móvil", "Teclados"),
        (
            "Corsair VOID Max (Negro)",
            "Auriculares para juegos - compatible con móvil",
            "Auriculares",
        ),
        (
            "Corsair EX300U 1 TB",
            "SSD externo USB 3.1 Tipo C ultraportátil de 1 TB",
            "Almacenamiento",
        ),
        ("Corsair MM Cloth L", "Alfombrilla de ratón de tela", "Alfombrillas"),
        ("Corsair XL5 Coolant 1L", "Líquido refrigerante - 1000 mL", "Refrigeración"),
        ("Corsair Warthog", None, "Otros"),
    ],
)
def test_categorize_with_description(title, description, category):
    assert categorize(title, description) == category


def test_matches_brand():
    assert matches_brand("Teclado CORSAIR K70", "corsair")
    assert not matches_brand("Funda para teclado", "corsair")


@respx.mock
def test_mediamarkt_quotes_brand_and_paginates():
    route = respx.get(url__startswith="https://www.mediamarkt.es/es/search.html")
    route.side_effect = [
        httpx.Response(200, text=MM_HTML),
        httpx.Response(200, text=MM_HTML),  # página repetida: no aporta nada nuevo → se para
        httpx.Response(200, text="no debería pedirse"),
    ]
    items = MediaMarktScraper(Settings(scrape_delay_seconds=0, max_pages=3)).search("samsung")
    assert len(items) == 2
    assert route.call_count == 2
    first, second = (c.request.url.params for c in route.calls)
    assert first["query"] == '"samsung"' and first["brand"] == "SAMSUNG" and "page" not in first
    assert second["page"] == "2" and second["brand"] == "SAMSUNG"


@respx.mock
def test_mediamarkt_falls_back_without_brand_filter():
    route = respx.get(url__startswith="https://www.mediamarkt.es/es/search.html")
    route.side_effect = [
        httpx.Response(200, text="<html>0 resultados</html>" + "x" * 5000),  # marca no reconocida
        httpx.Response(200, text=MM_HTML + '"pageCount":1'),
    ]
    items = MediaMarktScraper(Settings(scrape_delay_seconds=0)).search("hyperx")
    assert len(items) == 2
    with_brand, without = (c.request.url.params for c in route.calls)
    assert with_brand["brand"] == "HYPERX" and "brand" not in without


@respx.mock
def test_mediamarkt_stops_at_page_count():
    route = respx.get(url__startswith="https://www.mediamarkt.es/es/search.html")
    route.side_effect = [httpx.Response(200, text=MM_HTML + '"pageCount":1')]
    MediaMarktScraper(Settings(scrape_delay_seconds=0, max_pages=60)).search("corsair")
    assert route.call_count == 1


@respx.mock
def test_ldlc_paginates_until_last_page():
    page2 = LDLC_HTML.replace("AR1", "AR3").replace("AR2", "AR4")
    respx.get("https://www.ldlc.com/es-es/buscar/corsair/").mock(
        return_value=httpx.Response(200, text=LDLC_HTML + '<a href="/es-es/buscar/corsair/page2/">')
    )
    p2 = respx.get("https://www.ldlc.com/es-es/buscar/corsair/page2/").mock(
        return_value=httpx.Response(200, text=page2)  # sin enlace a page3 → última página
    )
    items = LdlcScraper(Settings(scrape_delay_seconds=0)).search("corsair")
    assert [i.external_id for i in items] == ["AR1", "AR2", "AR3", "AR4"]
    assert p2.call_count == 1


def _alternate_box(pid: str, name: str, price: str, old: str = "", delivery: str = "En stock"):
    old_html = f'<div><span class="line-through">{old}</span></div>' if old else ""
    return f"""
<a class="card productBox" href="https://www.alternate.es/Corsair/Item/html/product/{pid}">
  <img class="productPicture" src="/p/200x200/1/9/{pid}.jpg">
  <div class="product-name font-weight-bold"><span>Corsair</span> {name}</div>
  <span class="product-name-sub">negro</span>
  <ul class="product-bullet-list"><li>Escritorio gaming</li></ul>
  <div class="campaign-timer-price-section">{old_html}<span class="price">{price}</span>
  <div class="delivery-info"><span>{delivery}</span></div></div>
</a>"""


ALTERNATE_HTML = (
    _alternate_box("100001", "Platform:6", "€ 299,00", old="€ 399,00")
    + _alternate_box("100002", "K70", "€ 81,90")
    + _alternate_box("100003", "Agotado", "€ 10,00", delivery="El artículo no puede ser comprado")
)


def test_alternate_parse():
    deal, normal = AlternateScraper.parse(ALTERNATE_HTML)
    assert deal.external_id == "100001"
    assert deal.title == "Corsair Platform:6 negro"
    assert deal.price == Decimal("299.00") and deal.original_price == Decimal("399.00")
    assert deal.image_url == "https://www.alternate.es/p/200x200/1/9/100001.jpg"
    assert normal.original_price is None  # el producto sin stock se descarta


@respx.mock
def test_alternate_paginates_until_a_page_adds_nothing_new():
    page2 = ALTERNATE_HTML.replace("100001", "100004").replace("100002", "100005")
    route = respx.get(url__startswith="https://www.alternate.es/listing.xhtml")
    route.side_effect = [
        httpx.Response(200, text=ALTERNATE_HTML),
        httpx.Response(200, text=page2),
        httpx.Response(200, text=page2),  # repetida → fin
    ]
    items = AlternateScraper(Settings(scrape_delay_seconds=0)).search("corsair")
    assert [i.external_id for i in items] == ["100001", "100002", "100004", "100005"]
    assert [c.request.url.params.get("page") for c in route.calls] == [None, "2", "3"]


def _corsair_page(*products: dict, links: str = "") -> str:
    data = {
        "props": {"pageProps": {"data": {"products": {"page_info": {}, "items": list(products)}}}}
    }
    return f'{links}<script id="__NEXT_DATA__" type="application/json">{json.dumps(data)}</script>'


def _corsair_product(sku, name, final, regular=None, stock="IN_STOCK", cats=()):
    price = {"final_price": {"value": final}, "regular_price": {"value": regular or final}}
    return {
        "sku": sku,
        "name": name,
        "stock_status": stock,
        "price_range": {"minimum_price": price},
        "image": {"url": "https://assets.corsair.com/image/upload/c_scale%2Cq_auto%2Cw_96/x.png"},
        "categories": [{"name": c} for c in cats],
        "description": {"html": "<p>Texto</p>"},
    }


CORSAIR_PAGE = _corsair_page(
    _corsair_product("CF-9500006-WW", "Escritorio Platform:6", 229.9, 299.9),
    _corsair_product("CF-9010074-WW", "Embrace", 499.99, cats=("Sillas gaming",)),
    _corsair_product("CH-1", "Corsair K70", 99, stock="OUT_OF_STOCK"),
    links='<a href="/es/es/p/gaming-furniture/cf-9500006-ww/platform-6-desk-cf-9500006-ww?position=1">',
)


def test_corsair_parse():
    desk, chair = CorsairScraper.parse(CORSAIR_PAGE)  # el producto sin stock se descarta
    assert desk.title == "Corsair Escritorio Platform:6"
    assert desk.price == Decimal("229.90") and desk.original_price == Decimal("299.90")
    assert desk.url == (
        "https://www.corsair.com/es/es/p/gaming-furniture/cf-9500006-ww/platform-6-desk-cf-9500006-ww"
    )
    assert (
        desk.image_url == "https://assets.corsair.com/image/upload/c_scale%2Cq_auto%2Cw_400/x.png"
    )
    assert categorize(desk.title, desk.description) == "Escritorios"
    # Sin enlace en el HTML cae a la búsqueda por SKU; "Embrace" se clasifica por su categoría
    assert chair.url.endswith("/es/es/search?q=CF-9010074-WW")
    assert categorize(chair.title, chair.description) == "Sillas"


def test_corsair_parse_without_next_data():
    assert CorsairScraper.parse("<html>nada</html>") == []


@respx.mock
def test_corsair_scrapes_categories_and_ignores_other_brands():
    route = respx.get(url__startswith="https://www.corsair.com/es/es/c/")
    route.mock(return_value=httpx.Response(200, text=CORSAIR_PAGE))
    scraper = CorsairScraper(Settings(scrape_delay_seconds=0))
    assert scraper.search("logitech") == []
    assert route.call_count == 0
    items = scraper.search("corsair")
    assert len(items) == 2  # misma ficha en todas las categorías: sin duplicados
    assert route.call_count == len(CATEGORIES)


@respx.mock
def test_corsair_survives_one_missing_category_but_not_a_block():
    route = respx.get(url__startswith="https://www.corsair.com/es/es/c/")
    route.side_effect = [httpx.Response(404)] + [httpx.Response(200, text=CORSAIR_PAGE)] * 20
    assert len(CorsairScraper(Settings(scrape_delay_seconds=0)).search("corsair")) == 2
    route.side_effect = [httpx.Response(403)]
    with pytest.raises(BlockedError):
        CorsairScraper(Settings(scrape_delay_seconds=0)).search("corsair")


def test_seed_enables_scrapers_on_existing_stores(db):
    from sqlalchemy import select

    from app.models import Store
    from app.services.seed import seed_defaults

    for slug in ("alternate", "corsair"):
        store = db.scalar(select(Store).where(Store.slug == slug))
        store.scraper, store.search_url = None, None
    db.commit()
    seed_defaults(db)
    stores = {s.slug: s for s in db.scalars(select(Store))}
    assert stores["alternate"].scraper == "alternate"
    assert stores["corsair"].scraper == "corsair" and "{query}" in stores["corsair"].search_url


def _car_card(car_id: str, model: str = "SEAT Ateca 1.0 TSI", price="24840", **vehicle) -> str:
    cfg = {
        "VehicleManufacturer": "SEAT",
        "Model": {"Name": model},
        "Production": {"Year": "2026"},
        "Vehicle": {"Milage": "51 km", "Sold": "false", "Reserved": "false", **vehicle},
        "BodyType": {"Name": "Todo terreno"},
        "Engine": {"FuelType": {"Main": "Gasolina"}},
        "Budget": {"Price": {"price": price}},
    }
    return (
        f"<article data-car-id='{car_id}' data-configuration='{json.dumps(cfg)}'>"
        f'<a class="enlaceficha" href="/esp/oferta/seat-ateca/{car_id}"></a>'
        '<picture><source data-srcset="https://img.test/a.webp?x=1&amp;size=400 1x, other 2x">'
        "</picture></article>"
    )


def test_dasweltauto_parse():
    html = _car_card("1") + _car_card("2", Reserved="true") + _car_card("3", "SEAT X", "0")
    items = DasWeltAutoScraper.parse(html)
    assert [i.external_id for i in items] == ["1"]  # reservado y precio 0 fuera
    car = items[0]
    assert car.title == "SEAT Ateca 1.0 TSI · 2026 · 51 km · Gasolina"
    assert car.price == Decimal("24840")
    assert car.url == "https://www.dasweltauto.es/esp/oferta/seat-ateca/1"
    assert car.image_url == "https://img.test/a.webp?x=1&size=400"
    assert car.category == "SUV" and car.curated


@respx.mock
def test_dasweltauto_paginates_and_ignores_other_brands():
    full = "".join(_car_card(str(i)) for i in range(23))
    route = respx.get(url__startswith="https://www.dasweltauto.es/esp/coches-seleccion/seat")
    route.side_effect = [
        httpx.Response(200, text=full),
        httpx.Response(200, text=_car_card("99")),  # página corta: última
    ]
    scraper = DasWeltAutoScraper(Settings(scrape_delay_seconds=0))
    assert scraper.search("corsair") == []
    assert len(scraper.search("seat")) == 24
    assert route.call_count == 2
    assert "descuento_desde%5D=1" in str(route.calls[0].request.url)


def _op_vehicle(
    code: str, price: int, brand="Renault", model="Renault Clio 1.0 TCe", **offer
) -> dict:
    return {
        "@type": "Vehicle",
        "name": "Renault Clio",
        "brand": {"@type": "Brand", "name": brand},
        "model": model,
        "fuelType": "Gasolina",
        "productionDate": "2019-05-01T00:00:00.000Z",
        "mileageFromOdometer": {"value": 64500, "unitText": "KM"},
        "image": "https://img.test/clio.jpg",
        "offers": {
            "price": price,
            "availability": "https://schema.org/InStock",
            "url": f"https://www.ocasionplus.com/coches-segunda-mano/renault-clio-con-64500km-2019-{code}",
            **offer,
        },
    }


def _op_page(*vehicles: dict) -> str:
    ld = {"@type": "ItemList", "itemListElement": list(vehicles)}
    return f'<script type="application/ld+json">{json.dumps(ld)}</script>'


def test_ocasionplus_parse_keeps_only_in_budget_in_stock():
    page = _op_page(
        _op_vehicle("aaa", 8900),
        _op_vehicle("bbb", 10000),
        _op_vehicle("ccc", 10001),
        _op_vehicle("ddd", 5000, availability="https://schema.org/OutOfStock"),
    )
    items, listed = OcasionPlusScraper.parse(page, 10000)
    assert listed == {"aaa", "bbb", "ccc", "ddd"}
    assert [i.external_id for i in items] == ["aaa", "bbb"]
    car = items[0]
    assert car.title == "Renault Clio 1.0 TCe · 2019 · 64.500 km · Gasolina"
    assert car.category == "Hasta 10.000 €" and car.curated and car.price == Decimal("8900")


@respx.mock
def test_ocasionplus_paginates_until_a_page_adds_nothing_new():
    route = respx.get(url__startswith="https://www.ocasionplus.com/coches-segunda-mano/renault")
    route.side_effect = [
        httpx.Response(200, text=_op_page(_op_vehicle("aaa", 8000))),
        httpx.Response(200, text=_op_page(_op_vehicle("bbb", 9000))),
        httpx.Response(200, text=_op_page(_op_vehicle("bbb", 9000))),  # repetida: fin
    ]
    scraper = OcasionPlusScraper(Settings(scrape_delay_seconds=0))
    assert [i.external_id for i in scraper.search("Renault")] == ["aaa", "bbb"]
    assert route.call_count == 3
    assert "?page=2" in str(route.calls[1].request.url)


@respx.mock
def test_ocasionplus_unknown_brand_is_empty_not_an_error():
    respx.get("https://www.ocasionplus.com/coches-segunda-mano/lada").mock(
        return_value=httpx.Response(404)
    )
    assert OcasionPlusScraper(Settings(scrape_delay_seconds=0)).search("lada") == []


def test_ocasionplus_max_km_filters_high_mileage_and_zero_means_unlimited():
    page = _op_page(_op_vehicle("aaa", 8000), _op_vehicle("bbb", 7000))
    high = json.loads(page.split(">", 1)[1].rsplit("</script>", 1)[0])
    high["itemListElement"][1]["mileageFromOdometer"]["value"] = 210000
    page = f'<script type="application/ld+json">{json.dumps(high)}</script>'
    assert [i.external_id for i in OcasionPlusScraper.parse(page, 10000, 150000)[0]] == ["aaa"]
    assert len(OcasionPlusScraper.parse(page, 10000, 0)[0]) == 2

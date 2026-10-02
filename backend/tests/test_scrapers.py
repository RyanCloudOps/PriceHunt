from datetime import UTC, datetime
from decimal import Decimal

import httpx
import pytest
import respx

from app.config import Settings
from app.scrapers import BlockedError, build_scraper, parse_price
from app.scrapers.amazon import AmazonPaapiScraper, sigv4_headers
from app.scrapers.demo import DemoScraper
from app.scrapers.ldlc import LdlcScraper
from app.scrapers.mediamarkt import MediaMarktScraper
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

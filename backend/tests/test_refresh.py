from datetime import timedelta
from decimal import Decimal

from sqlalchemy import select

from app.config import Settings
from app.db import utcnow
from app.models import Deal, PriceHistory, ScrapeRun, Store, WatchTerm
from app.scrapers import ScrapedItem, Scraper, ScraperError
from app.services.refresh import needs_refresh, run_refresh

SETTINGS = Settings(min_discount_pct=5, scrape_delay_seconds=0)


class FakeScraper(Scraper):
    key = "fake"

    def __init__(self, catalog: dict[str, list[ScrapedItem] | Exception]):
        self.catalog = catalog

    def search(self, query: str) -> list[ScrapedItem]:
        result = self.catalog.get(query, [])
        if isinstance(result, Exception):
            raise result
        return result

    def close(self) -> None:
        pass


def item(eid: str, title: str, price: str, original: str | None = None) -> ScrapedItem:
    return ScrapedItem(
        external_id=eid,
        title=title,
        url=f"https://shop.test/{eid}",
        price=Decimal(price),
        original_price=Decimal(original) if original else None,
    )


def only_ldlc(catalog):
    def factory(store: Store, _settings):
        return FakeScraper(catalog) if store.slug == "ldlc" else None

    return factory


def setup_terms(db, *terms):
    db.query(WatchTerm).delete()
    db.add_all(WatchTerm(query=t) for t in terms)
    db.commit()


def active_ids(db) -> set[str]:
    return set(db.scalars(select(Deal.external_id).where(Deal.is_active.is_(True))))


def test_refresh_creates_and_filters(db):
    setup_terms(db, "corsair")
    catalog = {
        "corsair": [
            item("a", "Corsair K70 Teclado", "99.90", "149.90"),
            item("b", "Corsair M75 Ratón", "80", "82"),  # 2,4 %: por debajo del mínimo
            item("c", "Funda genérica", "10", "20"),  # no contiene la marca
            item("d", "Corsair HS80 Auriculares", "120"),  # sin descuento
        ]
    }
    run_id = run_refresh("manual", scraper_factory=only_ldlc(catalog), settings=SETTINGS)

    run = db.get(ScrapeRun, run_id)
    assert run.status == "success" and run.deals_found == 1
    deal = db.scalar(select(Deal))
    assert deal.external_id == "a"
    assert deal.category == "Teclados" and deal.brand == "corsair"
    assert deal.discount_pct == 33.4
    assert db.scalar(select(PriceHistory).where(PriceHistory.deal_id == deal.id)).price == Decimal(
        "99.90"
    )


def test_next_day_refresh_expires_missing_deals_and_tracks_price(db):
    setup_terms(db, "corsair")
    run_refresh(
        "startup",
        scraper_factory=only_ldlc(
            {"corsair": [item("a", "Corsair A", "90", "100"), item("b", "Corsair B", "50", "80")]}
        ),
        settings=SETTINGS,
    )
    assert active_ids(db) == {"a", "b"}

    # Al día siguiente "b" ya no está en oferta y "a" ha bajado de precio
    run_refresh(
        "schedule",
        scraper_factory=only_ldlc({"corsair": [item("a", "Corsair A", "85", "100")]}),
        settings=SETTINGS,
    )
    db.expire_all()
    assert active_ids(db) == {"a"}
    a = db.scalar(select(Deal).where(Deal.external_id == "a"))
    assert [h.price for h in a.history] == [Decimal("90.00"), Decimal("85.00")]


def test_partial_failure_does_not_expire_deals(db):
    setup_terms(db, "corsair", "razer")
    first = {
        "corsair": [item("a", "Corsair A", "90", "100")],
        "razer": [item("r", "Razer R", "50", "80")],
    }
    run_refresh("manual", scraper_factory=only_ldlc(first), settings=SETTINGS)

    broken = {"corsair": [item("a", "Corsair A", "90", "100")], "razer": ScraperError("timeout")}
    run_id = run_refresh("manual", scraper_factory=only_ldlc(broken), settings=SETTINGS)
    db.expire_all()
    assert active_ids(db) == {"a", "r"}
    assert "timeout" in db.get(ScrapeRun, run_id).log


def test_needs_refresh(db):
    assert needs_refresh(db, SETTINGS)
    db.add(ScrapeRun(trigger="manual", status="success", finished_at=utcnow()))
    db.commit()
    assert not needs_refresh(db, SETTINGS)
    db.add(
        ScrapeRun(trigger="manual", status="failed", finished_at=utcnow() + timedelta(minutes=1))
    )
    db.commit()
    assert not needs_refresh(db, SETTINGS)  # los fallidos no cuentan
    run = db.scalar(select(ScrapeRun).where(ScrapeRun.status == "success"))
    run.finished_at = utcnow() - timedelta(hours=25)
    db.commit()
    assert needs_refresh(db, SETTINGS)


def test_demo_mode_end_to_end(db):
    run_id = run_refresh("manual", settings=Settings(demo_mode=True, scrape_delay_seconds=0))
    run = db.get(ScrapeRun, run_id)
    assert run.status == "success"
    assert run.stores_ok == 5  # amazon, ldlc, mediamarkt, alternate, corsair
    assert run.deals_found > 0


def test_store_without_scraper_hides_old_deals(db):
    # Ofertas cazadas en modo demo para Amazon...
    run_refresh("manual", settings=Settings(demo_mode=True, scrape_delay_seconds=0))
    amazon = db.scalar(select(Store).where(Store.slug == "amazon"))
    assert db.scalar(select(Deal).where(Deal.store_id == amazon.id, Deal.is_active.is_(True)))

    # ...y después sin credenciales PA-API: no se pueden revalidar, así que se ocultan
    run_refresh("manual", scraper_factory=lambda store, s: None, settings=SETTINGS)
    db.expire_all()
    assert not db.scalar(select(Deal).where(Deal.store_id == amazon.id, Deal.is_active.is_(True)))

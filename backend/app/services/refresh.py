"""Orquestador del refresco de ofertas.

Cada ejecución recorre las tiendas con scraper x términos vigilados, hace upsert
de las ofertas, guarda historial de precios y desactiva las ofertas que ya no
aparecen (o que han dejado de tener descuento). Así lo que se cazó ayer se
revalida automáticamente hoy.
"""

import logging
import threading
import time
from collections.abc import Callable
from datetime import timedelta

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, sessionmaker

from app import metrics
from app.config import Settings, get_settings
from app.db import SessionLocal, as_utc, utcnow
from app.models import Deal, PriceHistory, ScrapeRun, Store, WatchTerm
from app.scrapers import BlockedError, ScrapedItem, Scraper, build_scraper
from app.services.classify import categorize, matches_brand

log = logging.getLogger(__name__)

_lock = threading.Lock()

ScraperFactory = Callable[[Store, Settings], Scraper | None]


def is_running() -> bool:
    return _lock.locked()


def last_completed_run(session: Session) -> ScrapeRun | None:
    return session.scalar(
        select(ScrapeRun)
        .where(ScrapeRun.status.in_(("success", "partial")))
        .order_by(ScrapeRun.finished_at.desc())
        .limit(1)
    )


def needs_refresh(session: Session, settings: Settings) -> bool:
    last = last_completed_run(session)
    if last is None or last.finished_at is None:
        return True
    return utcnow() - as_utc(last.finished_at) >= timedelta(hours=settings.refresh_interval_hours)


def fail_orphan_runs(session: Session) -> None:
    """Ejecuciones que quedaron 'running' por un reinicio del contenedor."""
    session.execute(
        update(ScrapeRun)
        .where(ScrapeRun.status == "running")
        .values(status="failed", finished_at=utcnow(), log=ScrapeRun.log + "\nInterrumpida")
    )
    session.commit()


def _discount_pct(price, original) -> float:
    if not original or original <= price:
        return 0.0
    return round(float((1 - price / original) * 100), 1)


def upsert_deal(session: Session, store: Store, brand: str, item: ScrapedItem) -> Deal:
    now = utcnow()
    deal = session.scalar(
        select(Deal).where(Deal.store_id == store.id, Deal.external_id == item.external_id)
    )
    if deal is None:
        deal = Deal(store_id=store.id, external_id=item.external_id, first_seen_at=now)
        session.add(deal)
        price_changed = True
    else:
        price_changed = deal.price != item.price

    original = item.original_price
    if original is None and item.curated and deal.id is not None:
        # La tienda marca el coche como rebajado pero no da el precio anterior:
        # el más alto que hemos visto es la referencia.
        top = session.scalar(
            select(func.max(PriceHistory.price)).where(PriceHistory.deal_id == deal.id)
        )
        if top is not None and top > item.price:
            original = top
    discount_pct = _discount_pct(item.price, original)

    deal.title = item.title[:500]
    deal.url = item.url
    deal.image_url = item.image_url
    deal.brand = brand
    deal.category = item.category or categorize(item.title, item.description)
    deal.price = item.price
    deal.original_price = original
    deal.discount_pct = discount_pct
    deal.currency = item.currency
    deal.is_active = True
    deal.last_seen_at = now
    session.flush()
    if price_changed:
        session.add(PriceHistory(deal_id=deal.id, price=item.price, captured_at=now))
    return deal


def _scrape_store(
    session: Session, store: Store, scraper: Scraper, terms: list[str], settings: Settings
) -> tuple[int, list[str]]:
    seen: set[int] = set()
    errors: list[str] = []
    for term in terms:
        try:
            items = scraper.search(term)
        except BlockedError as exc:
            metrics.SCRAPE_ERRORS.labels(store.slug, "blocked").inc()
            errors.append(str(exc))
            break  # si nos bloquean no insistimos con más términos
        except Exception as exc:
            metrics.SCRAPE_ERRORS.labels(store.slug, "error").inc()
            errors.append(f"{store.slug}/{term}: {exc}")
            continue
        for item in items:
            if not matches_brand(item.title, term):
                continue
            if not item.curated and item.discount_pct < settings.min_discount_pct:
                continue
            seen.add(upsert_deal(session, store, term, item).id)

    # Solo caducamos si TODAS las búsquedas fueron bien; si no, un fallo
    # puntual borraría ofertas que siguen vigentes.
    if not errors:
        session.execute(
            update(Deal)
            .where(
                Deal.store_id == store.id, Deal.is_active.is_(True), Deal.id.not_in(seen or {-1})
            )
            .values(is_active=False)
        )
    session.commit()
    return len(seen), errors


def expire_stale_deals(session: Session, settings: Settings) -> int:
    """Red de seguridad: lo que no se ha revalidado en 2 intervalos deja de mostrarse."""
    cutoff = utcnow() - timedelta(hours=settings.refresh_interval_hours * 2)
    result = session.execute(
        update(Deal)
        .where(Deal.is_active.is_(True), Deal.last_seen_at < cutoff)
        .values(is_active=False)
    )
    session.commit()
    return result.rowcount or 0


def _update_gauges(session: Session) -> None:
    rows = session.execute(
        select(Store.slug, func.count(Deal.id))
        .join(Deal, (Deal.store_id == Store.id) & Deal.is_active.is_(True), isouter=True)
        .group_by(Store.slug)
    )
    for slug, count in rows:
        metrics.ACTIVE_DEALS.labels(slug).set(count)


def run_refresh(
    trigger: str,
    session_factory: sessionmaker = SessionLocal,
    scraper_factory: ScraperFactory = build_scraper,
    settings: Settings | None = None,
) -> int | None:
    """Ejecuta un refresco completo. Devuelve el id del ScrapeRun, o None si ya había uno en curso."""
    settings = settings or get_settings()
    if not _lock.acquire(blocking=False):
        log.info("Refresco ya en curso; se ignora trigger=%s", trigger)
        return None
    started = time.monotonic()
    try:
        with session_factory() as session:
            run = ScrapeRun(trigger=trigger, status="running")
            session.add(run)
            session.commit()
            run_id = run.id
            log.info("Refresco #%s iniciado (trigger=%s)", run_id, trigger)

            stores = session.scalars(
                select(Store).where(Store.enabled.is_(True), Store.scraper.is_not(None))
            ).all()
            terms = session.scalars(select(WatchTerm).where(WatchTerm.enabled.is_(True))).all()

            lines: list[str] = []
            ok = failed = found = 0
            for store in stores:
                scraper = scraper_factory(store, settings)
                if scraper is None:
                    # Sin forma de revalidar (p. ej. faltan credenciales): no mostramos ofertas viejas
                    session.execute(
                        update(Deal)
                        .where(Deal.store_id == store.id, Deal.is_active.is_(True))
                        .values(is_active=False)
                    )
                    session.commit()
                    lines.append(f"{store.slug}: sin scraper disponible (acceso directo)")
                    continue
                try:
                    store_terms = [t.query for t in terms if t.vertical == store.vertical]
                    count, errors = _scrape_store(session, store, scraper, store_terms, settings)
                except Exception as exc:
                    session.rollback()
                    log.exception("Fallo inesperado en %s", store.slug)
                    count, errors = 0, [f"{store.slug}: {exc!r}"]
                finally:
                    scraper.close()
                found += count
                lines.append(f"{store.slug}: {count} ofertas")
                lines.extend(f"  ! {e}" for e in errors)
                if errors and count == 0:
                    failed += 1
                else:
                    ok += 1

            expired = expire_stale_deals(session, settings)
            if expired:
                lines.append(f"{expired} ofertas caducadas por antigüedad")

            run = session.get(ScrapeRun, run_id)
            run.status = "failed" if failed and not ok else ("partial" if failed else "success")
            run.stores_ok, run.stores_failed, run.deals_found = ok, failed, found
            run.finished_at = utcnow()
            run.log = "\n".join(lines)
            session.commit()
            _update_gauges(session)

            metrics.SCRAPE_RUNS.labels(trigger, run.status).inc()
            if run.status != "failed":
                metrics.LAST_SUCCESS.set(time.time())
            log.info("Refresco #%s %s: %s ofertas", run_id, run.status, found)
            return run_id
    finally:
        metrics.SCRAPE_DURATION.observe(time.monotonic() - started)
        _lock.release()


def refresh_if_stale(trigger: str = "stale") -> int | None:
    settings = get_settings()
    with SessionLocal() as session:
        if not needs_refresh(session, settings):
            return None
    return run_refresh(trigger)


def start_in_background(trigger: str, fn: Callable[..., object] = run_refresh) -> bool:
    if is_running():
        return False
    threading.Thread(target=fn, args=(trigger,), daemon=True, name=f"refresh-{trigger}").start()
    return True

import re
from datetime import timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app import scheduler
from app.config import get_settings
from app.db import as_utc, get_session, utcnow
from app.models import Deal, PriceHistory, ScrapeRun, Store, WatchTerm
from app.schemas import (
    CategoryCount,
    DealOut,
    DealPage,
    PricePoint,
    RunOut,
    Stats,
    StoreIn,
    StoreOut,
    WatchTermIn,
    WatchTermOut,
)
from app.scrapers import REGISTRY
from app.services import refresh

router = APIRouter(prefix="/api")

VerticalParam = Literal["tech", "cars"]
SortKey = Literal["discount", "price_asc", "price_desc", "newest"]
_SORTS = {
    "discount": Deal.discount_pct.desc(),
    "price_asc": Deal.price.asc(),
    "price_desc": Deal.price.desc(),
    "newest": Deal.first_seen_at.desc(),
}


def _is_tracked(store: Store) -> bool:
    settings = get_settings()
    if not store.scraper:
        return False
    if settings.demo_mode:
        return True
    cls = REGISTRY.get(store.scraper)
    return bool(cls and cls.available(settings))


def _deal_out(deal: Deal) -> DealOut:
    out = DealOut.model_validate(
        {
            **{c: getattr(deal, c) for c in DealOut.model_fields if hasattr(deal, c)},
            "store_slug": deal.store.slug,
            "store_name": deal.store.name,
            "store_color": deal.store.accent_color,
        }
    )
    out.is_new = utcnow() - as_utc(deal.first_seen_at) < timedelta(hours=24)
    return out


@router.get("/health")
def health(session: Session = Depends(get_session)) -> dict:
    session.execute(text("SELECT 1"))
    return {"status": "ok"}


@router.get("/deals", response_model=DealPage)
def list_deals(
    session: Session = Depends(get_session),
    vertical: VerticalParam = "tech",
    store: str | None = None,
    category: str | None = None,
    brand: str | None = None,
    q: str | None = Query(default=None, max_length=100),
    min_discount: float = Query(default=0, ge=0, le=100),
    sort: SortKey = "discount",
    include_inactive: bool = False,
    limit: int = Query(default=60, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> DealPage:
    stmt = select(Deal).join(Store).where(Store.vertical == vertical)
    if not include_inactive:
        stmt = stmt.where(Deal.is_active.is_(True))
    if store:
        stmt = stmt.where(Store.slug == store)
    if category:
        stmt = stmt.where(Deal.category == category)
    if brand:
        stmt = stmt.where(Deal.brand == brand.lower())
    if q:
        stmt = stmt.where(Deal.title.ilike(f"%{q}%"))
    if min_discount:
        stmt = stmt.where(Deal.discount_pct >= min_discount)

    total = session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = session.scalars(stmt.order_by(_SORTS[sort], Deal.id).limit(limit).offset(offset)).all()
    return DealPage(total=total, items=[_deal_out(d) for d in rows])


@router.get("/deals/{deal_id}/history", response_model=list[PricePoint])
def deal_history(deal_id: int, session: Session = Depends(get_session)) -> list[PriceHistory]:
    if not session.get(Deal, deal_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Oferta no encontrada")
    return session.scalars(
        select(PriceHistory)
        .where(PriceHistory.deal_id == deal_id)
        .order_by(PriceHistory.captured_at)
    ).all()


@router.get("/categories", response_model=list[CategoryCount])
def categories(
    vertical: VerticalParam = "tech", session: Session = Depends(get_session)
) -> list[CategoryCount]:
    rows = session.execute(
        select(Deal.category, func.count())
        .join(Store)
        .where(Deal.is_active.is_(True), Store.vertical == vertical)
        .group_by(Deal.category)
        .order_by(func.count().desc())
    )
    return [CategoryCount(name=n, count=c) for n, c in rows]


@router.get("/stores", response_model=list[StoreOut])
def list_stores(
    vertical: VerticalParam = "tech", session: Session = Depends(get_session)
) -> list[StoreOut]:
    counts = dict(
        session.execute(
            select(Deal.store_id, func.count())
            .where(Deal.is_active.is_(True))
            .group_by(Deal.store_id)
        ).all()
    )
    stores = session.scalars(
        select(Store).where(Store.vertical == vertical).order_by(Store.id)
    ).all()
    out = []
    for s in stores:
        item = StoreOut.model_validate(s)
        item.active_deals = counts.get(s.id, 0)
        item.tracked = _is_tracked(s)
        out.append(item)
    return out


@router.post("/stores", response_model=StoreOut, status_code=status.HTTP_201_CREATED)
def create_store(payload: StoreIn, session: Session = Depends(get_session)) -> StoreOut:
    url = str(payload.shortcut_url)
    slug = re.sub(r"[^a-z0-9]+", "-", payload.name.lower()).strip("-")[:50]
    if session.scalar(select(Store).where(Store.slug == slug)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya existe una tienda con ese nombre")
    store = Store(
        slug=slug,
        name=payload.name,
        base_url=url,
        shortcut_url=url,
        search_url=payload.search_url,
        accent_color=payload.accent_color,
        scraper=None,
        vertical=payload.vertical,
    )
    session.add(store)
    session.commit()
    return StoreOut.model_validate(store)


@router.delete("/stores/{store_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_store(store_id: int, session: Session = Depends(get_session)) -> Response:
    store = session.get(Store, store_id)
    if not store:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tienda no encontrada")
    if store.scraper:
        raise HTTPException(status.HTTP_409_CONFLICT, "Las tiendas rastreadas no se pueden borrar")
    session.delete(store)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/watchlist", response_model=list[WatchTermOut])
def list_terms(
    vertical: VerticalParam = "tech", session: Session = Depends(get_session)
) -> list[WatchTerm]:
    return session.scalars(
        select(WatchTerm).where(WatchTerm.vertical == vertical).order_by(WatchTerm.id)
    ).all()


@router.post("/watchlist", response_model=WatchTermOut, status_code=status.HTTP_201_CREATED)
def add_term(payload: WatchTermIn, session: Session = Depends(get_session)) -> WatchTerm:
    query = payload.query.strip().lower()
    if session.scalar(select(WatchTerm).where(WatchTerm.query == query)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya se está vigilando")
    term = WatchTerm(query=query, vertical=payload.vertical)
    session.add(term)
    session.commit()
    return term


@router.delete("/watchlist/{term_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_term(term_id: int, session: Session = Depends(get_session)) -> Response:
    term = session.get(WatchTerm, term_id)
    if not term:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Término no encontrado")
    session.delete(term)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/runs", response_model=list[RunOut])
def list_runs(
    session: Session = Depends(get_session), limit: int = Query(default=10, ge=1, le=100)
) -> list[ScrapeRun]:
    return session.scalars(select(ScrapeRun).order_by(ScrapeRun.id.desc()).limit(limit)).all()


@router.post("/refresh", status_code=status.HTTP_202_ACCEPTED)
def trigger_refresh() -> dict:
    if not refresh.start_in_background("manual"):
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya hay un refresco en curso")
    return {"status": "started"}


@router.get("/stats", response_model=Stats)
def stats(vertical: VerticalParam = "tech", session: Session = Depends(get_session)) -> Stats:
    active = Deal.is_active.is_(True)
    in_vertical = Deal.store_id.in_(select(Store.id).where(Store.vertical == vertical))
    count, best, avg, savings = session.execute(
        select(
            func.count(Deal.id),
            func.coalesce(func.max(Deal.discount_pct), 0),
            func.coalesce(func.avg(Deal.discount_pct), 0),
            func.coalesce(func.sum(Deal.original_price - Deal.price), 0),
        ).where(active, in_vertical)
    ).one()
    new_today = session.scalar(
        select(func.count(Deal.id)).where(
            active, in_vertical, Deal.first_seen_at >= utcnow() - timedelta(days=1)
        )
    )
    stores = session.scalars(
        select(Store).where(Store.enabled.is_(True), Store.vertical == vertical)
    ).all()
    last = session.scalar(select(ScrapeRun).order_by(ScrapeRun.id.desc()).limit(1))
    return Stats(
        active_deals=count,
        new_today=new_today or 0,
        stores_total=len(stores),
        stores_tracked=sum(_is_tracked(s) for s in stores),
        best_discount=round(float(best), 1),
        avg_discount=round(float(avg), 1),
        total_savings=float(savings),
        last_run=RunOut.model_validate(last) if last else None,
        next_run=scheduler.next_run(),
        refreshing=refresh.is_running(),
        demo_mode=get_settings().demo_mode,
    )

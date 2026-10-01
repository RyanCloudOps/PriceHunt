from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, PlainSerializer, field_validator

Money = Annotated[float, PlainSerializer(lambda v: round(float(v), 2), return_type=float)]


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class StoreOut(ORM):
    id: int
    slug: str
    name: str
    base_url: str
    shortcut_url: str
    search_url: str | None
    accent_color: str
    scraper: str | None
    enabled: bool
    active_deals: int = 0
    tracked: bool = False  # True si tiene scraper operativo


class StoreIn(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    shortcut_url: HttpUrl
    search_url: str | None = Field(default=None, max_length=500)
    accent_color: str = Field(default="#f5a524", pattern=r"^#[0-9a-fA-F]{6}$")

    @field_validator("shortcut_url")
    @classmethod
    def https_only(cls, v: HttpUrl) -> HttpUrl:
        if v.scheme != "https":
            raise ValueError("Solo se admiten webs https")
        return v

    @field_validator("search_url")
    @classmethod
    def search_template(cls, v: str | None) -> str | None:
        if v and (not v.startswith("https://") or "{query}" not in v):
            raise ValueError("Debe ser https y contener {query}")
        return v


class DealOut(ORM):
    id: int
    title: str
    url: str
    image_url: str | None
    brand: str
    category: str
    price: Money
    original_price: Money | None
    discount_pct: float
    currency: str
    is_active: bool
    is_new: bool = False
    first_seen_at: datetime
    last_seen_at: datetime
    store_slug: str
    store_name: str
    store_color: str


class DealPage(BaseModel):
    total: int
    items: list[DealOut]


class PricePoint(ORM):
    price: Money
    captured_at: datetime


class WatchTermOut(ORM):
    id: int
    query: str
    enabled: bool


class WatchTermIn(BaseModel):
    query: str = Field(min_length=2, max_length=100, pattern=r"^[\w\s\-]+$")


class CategoryCount(BaseModel):
    name: str
    count: int


class RunOut(ORM):
    id: int
    trigger: str
    status: str
    started_at: datetime
    finished_at: datetime | None
    stores_ok: int
    stores_failed: int
    deals_found: int
    log: str


class Stats(BaseModel):
    active_deals: int
    new_today: int
    stores_total: int
    stores_tracked: int
    best_discount: float
    avg_discount: float
    total_savings: Money
    last_run: RunOut | None
    next_run: datetime | None
    refreshing: bool
    demo_mode: bool

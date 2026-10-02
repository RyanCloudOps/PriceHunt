from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://pricehunt:pricehunt@localhost:5432/pricehunt"
    log_level: str = "INFO"
    timezone: str = "Europe/Madrid"
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:8080"]

    # Refresco de ofertas
    scheduler_enabled: bool = True
    refresh_on_startup: bool = True
    refresh_interval_hours: int = 24  # antigüedad máxima antes de forzar un refresco
    refresh_cron_hour: int = 7  # refresco diario fijo (hora local)
    stale_check_minutes: int = 30  # cada cuánto se comprueba si los datos están caducados

    # Scraping
    demo_mode: bool = False  # datos sintéticos, sin tocar webs reales (CI / offline)
    min_discount_pct: float = 5.0
    max_pages: int = 60  # tope de páginas por marca y tienda (se para antes si no hay más)
    scrape_delay_seconds: float = 2.0
    http_timeout_seconds: float = 20.0
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/128.0 Safari/537.36"
    )

    # Amazon Product Advertising API 5 (opcional)
    amazon_access_key: str | None = None
    amazon_secret_key: str | None = None
    amazon_partner_tag: str | None = None
    amazon_host: str = "webservices.amazon.es"
    amazon_region: str = "eu-west-1"
    amazon_marketplace: str = "www.amazon.es"


@lru_cache
def get_settings() -> Settings:
    return Settings()

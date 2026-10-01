from prometheus_client import Counter, Gauge, Histogram

SCRAPE_RUNS = Counter(
    "pricehunt_scrape_runs_total", "Ejecuciones de refresco", ["trigger", "status"]
)
SCRAPE_ERRORS = Counter("pricehunt_scrape_errors_total", "Errores por tienda", ["store", "kind"])
SCRAPE_DURATION = Histogram(
    "pricehunt_scrape_duration_seconds",
    "Duración de cada refresco completo",
    buckets=(1, 5, 15, 30, 60, 120, 300, 600),
)
ACTIVE_DEALS = Gauge("pricehunt_active_deals", "Ofertas activas por tienda", ["store"])
LAST_SUCCESS = Gauge("pricehunt_last_success_timestamp", "Epoch del último refresco correcto")

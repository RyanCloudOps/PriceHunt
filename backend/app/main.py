import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import make_asgi_app

from app import scheduler
from app.api import router
from app.config import get_settings
from app.db import SessionLocal
from app.services import refresh
from app.services.seed import seed_defaults

settings = get_settings()
logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
log = logging.getLogger("pricehunt")


@asynccontextmanager
async def lifespan(_: FastAPI):
    with SessionLocal() as session:
        seed_defaults(session)
        refresh.fail_orphan_runs(session)
    if settings.scheduler_enabled:
        scheduler.start()
    if settings.refresh_on_startup:
        # Al lanzar la web: si los datos tienen más de `refresh_interval_hours`, se refrescan
        refresh.start_in_background("startup", lambda trigger: refresh.refresh_if_stale(trigger))
    log.info("PriceHunt API lista (demo_mode=%s)", settings.demo_mode)
    yield
    scheduler.shutdown()


app = FastAPI(title="PriceHunt API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)
app.mount("/metrics", make_asgi_app())

import os
import tempfile

# Configuración ANTES de importar la app. En CI DATABASE_URL apunta a Postgres.
os.environ.setdefault(
    "DATABASE_URL", f"sqlite:///{os.path.join(tempfile.gettempdir(), 'pricehunt-test.db')}"
)
os.environ["SCHEDULER_ENABLED"] = "false"
os.environ["REFRESH_ON_STARTUP"] = "false"
os.environ["SCRAPE_DELAY_SECONDS"] = "0"

import pytest
from fastapi.testclient import TestClient

from app.db import Base, SessionLocal, engine
from app.services.seed import seed_defaults


@pytest.fixture(autouse=True)
def db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with SessionLocal() as session:
        seed_defaults(session)
        yield session
    Base.metadata.drop_all(engine)


@pytest.fixture
def client():
    from app.main import app

    with TestClient(app) as c:
        yield c

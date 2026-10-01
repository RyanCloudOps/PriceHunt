"""accesos directos genéricos (no ligados a Corsair)

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-02
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# slug: (url antigua, url nueva). Solo se tocan las que no ha editado el usuario.
CHANGES = {
    "amazon": ("https://www.amazon.es/s?k=corsair", "https://www.amazon.es/gp/goldbox"),
    "ldlc": ("https://www.ldlc.com/es-es/buscar/corsair/", "https://www.ldlc.com/es-es/"),
    "mediamarkt": ("https://www.mediamarkt.es/es/brand/corsair", "https://www.mediamarkt.es/es/"),
    "pccomponentes": (
        "https://www.pccomponentes.com/buscar/?query=corsair",
        "https://www.pccomponentes.com/",
    ),
    "alternate": ("https://www.alternate.es/listing.xhtml?q=corsair", "https://www.alternate.es/"),
}

stores = sa.table("stores", sa.column("slug", sa.String), sa.column("shortcut_url", sa.String))


def _apply(direction: int) -> None:
    for slug, urls in CHANGES.items():
        old, new = urls[::direction]
        op.execute(
            stores.update()
            .where(stores.c.slug == slug, stores.c.shortcut_url == old)
            .values(shortcut_url=new)
        )


def upgrade() -> None:
    _apply(1)


def downgrade() -> None:
    _apply(-1)

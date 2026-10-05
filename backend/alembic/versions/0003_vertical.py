"""modo de búsqueda (tecnología / coches) en tiendas y términos vigilados

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-05
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for table in ("stores", "watch_terms"):
        op.add_column(
            table, sa.Column("vertical", sa.String(10), nullable=False, server_default="tech")
        )


def downgrade() -> None:
    for table in ("stores", "watch_terms"):
        op.drop_column(table, "vertical")

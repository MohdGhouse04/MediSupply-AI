"""baseline existing database schema

Revision ID: 184a67c288ff
Revises:
Create Date: 2026-11-22 17:06:48.790676
"""

from typing import Sequence, Union

from alembic import op

from backend.app.database.base import Base
import backend.app.models  # noqa: F401


revision: str = "184a67c288ff"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create core application tables."""
    bind = op.get_bind()

    core_tables = [
        table
        for table in Base.metadata.sorted_tables
        if table.name != "stockout_alerts"
    ]

    Base.metadata.create_all(bind=bind, tables=core_tables)


def downgrade() -> None:
    """Drop core application tables."""
    bind = op.get_bind()

    core_tables = [
        table
        for table in Base.metadata.sorted_tables
        if table.name != "stockout_alerts"
    ]

    Base.metadata.drop_all(bind=bind, tables=core_tables)

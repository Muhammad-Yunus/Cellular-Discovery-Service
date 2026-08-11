"""add mission_logs table

Revision ID: 9306296c5560
Revises: 6f2b2fd5c9fe
Create Date: 2026-08-11 07:47:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9306296c5560'
down_revision: Union[str, None] = '6f2b2fd5c9fe'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Table already exists in production DB (was created manually or via
    # Base.metadata.create_all()). This migration is a no-op for upgrade —
    # it exists only to register the schema in Alembic's migration history.
    # Use `alembic stamp 9306296c5560` after deploying.
    pass


def downgrade() -> None:
    # Only drop if we created it (idempotent guard).
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT EXISTS ("
            "SELECT FROM information_schema.tables "
            "WHERE table_schema = 'app' AND table_name = 'mission_logs'"
            ")"
        )
    )
    if result.scalar():
        op.drop_table('mission_logs', schema='app')

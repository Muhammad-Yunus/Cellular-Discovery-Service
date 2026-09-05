"""add band column to missions table

Revision ID: e1f2g3h4i5j6
Revises: abc123_def_band_scan_sessions
Create Date: 2026-09-05 13:00:00.000000

Adds:
- band column to missions table (VARCHAR 20, nullable)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e1f2g3h4i5j6'
down_revision: Union[str, None] = 'abc123_def_band_scan_sessions'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(connection, table_name, column_name, schema='app'):
    """Check if a column exists in a table."""
    result = connection.execute(sa.text(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_schema = :schema AND table_name = :table AND column_name = :column"
    ), {
        'schema': schema,
        'table': table_name,
        'column': column_name
    })
    return result.fetchone() is not None


def upgrade() -> None:
    conn = op.get_bind()

    # Add band column to missions if not exists
    if not _column_exists(conn, 'missions', 'band'):
        op.add_column(
            'missions',
            sa.Column('band', sa.String(length=20), nullable=True),
            schema='app'
        )


def downgrade() -> None:
    op.drop_column('missions', 'band', schema='app')

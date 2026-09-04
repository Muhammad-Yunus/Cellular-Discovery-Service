"""add band column to scan_sessions

Revision ID: abc123_def_band_scan_sessions
Revises: f1a2b3c4d5e6
Create Date: 2026-09-01 12:00:00.000000

Adds:
- band column to scan_sessions (VARCHAR 10, NOT NULL) for multi-band scanning
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'abc123_def_band_scan_sessions'
down_revision: Union[str, None] = 'f1a2b3c4d5e6'
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
    
    # Add band column to scan_sessions if not exists
    if not _column_exists(conn, 'scan_sessions', 'band'):
        op.add_column(
            'scan_sessions',
            sa.Column('band', sa.String(length=10), nullable=False, server_default=''),
            schema='app'
        )


def downgrade() -> None:
    op.drop_column('scan_sessions', 'band', schema='app')

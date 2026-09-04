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


def upgrade() -> None:
    op.add_column(
        'scan_sessions',
        sa.Column('band', sa.String(length=10), nullable=False, server_default=''),
        schema='app'
    )


def downgrade() -> None:
    op.drop_column('scan_sessions', 'band', schema='app')

"""add tty_port column and LTE scan fields

Revision ID: d8f2e3a1b0c9
Revises: c711c08c3947
Create Date: 2026-08-27 19:50:00.000000

Adds:
- tty_port column to scan_sessions (default "")
- GPS metadata columns already added in abc123_ad_altitude_course (altitude, course_deg)
- Detailed cell fields to scan_results (frequency_mhz, earfcn, band, pci, rsrp, rsrq, snr)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd8f2e3a1b0c9'
down_revision: Union[str, None] = 'c711c08c3947'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add tty_port column to scan_sessions
    op.add_column(
        'scan_sessions',
        sa.Column('tty_port', sa.String(length=255), nullable=False, server_default=""),
        schema='app'
    )
    # Add detailed LTE scan fields to scan_results
    op.add_column(
        'scan_results',
        sa.Column('frequency_mhz', sa.Float(), nullable=True),
        schema='app'
    )
    op.add_column(
        'scan_results',
        sa.Column('earfcn', sa.Integer(), nullable=True),
        schema='app'
    )
    op.add_column(
        'scan_results',
        sa.Column('band', sa.String(length=10), nullable=True),
        schema='app'
    )
    op.add_column(
        'scan_results',
        sa.Column('pci', sa.Integer(), nullable=True),
        schema='app'
    )
    op.add_column(
        'scan_results',
        sa.Column('rsrp', sa.Float(), nullable=True),
        schema='app'
    )
    op.add_column(
        'scan_results',
        sa.Column('rsrq', sa.Float(), nullable=True),
        schema='app'
    )
    op.add_column(
        'scan_results',
        sa.Column('snr', sa.Float(), nullable=True),
        schema='app'
    )


def downgrade() -> None:
    op.drop_column('scan_results', 'snr', schema='app')
    op.drop_column('scan_results', 'rsrq', schema='app')
    op.drop_column('scan_results', 'rsrp', schema='app')
    op.drop_column('scan_results', 'pci', schema='app')
    op.drop_column('scan_results', 'band', schema='app')
    op.drop_column('scan_results', 'earfcn', schema='app')
    op.drop_column('scan_results', 'frequency_mhz', schema='app')
    op.drop_column('scan_sessions', 'tty_port', schema='app')

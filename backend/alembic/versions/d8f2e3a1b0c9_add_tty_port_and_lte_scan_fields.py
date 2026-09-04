"""add tty_port column and LTE scan fields

Revision ID: d8f2e3a1b0c9
Revises: abc123_ad_altitude_course
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
down_revision: Union[str, None] = 'abc123_ad_altitude_course'
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
    
    # Add tty_port column to scan_sessions if not exists
    if not _column_exists(conn, 'scan_sessions', 'tty_port'):
        op.add_column(
            'scan_sessions',
            sa.Column('tty_port', sa.String(length=255), nullable=False, server_default=""),
            schema='app'
        )
    
    # Add detailed LTE scan fields to scan_results if not exists
    lte_fields = [
        ('frequency_mhz', sa.Float(), True),
        ('earfcn', sa.Integer(), True),
        ('band', sa.String(length=10), True),
        ('pci', sa.Integer(), True),
        ('rsrp', sa.Float(), True),
        ('rsrq', sa.Float(), True),
        ('snr', sa.Float(), True),
    ]
    
    for col_name, col_type, nullable in lte_fields:
        if not _column_exists(conn, 'scan_results', col_name):
            op.add_column(
                'scan_results',
                sa.Column(col_name, col_type, nullable=nullable),
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

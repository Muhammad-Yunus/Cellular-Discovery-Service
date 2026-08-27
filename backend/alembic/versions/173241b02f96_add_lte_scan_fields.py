"""add_lte_scan_fields

Revision ID: 173241b02f96
Revises: abc123_ad_altitude_course
Create Date: 2026-08-26 10:27:29.069567

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '173241b02f96'
down_revision: Union[str, None] = 'abc123_ad_altitude_course'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add lte-scan (RTL-SDR) fields to scan_results
    op.add_column('scan_results', sa.Column('earfcn', sa.String(length=20), nullable=True), schema='app')
    op.add_column('scan_results', sa.Column('pci', sa.Integer(), nullable=True), schema='app')
    op.add_column('scan_results', sa.Column('frequency_mhz', sa.Float(), nullable=True), schema='app')
    op.add_column('scan_results', sa.Column('rsrp', sa.Float(), nullable=True), schema='app')
    op.add_column('scan_results', sa.Column('band', sa.String(length=10), nullable=True), schema='app')


def downgrade() -> None:
    op.drop_column('scan_results', 'band', schema='app')
    op.drop_column('scan_results', 'rsrp', schema='app')
    op.drop_column('scan_results', 'frequency_mhz', schema='app')
    op.drop_column('scan_results', 'pci', schema='app')
    op.drop_column('scan_results', 'earfcn', schema='app')

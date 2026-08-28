"""add device_status table

Revision ID: f1a2b3c4d5e6
Revises: d8f2e3a1b0c9
Create Date: 2026-08-28 10:00:00.000000

Creates the device_status table to store periodic peripheral status
information including SDR, GPS, machine metrics, and network status.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, None] = 'd8f2e3a1b0c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'device_status',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('collected_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        # SDR
        sa.Column('sdr_type', sa.String(length=255), nullable=True),
        sa.Column('sdr_status', sa.String(length=50), nullable=True),
        sa.Column('sdr_message', sa.Text(), nullable=True),
        # GPS
        sa.Column('gps_type', sa.String(length=255), nullable=True),
        sa.Column('gps_status', sa.String(length=50), nullable=True),
        sa.Column('gps_message', sa.Text(), nullable=True),
        sa.Column('gps_latitude', sa.Float(), nullable=True),
        sa.Column('gps_longitude', sa.Float(), nullable=True),
        sa.Column('gps_satellites', sa.Integer(), nullable=True),
        # Machine
        sa.Column('cpu_percent', sa.Float(), nullable=True),
        sa.Column('memory_total_mb', sa.Integer(), nullable=True),
        sa.Column('memory_used_mb', sa.Integer(), nullable=True),
        sa.Column('memory_percent', sa.Float(), nullable=True),
        sa.Column('temperature_c', sa.Float(), nullable=True),
        sa.Column('disk_total_gb', sa.Float(), nullable=True),
        sa.Column('disk_used_gb', sa.Float(), nullable=True),
        sa.Column('disk_percent', sa.Float(), nullable=True),
        sa.Column('load_avg_1m', sa.Float(), nullable=True),
        sa.Column('uptime_seconds', sa.Integer(), nullable=True),
        # Network
        sa.Column('network_status', sa.String(length=50), nullable=True),
        sa.Column('network_mode', sa.String(length=50), nullable=True),
        sa.Column('ip_address', sa.String(length=50), nullable=True),
        sa.Column('gateway', sa.String(length=50), nullable=True),
        sa.Column('dns_servers', sa.Text(), nullable=True),
        # Metadata
        sa.Column('collector_version', sa.String(length=50), nullable=True),
        sa.Column('health_summary_active', sa.Integer(), nullable=True),
        sa.Column('health_summary_missing', sa.Integer(), nullable=True),
        sa.Column('health_summary_error', sa.Integer(), nullable=True),
        sa.Column('health_summary_total', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        schema='app',
    )
    
    # Create indexes
    op.create_index(
        'ix_device_status_collected_at',
        'device_status',
        ['collected_at'],
        schema='app',
    )
    op.create_index(
        'ix_device_status_sdr_status',
        'device_status',
        ['sdr_status'],
        schema='app',
    )
    op.create_index(
        'ix_device_status_gps_status',
        'device_status',
        ['gps_status'],
        schema='app',
    )
    op.create_index(
        'ix_device_status_network_status',
        'device_status',
        ['network_status'],
        schema='app',
    )


def downgrade() -> None:
    op.drop_index('ix_device_status_network_status', table_name='device_status', schema='app')
    op.drop_index('ix_device_status_gps_status', table_name='device_status', schema='app')
    op.drop_index('ix_device_status_sdr_status', table_name='device_status', schema='app')
    op.drop_index('ix_device_status_collected_at', table_name='device_status', schema='app')
    op.drop_table('device_status', schema='app')

"""add altitude and course_deg columns to scan_sessions

Revision ID: abc123_ad_altitude_course
Revises: 9306296c5560
Create Date: 2026-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'abc123_ad_altitude_course'
down_revision: Union[str, None] = '9306296c5560'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('scan_sessions', sa.Column('altitude', sa.Float(), nullable=True), schema='app')
    op.add_column('scan_sessions', sa.Column('course_deg', sa.Float(), nullable=True), schema='app')


def downgrade() -> None:
    op.drop_column('scan_sessions', 'course_deg', schema='app')
    op.drop_column('scan_sessions', 'altitude', schema='app')

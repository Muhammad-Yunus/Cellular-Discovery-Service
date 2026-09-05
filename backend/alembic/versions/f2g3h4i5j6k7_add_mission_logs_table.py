"""add mission_logs table

Revision ID: f2g3h4i5j6k7
Revises: e1f2g3h4i5j6
Create Date: 2026-09-05 14:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f2g3h4i5j6k7'
down_revision: Union[str, None] = 'e1f2g3h4i5j6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create mission_logs table if it does not exist
    op.execute("""
        CREATE TABLE IF NOT EXISTS app.mission_logs (
            id SERIAL NOT NULL,
            mission_id INTEGER NOT NULL,
            timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
            event_type VARCHAR(50) NOT NULL,
            message TEXT,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
            PRIMARY KEY (id),
            FOREIGN KEY (mission_id) REFERENCES app.missions(id) ON DELETE CASCADE
        )
    """)
    
    # Create indexes if they do not exist
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_mission_logs_mission 
        ON app.mission_logs(mission_id)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_mission_logs_timestamp 
        ON app.mission_logs(timestamp)
    """)


def downgrade() -> None:
    op.drop_table('mission_logs', schema='app')

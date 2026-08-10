from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func, text
from app.db.base import Base
from app.db.models.mission_location import MissionLocation
from app.db.models.mission_log import MissionLog


class Mission(Base):
    __tablename__ = "missions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('IDLE','PLANNING','READY','STARTING','RUNNING',"
            "'PAUSED','COMPLETED','STOPPED','FAILED')",
            name="status",
        ),
        CheckConstraint("radius_meters > 0", name="radius_positive"),
        Index("idx_missions_status", "status"),
        Index("idx_missions_start_loc", "start_location_id"),
        Index("idx_missions_current_loc", "current_location_id"),
        {"schema": "app"},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(20), nullable=False, server_default=text("'IDLE'"))
    radius_meters = Column(Integer, nullable=True, server_default=text("20"))
    tty_port = Column(String(50), nullable=True)
    start_location_id = Column(
        Integer,
        ForeignKey(
            "app.mission_locations.id",
            ondelete="SET NULL",
            name="fk_missions_start_location",
            use_alter=True,
        ),
        nullable=True,
    )
    current_location_id = Column(
        Integer,
        ForeignKey(
            "app.mission_locations.id",
            ondelete="SET NULL",
            name="fk_missions_current_location",
            use_alter=True,
        ),
        nullable=True,
    )
    total_locations = Column(Integer, nullable=False, server_default=text("0"))
    visited_locations = Column(Integer, nullable=False, server_default=text("0"))
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    stopped_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    locations = relationship(
        "MissionLocation",
        back_populates="mission",
        foreign_keys="[MissionLocation.mission_id]",
        cascade="all, delete-orphan",
        order_by=lambda: (MissionLocation.sequence_order, MissionLocation.id),
    )
    logs = relationship(
        "MissionLog",
        back_populates="mission",
        cascade="all, delete-orphan",
        order_by="MissionLog.timestamp",
    )

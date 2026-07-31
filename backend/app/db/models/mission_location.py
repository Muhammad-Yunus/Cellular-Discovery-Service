from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func, text
from app.db.base import Base


class MissionLocation(Base):
    __tablename__ = "mission_locations"
    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING','IN_PROGRESS','VISITED','SKIPPED')",
            name="status",
        ),
        CheckConstraint("latitude BETWEEN -90 AND 90", name="latitude_range"),
        CheckConstraint("longitude BETWEEN -180 AND 180", name="longitude_range"),
        UniqueConstraint("mission_id", "cellular_tower_id", name="uq_mission_location_tower"),
        Index("idx_mission_locations_mission", "mission_id"),
        Index("idx_mission_locations_sequence", "mission_id", "sequence_order"),
        Index("idx_mission_locations_status", "status"),
        Index("idx_mission_locations_scan_session", "scan_session_id"),
        Index("idx_mission_locations_batch", "upload_batch_id"),
        {"schema": "app"},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    mission_id = Column(
        Integer, ForeignKey("app.missions.id", ondelete="CASCADE"), nullable=False
    )
    cellular_tower_id = Column(String(100), nullable=False)
    cellular_tower_name = Column(String(255), nullable=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    upload_batch_id = Column(String(36), nullable=True)
    sequence_order = Column(Integer, nullable=True)
    status = Column(String(20), nullable=False, server_default=text("'PENDING'"))
    distance_from_previous_meters = Column(Float, nullable=True)
    bearing_from_previous_degrees = Column(Float, nullable=True)
    estimated_arrival_time = Column(DateTime(timezone=True), nullable=True)
    actual_visit_time = Column(DateTime(timezone=True), nullable=True)
    scan_session_id = Column(
        Integer,
        ForeignKey("app.scan_sessions.id", ondelete="SET NULL"),
        unique=True,
        nullable=True,
    )
    visited_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    mission = relationship(
        "Mission", back_populates="locations", foreign_keys="[MissionLocation.mission_id]"
    )
    scan_session = relationship(
        "ScanSession",
        foreign_keys="[MissionLocation.scan_session_id]",
        uselist=False,
    )

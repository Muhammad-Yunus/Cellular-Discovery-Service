from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base


class ScanSession(Base):
    __tablename__ = "scan_sessions"
    __table_args__ = (
        Index("ix_scan_sessions_mission_location_id", "mission_location_id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    scan_time = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    tty_port = Column(String(255), nullable=False, default="")
    band = Column(String(10), nullable=False)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    mission_location_id = Column(
        Integer,
        ForeignKey("mission_locations.id", ondelete="SET NULL", use_alter=True),
        nullable=True,
    )
    altitude = Column(Float, nullable=True)
    course_deg = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    results = relationship("ScanResult", back_populates="session", cascade="all, delete-orphan")
    mission_location = relationship(
        "MissionLocation",
        foreign_keys="[ScanSession.mission_location_id]",
        uselist=False,
    )

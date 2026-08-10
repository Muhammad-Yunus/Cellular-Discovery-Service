from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base


class MissionLog(Base):
    __tablename__ = "mission_logs"
    __table_args__ = (
        Index("idx_mission_logs_mission", "mission_id"),
        Index("idx_mission_logs_timestamp", "timestamp"),
        {"schema": "app"},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    mission_id = Column(
        Integer, ForeignKey("app.missions.id", ondelete="CASCADE"), nullable=False
    )
    timestamp = Column(DateTime(timezone=True), nullable=False)
    event_type = Column(String(50), nullable=False)
    message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    mission = relationship("Mission", back_populates="logs")

    def __repr__(self):
        return f"<MissionLog(id={self.id}, mission_id={self.mission_id}, event={self.event_type})>"

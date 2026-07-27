from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base


class ScanSession(Base):
    __tablename__ = "scan_sessions"
    __table_args__ = {"schema": "app"}

    id = Column(Integer, primary_key=True, autoincrement=True)
    scan_time = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    tty_port = Column(String(50), nullable=False)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    results = relationship("ScanResult", back_populates="session", cascade="all, delete-orphan")

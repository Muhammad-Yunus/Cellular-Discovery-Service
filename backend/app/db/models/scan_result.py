from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from app.db.base import Base


class ScanResult(Base):
    __tablename__ = "scan_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("scan_sessions.id", ondelete="CASCADE"), nullable=False)
    operator_name = Column(String(100), nullable=True)
    mcc = Column(String(10), nullable=True)
    mnc = Column(String(10), nullable=True)
    rat = Column(String(50), nullable=True)
    status = Column(String(50), nullable=True)

    session = relationship("ScanSession", back_populates="results")

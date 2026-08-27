from sqlalchemy import Column, Integer, String, Float, ForeignKey
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
    # Additional detail fields
    frequency_mhz = Column(Float, nullable=True)
    earfcn = Column(Integer, nullable=True)
    band = Column(String(10), nullable=True)
    pci = Column(Integer, nullable=True)
    rsrp = Column(Float, nullable=True)
    rsrq = Column(Float, nullable=True)
    snr = Column(Float, nullable=True)

    session = relationship("ScanSession", back_populates="results")

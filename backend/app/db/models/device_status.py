from sqlalchemy import Column, Integer, String, Float, Text, DateTime, CheckConstraint
from sqlalchemy.sql import func
from app.db.base import Base


class DeviceStatus(Base):
    __tablename__ = "device_status"
    __table_args__ = (
        CheckConstraint(
            "sdr_status IN ('active', 'missing', 'error', 'unknown')",
            name="ck_device_status_sdr_status",
        ),
        CheckConstraint(
            "gps_status IN ('active', 'missing', 'error', 'unknown')",
            name="ck_device_status_gps_status",
        ),
        CheckConstraint(
            "network_status IN ('online', 'offline', 'error')",
            name="ck_device_status_network_status",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    collected_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # SDR
    sdr_type = Column(String(255), nullable=True)
    sdr_status = Column(String(50), nullable=True)
    sdr_message = Column(Text, nullable=True)

    # GPS
    gps_type = Column(String(255), nullable=True)
    gps_status = Column(String(50), nullable=True)
    gps_message = Column(Text, nullable=True)
    gps_latitude = Column(Float, nullable=True)
    gps_longitude = Column(Float, nullable=True)
    gps_satellites = Column(Integer, nullable=True)

    # Machine
    cpu_percent = Column(Float, nullable=True)
    memory_total_mb = Column(Integer, nullable=True)
    memory_used_mb = Column(Integer, nullable=True)
    memory_percent = Column(Float, nullable=True)
    temperature_c = Column(Float, nullable=True)
    disk_total_gb = Column(Float, nullable=True)
    disk_used_gb = Column(Float, nullable=True)
    disk_percent = Column(Float, nullable=True)
    load_avg_1m = Column(Float, nullable=True)
    uptime_seconds = Column(Integer, nullable=True)

    # Network
    network_status = Column(String(50), nullable=True)
    network_mode = Column(String(50), nullable=True)
    ip_address = Column(String(50), nullable=True)
    gateway = Column(String(50), nullable=True)
    dns_servers = Column(Text, nullable=True)  # JSON string

    # Metadata
    collector_version = Column(String(50), nullable=True)
    health_summary_active = Column(Integer, nullable=True)
    health_summary_missing = Column(Integer, nullable=True)
    health_summary_error = Column(Integer, nullable=True)
    health_summary_total = Column(Integer, nullable=True)

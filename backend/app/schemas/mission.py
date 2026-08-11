import subprocess
import re
from enum import Enum
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field, field_validator
from app.schemas.mission_location import MissionLocationResponse


class MissionStatus(str, Enum):
    IDLE = "IDLE"
    PLANNING = "PLANNING"
    READY = "READY"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    STOPPED = "STOPPED"
    FAILED = "FAILED"


def _get_connected_usb_ports() -> set[str]:
    """Get set of connected /dev/ttyUSB* ports from lsusb."""
    try:
        result = subprocess.run(
            ["lsusb"], capture_output=True, text=True, timeout=5
        )
        if result.returncode != 0:
            return set()
        # Find all Bus:Device pairs
        bus_dev_pattern = re.compile(r"Bus (\d+) Device (\d+): ID ([0-9a-f]{4}):([0-9a-f]{4})")
        bus_devices = set()
        for line in result.stdout.splitlines():
            match = bus_dev_pattern.search(line)
            if match:
                bus_devices.add((match.group(1), match.group(2)))
        
        # Map to /dev/ttyUSB* using udevadm
        ports = set()
        import glob
        for tty_dev in glob.glob("/dev/ttyUSB*"):
            dev_name = tty_dev.replace("/dev/", "")
            try:
                udev_info = subprocess.run(
                    ["udevadm", "info", "-n", dev_name],
                    capture_output=True, text=True, timeout=5
                )
                # Check if this device appears in lsusb output
                if udev_info.returncode == 0:
                    # Get bus:dev from udev
                    for line in udev_info.stdout.splitlines():
                        if line.startswith("E: DEVNAME="):
                            port_name = line.split("=", 1)[1].replace("/dev/", "")
                            ports.add(f"/dev/{port_name}")
            except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
                continue
        return ports
    except Exception:
        return set()


def _validate_tty_port(cls, v):
    if v is None:
        return v
    v = str(v).strip()
    if not v.startswith("/dev/ttyUSB"):
        raise ValueError("tty_port must be a /dev/ttyUSB* device")
    # Check if port exists in system
    if not __import__("os").path.exists(v):
        raise ValueError(f"tty_port {v} does not exist on this device")
    # Check if port appears in lsusb (USB-connected device)
    connected_ports = _get_connected_usb_ports()
    if connected_ports and v not in connected_ports:
        raise ValueError(f"tty_port {v} is not connected via USB. Available: {sorted(connected_ports)}")
    return v


class MissionCreate(BaseModel):
    name: str
    description: Optional[str] = None
    radius_meters: Optional[int] = Field(default=None, ge=10, le=100)
    tty_port: str  # Required: must be a valid, existing /dev/ttyUSB* port

    @field_validator("name")
    @classmethod
    def _validate_name(cls, v):
        name = str(v).strip()
        if not name:
            raise ValueError("Mission name is required")
        return name

    @field_validator("tty_port")
    @classmethod
    def _validate_tty_port(cls, v):
        return _validate_tty_port(cls, v)


class MissionUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    radius_meters: Optional[int] = Field(default=None, ge=10, le=100)
    tty_port: Optional[str] = None
    start_location_id: Optional[int] = None

    @field_validator("name")
    @classmethod
    def _validate_name(cls, v):
        if v is None:
            raise ValueError("Mission name is required")
        name = str(v).strip()
        if not name:
            raise ValueError("Mission name is required")
        return name

    @field_validator("tty_port")
    @classmethod
    def _validate_tty_port(cls, v):
        return _validate_tty_port(cls, v)


class MissionResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    status: MissionStatus
    radius_meters: Optional[int] = None
    tty_port: Optional[str] = None
    start_location_id: Optional[int] = None
    current_location_id: Optional[int] = None
    total_locations: int
    visited_locations: int
    progress_percent: float
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    stopped_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class MissionDetailResponse(MissionResponse):
    locations: list[MissionLocationResponse]


class MissionListResponse(BaseModel):
    items: list[MissionResponse]
    total: int
    page: int
    page_size: int


class MissionDeleteResponse(BaseModel):
    message: str
    id: int

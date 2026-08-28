"""
Device Collector: Collects peripheral status data and persists to database.

Collects data from:
- RTL-SDR (via rtl_test CLI)
- GPS (via existing CLIGPSProvider)
- Machine metrics (CPU, RAM, Disk, Temp, Load)
- Network (IP, mode, connectivity)
"""
import asyncio
import json
import logging
import os
import shutil
import socket
import subprocess
import sys
import time
from typing import Optional

import psutil
from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.db.models.device_status import DeviceStatus
from app.gps.factory import create_gps_provider

# Configure logging to write to stderr for systemd journal visibility
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
)
logger = logging.getLogger(__name__)


class DeviceCollector:
    """Collects and stores device peripheral status."""

    COLLECTOR_VERSION = "0.3.0"

    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()

    async def collect_all(self) -> DeviceStatus:
        """Collect all peripheral status and save to database."""
        logger.info("Starting device status collection...")

        # Collect all metrics (GPS and SDR in parallel, Machine and Network synchronous)
        sdr_data = await self._collect_sdr_async()
        gps_data = await self._collect_gps_async()
        machine_data = self._collect_machine()
        network_data = self._collect_network()

        # Calculate health summary
        health_summary = self._calculate_health_summary(
            sdr_data["status"],
            gps_data["status"],
        )

        # Create database record
        record = DeviceStatus(
            # SDR
            sdr_type=sdr_data.get("type"),
            sdr_status=sdr_data.get("status"),
            sdr_message=sdr_data.get("message"),
            # GPS
            gps_type=gps_data.get("type"),
            gps_status=gps_data.get("status"),
            gps_message=gps_data.get("message"),
            gps_latitude=gps_data.get("latitude"),
            gps_longitude=gps_data.get("longitude"),
            gps_satellites=gps_data.get("satellites"),
            # Machine
            cpu_percent=machine_data.get("cpu_percent"),
            memory_total_mb=machine_data.get("memory_total_mb"),
            memory_used_mb=machine_data.get("memory_used_mb"),
            memory_percent=machine_data.get("memory_percent"),
            temperature_c=machine_data.get("temperature_c"),
            disk_total_gb=machine_data.get("disk_total_gb"),
            disk_used_gb=machine_data.get("disk_used_gb"),
            disk_percent=machine_data.get("disk_percent"),
            load_avg_1m=machine_data.get("load_avg_1m"),
            uptime_seconds=machine_data.get("uptime_seconds"),
            # Network
            network_status=network_data.get("status"),
            network_mode=network_data.get("mode"),
            ip_address=network_data.get("ip_address"),
            gateway=network_data.get("gateway"),
            dns_servers=json.dumps(network_data.get("dns", []))
            if network_data.get("dns")
            else None,
            # Metadata
            collector_version=self.COLLECTOR_VERSION,
            health_summary_active=health_summary["active"],
            health_summary_missing=health_summary["missing"],
            health_summary_error=health_summary["error"],
            health_summary_total=health_summary["total"],
        )

        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)

        logger.info(
            f"Device status collected: SDR={sdr_data['status']}, "
            f"GPS={gps_data['status']}, Network={network_data['status']}, "
            f"Record ID={record.id}"
        )

        return record

    async def _collect_sdr_async(self) -> dict:
        """Collect RTL-SDR status using rtl_test."""
        result = {
            "type": None,
            "status": "unknown",
            "message": "Checking RTL-SDR status...",
        }

        try:
            # Check if rtl_test is available
            rtl_test_path = shutil.which("rtl_test")
            if not rtl_test_path:
                result["status"] = "missing"
                result["message"] = "rtl_test command not found in PATH"
                return result

            # Run rtl_test with timeout (10 seconds)
            proc = await asyncio.wait_for(
                asyncio.create_subprocess_exec(
                    "rtl_test",
                    "-t",
                    "10",  # Test for 10 seconds
                    "-d",
                    "0",  # Use first device
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                ),
                timeout=15,
            )

            stdout, stderr = await proc.communicate()

            if proc.returncode == 0:
                # Parse output for device info
                output = stdout.decode()

                # Extract tuner type
                if "E4000" in output:
                    result["type"] = "RTL-SDR V3 (E4000)"
                elif "FC0012" in output:
                    result["type"] = "RTL-SDR BASIC (FC0012)"
                elif "FC0013" in output:
                    result["type"] = "RTL-SDR Blog V3 (FC0013)"
                elif "XR20V" in output or "R820T" in output:
                    result["type"] = "RTL-SDR R820T"
                else:
                    result["type"] = "RTL-SDR Dongle"

                # Extract serial number if available
                for line in output.split("\n"):
                    if "Serial number:" in line:
                        serial = line.split(":")[1].strip()
                        result[
                            "message"
                        ] = f"Test successful - tuner: {result['type']}, serial: {serial}"
                        break
                else:
                    result["message"] = f"rtl_test successful - {result['type']}"

                result["status"] = "active"
            else:
                error_msg = stderr.decode().strip()
                result["status"] = "error"
                result["message"] = f"rtl_test failed: {error_msg[:200]}"

        except asyncio.TimeoutError:
            result["status"] = "error"
            result["message"] = "rtl_test timed out after 15 seconds"
        except FileNotFoundError:
            result["status"] = "missing"
            result["message"] = "rtl_test binary not found"
        except Exception as e:
            result["status"] = "error"
            result["message"] = f"Unexpected error: {str(e)[:200]}"

        return result

    async def _collect_gps_async(self) -> dict:
        """Collect GPS status using existing provider."""
        result = {
            "type": None,
            "status": "unknown",
            "message": "Checking GPS status...",
            "latitude": None,
            "longitude": None,
            "satellites": None,
        }

        try:
            provider = create_gps_provider(self.settings.GPS_PROVIDER)

            # Get device type from settings
            tty_port = self.settings.DEFAULT_GPS_TTY
            result["type"] = f"GPS Module - {tty_port}"

            # Check if port exists
            if not os.path.exists(tty_port):
                result["status"] = "missing"
                result["message"] = f"GPS port {tty_port} not found"
                return result

            # Try to get location (using sync method via to_thread)
            location = await asyncio.wait_for(
                asyncio.to_thread(provider.get_location), timeout=10
            )

            result["status"] = "active"
            result["latitude"] = location.latitude
            result["longitude"] = location.longitude
            # Try to get satellites count from the raw output if available
            result["message"] = (
                f"fix: true, lat: {location.latitude:.6f}, lon: {location.longitude:.6f}"
            )

        except FileNotFoundError:
            result["status"] = "missing"
            result["message"] = f"GPS port {tty_port} not found"
        except asyncio.TimeoutError:
            result["status"] = "error"
            result["message"] = "GPS read timed out after 10 seconds"
        except Exception as e:
            result["status"] = "error"
            result["message"] = f"GPS error: {str(e)[:200]}"

        return result

    def _collect_machine(self) -> dict:
        """Collect machine metrics using psutil."""
        # CPU
        cpu_percent = psutil.cpu_percent(interval=1)

        # Memory
        memory = psutil.virtual_memory()

        # Temperature (RPi-specific)
        temperature_c = None
        try:
            # Raspberry Pi thermal zone
            temp_file = "/sys/class/thermal/thermal_zone0/temp"
            if os.path.exists(temp_file):
                with open(temp_file) as f:
                    temperature_c = float(f.read().strip()) / 1000.0
        except Exception:
            pass

        # Disk
        disk = psutil.disk_usage("/")

        # Load average
        load_avg = os.getloadavg() if hasattr(os, "getloadavg") else (0.0, 0.0, 0.0)

        # Uptime
        uptime_seconds = int(time.time() - psutil.boot_time())

        return {
            "cpu_percent": cpu_percent,
            "memory_total_mb": memory.total // (1024 * 1024),
            "memory_used_mb": memory.used // (1024 * 1024),
            "memory_percent": memory.percent,
            "temperature_c": round(temperature_c, 1) if temperature_c else None,
            "disk_total_gb": round(disk.total / (1024**3), 1),
            "disk_used_gb": round(disk.used / (1024**3), 1),
            "disk_percent": disk.percent,
            "load_avg_1m": round(load_avg[0], 2),
            "uptime_seconds": uptime_seconds,
        }

    def _collect_network(self) -> dict:
        """Collect network status and configuration."""
        result = {
            "status": "offline",
            "mode": None,
            "ip_address": None,
            "gateway": None,
            "dns": [],
        }

        try:
            # Check internet connectivity
            try:
                socket.create_connection(("8.8.8.8", 53), timeout=3)
                result["status"] = "online"
            except (socket.error, socket.timeout):
                result["status"] = "offline"

            # Get IP address
            hostname = socket.gethostname()
            try:
                ip_address = socket.gethostbyname(hostname)
                result["ip_address"] = ip_address
            except socket.gaierror:
                result["ip_address"] = "127.0.0.1"

            # Determine network mode
            if ip_address and (
                ip_address.startswith("192.168.") or ip_address.startswith("10.")
            ):
                result["mode"] = "dhcp"

            # Get gateway (if available)
            try:
                if shutil.which("ip"):
                    proc = subprocess.run(
                        ["ip", "route"],
                        capture_output=True,
                        text=True,
                        timeout=5,
                    )
                    for line in proc.stdout.split("\n"):
                        if "default via" in line:
                            result["gateway"] = (
                                line.split("default via")[1].split()[0]
                            )
                            break
            except Exception:
                pass

            # Get DNS servers
            try:
                with open("/etc/resolv.conf") as f:
                    for line in f:
                        if line.startswith("nameserver"):
                            result["dns"].append(line.split()[1])
            except Exception:
                pass

        except Exception as e:
            result["status"] = "error"
            result["mode"] = f"error: {str(e)[:50]}"

        return result

    def _calculate_health_summary(
        self, sdr_status: str, gps_status: str
    ) -> dict:
        """Calculate health summary across all peripherals."""
        statuses = [sdr_status, gps_status]

        # Add machine and network (always present, either ok or not)
        summary = {"total": 4, "active": 0, "missing": 0, "error": 0}

        for status in statuses:
            if status == "active":
                summary["active"] += 1
            elif status == "missing":
                summary["missing"] += 1
            elif status == "error":
                summary["error"] += 1
            else:
                summary["active"] += 1

        return summary

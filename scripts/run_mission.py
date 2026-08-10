#!/usr/bin/env python3
"""
================================================================================
Mission Autonomy Script - Cellular Discovery Service
================================================================================
Script ini digunakan untuk menjalankan mission scanning secara otomatis.

Workflow:
  1. Mendeteksi lokasi GPS real (atau pakai override dari parameter)
  2. Membuat mission baru via API backend
  3. Menghasilkan 5 lokasi tower pada jarak 200-400m dari device
  4. Upload lokasi dalam format CSV ke backend
  5. Menjalankan route planning untuk optimasi urutan kunjungan
  6. Mengaktifkan Mock GPS (moving_mock) dengan waypoints sesuai lokasi tower
  7. Restart backend untuk apply perubahan konfigurasi GPS
  8. Menjalankan mission dan monitoring progress
  9. Setelah selesai, merevert GPS ke provider real (cli)

Cara Penggunaan:
  # Dengan GPS real dari device:
  python3 run_mission.py --name TEST-001

  # Dengan koordinat override (untuk testing tanpa GPS):
  python3 run_mission.py --name TEST-002 --lat -6.175 --lon 106.827

  # Custom parameter:
  python3 run_mission.py --name TEST-003 --count 10 --min-dist 100 --max-dist 500

================================================================================
"""

import os
import sys
import csv
import time
import json
import math
import argparse
import subprocess
import requests
from pathlib import Path
from io import StringIO

# ============================================================================
# KONFIGURASI
# ============================================================================

# Base URL API backend
API_BASE = "http://localhost:8001"

# Path ke file .env backend
ENV_FILE = "/home/pi/Cellular-Discovery-Service/backend/.env"

# Path ke direktori backend
BACKEND_DIR = "/home/pi/Cellular-Discovery-Service/backend"

# Konfigurasi GPS CLI (untuk provider 'cli')
GPS_CLI_COMMAND = "/home/pi/GPS/build/gps"
GPS_DEVICE = "/dev/ttyAMA0"
GPS_BAUD = 9600
GPS_COUNT = 5

# Konfigurasi lokasi tower
TOWER_SPACING_MIN = 200   # Jarak minimum tower dari device (meter)
TOWER_SPACING_MAX = 400   # Jarak maksimum tower dari device (meter)
TOWER_COUNT = 5           # Jumlah tower yang akan di-generate

# Konfigurasi monitoring
MONITOR_INTERVAL = 5      # Interval pengecekan status (detik)
MAX_MISSION_DURATION = 300  # Timeout maksimum mission (detik)

# Arah kompas untuk penempatan tower (derajat)
# 0° = Utara, 90° = Timur, 180° = Selatan, 270° = Barat
DIRECTIONS = [0, 72, 144, 216, 288]


# ============================================================================
# FUNGSI UTILITAS
# ============================================================================

def log(msg: str):
    """
    Mencetak pesan dengan timestamp ke stdout.
    flush=True memastikan pesan langsung keluar (tidak di-buffer).
    """
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


# ============================================================================
# FUNGSI GPS
# ============================================================================

def get_real_gps_location() -> tuple[float, float]:
    """
    Mendapatkan lokasi GPS real dari device /dev/ttyAMA0 menggunakan CLI tool.

    Returns:
        Tuple (latitude, longitude) dari GPS.
        Jika gagal, fallback ke koordinat dari MOCK_GPS_START_LAT/LON di .env.
    """
    log("Mendeteksi lokasi GPS real...")

    # Command untuk membaca GPS data
    # -d: device path, -b: baud rate, -w: wait for fix, -j: JSON output, -c: count
    # Filter: hanya ambil data dengan fix valid dan satellites_used > 0
    cmd = (
        f"{GPS_CLI_COMMAND} -d {GPS_DEVICE} -b {GPS_BAUD} "
        f"-w -j -c {GPS_COUNT} | jq -c 'select(.has_fix==true and (.satellites_used // 0) > 0)' | tail -1"
    )

    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)

        if result.returncode != 0 or not result.stdout.strip():
            raise ValueError(f"Tidak ada GPS fix: {result.stderr}")

        data = json.loads(result.stdout.strip())
        lat = data.get("latitude")
        lon = data.get("longitude")

        if lat is None or lon is None:
            raise ValueError(f"Data GPS tidak valid: {data}")

        sats = data.get('satellites_used', '?')
        log(f"GPS berhasil: {lat:.6f}, {lon:.6f} (satelit={sats})")
        return float(lat), float(lon)

    except Exception as e:
        log(f"ERROR mendapatkan GPS: {e}")
        log("Fallback ke MOCK_GPS_START_LAT/LON dari .env")

        # Fallback ke koordinat default dari environment
        lat = os.environ.get("MOCK_GPS_START_LAT", "-6.175")
        lon = os.environ.get("MOCK_GPS_START_LON", "106.827")
        return float(lat), float(lon)


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Menghitung jarak antara dua titik koordinat menggunakan Haversine formula.

    Args:
        lat1, lon1: Koordinat titik awal (derajat)
        lat2, lon2: Koordinat titik tujuan (derajat)

    Returns:
        Jarak dalam meter
    """
    R = 6371000.0  # Radius bumi dalam meter
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    return 2 * R * math.asin(math.sqrt(a))


def latlon_offset(lat: float, lon: float, bearing_deg: float, distance_m: float) -> tuple[float, float]:
    """
    Menghitung koordinat baru berdasarkan bearing dan jarak dari titik awal.

    Args:
        lat, lon: Titik awal (derajat)
        bearing_deg: Arah dalam derajat (0=Utara, 90=Timur)
        distance_m: Jarak dalam meter

    Returns:
        Tuple (lat_baru, lon_baru) dalam derajat
    """
    R = 6371000.0  # Radius bumi dalam meter
    bearing_rad = math.radians(bearing_deg)
    d = distance_m / R  # Sudut dalam radian

    new_lat = math.asin(
        math.sin(math.radians(lat)) * math.cos(d) +
        math.cos(math.radians(lat)) * math.sin(d) * math.cos(bearing_rad)
    )
    new_lon = math.radians(lon) + math.atan2(
        math.sin(bearing_rad) * math.sin(d) * math.cos(math.radians(lat)),
        math.cos(d) - math.sin(math.radians(lat)) * math.sin(new_lat)
    )
    return math.degrees(new_lat), math.degrees(new_lon)


def generate_tower_locations(start_lat: float, start_lon: float, count: int,
                              min_dist: float, max_dist: float) -> list[dict]:
    """
    Menghasilkan koordinat tower tower tersebar di sekitar titik start.

    Setiap tower ditempatkan pada arah yang berbeda dengan jarak random
    antara min_dist dan max_dist dari titik start.

    Args:
        start_lat, start_lon: Titik awal (koordinat device)
        count: Jumlah tower yang ingin di-generate
        min_dist: Jarak minimum tower (meter)
        max_dist: Jarak maksimum tower (meter)

    Returns:
        List dictionary dengan keys: cellular_tower_id, cellular_tower_name,
        latitude, longitude
    """
    locations = []
    for i in range(count):
        # Pilih arah berdasarkan index (rotasi jika count > DIRECTIONS)
        angle = DIRECTIONS[i % len(DIRECTIONS)]

        # Hitung jarak random di antara min dan max
        dist = min_dist + (max_dist - min_dist) * (i * 0.37 % 1.0)

        # Hitung koordinat baru
        lat, lon = latlon_offset(start_lat, start_lon, angle, dist)

        locations.append({
            "cellular_tower_id": f"TWR-{i+1:03d}",  # Contoh: TWR-001
            "cellular_tower_name": f"Tower-{i+1}",   # Contoh: Tower-1
            "latitude": round(lat, 6),               # Presisi 6 desimal
            "longitude": round(lon, 6),
        })

    return locations


# ============================================================================
# FUNGSI API - INTERAKSI DENGAN BACKEND
# ============================================================================

def create_mission(name: str, description: str = "") -> int:
    """
    Membuat mission baru via API.

    Args:
        name: Nama mission
        description: Deskripsi mission

    Returns:
        Mission ID yang dibuat
    """
    log(f"Membuat mission: {name}")
    resp = requests.post(f"{API_BASE}/api/v1/missions", json={
        "name": name,
        "description": description,
        "radius_meters": 20,  # Radius geofence 20 meter
    })
    resp.raise_for_status()
    data = resp.json()
    mission_id = data["id"]
    log(f"Mission dibuat: id={mission_id}, status={data['status']}")
    return mission_id


def upload_locations(mission_id: int, locations: list[dict]):
    """
    Upload lokasi tower ke backend dalam format CSV.

    Args:
        mission_id: ID mission tujuan
        locations: List dictionary lokasi tower
    """
    log(f"Mengupload {len(locations)} lokasi untuk mission {mission_id}")

    # Buat CSV content di memory
    csv_buf = StringIO()
    writer = csv.writer(csv_buf)
    writer.writerow(["cellular_tower_id", "cellular_tower_name", "latitude", "longitude"])
    for loc in locations:
        writer.writerow([
            loc["cellular_tower_id"],
            loc["cellular_tower_name"],
            loc["latitude"],
            loc["longitude"]
        ])
    csv_content = csv_buf.getvalue()

    # Simpan ke file sementara
    csv_file = f"/tmp/mission_{mission_id}_locations.csv"
    with open(csv_file, "w") as f:
        f.write(csv_content)
    log(f"CSV disimpan di {csv_file}")

    # Upload via API
    with open(csv_file, "rb") as f:
        resp = requests.post(
            f"{API_BASE}/api/v1/missions/{mission_id}/locations/upload",
            files={"file": ("locations.csv", f, "text/csv")}
        )
    resp.raise_for_status()
    result = resp.json()
    log(f"Upload result: {result}")


def plan_mission(mission_id: int) -> dict:
    """
    Menjalankan route planning untuk optimasi urutan kunjungan tower.

    Args:
        mission_id: ID mission yang akan di-plan

    Returns:
        Response dari API planning
    """
    log(f"Merencanakan route untuk mission {mission_id}")
    resp = requests.post(f"{API_BASE}/api/v1/missions/{mission_id}/plan")
    resp.raise_for_status()
    data = resp.json()
    log(f"Route direncanakan: {len(data.get('route', []))} waypoints")
    return data


def start_mission(mission_id: int) -> dict:
    """
    Menjalankan mission yang sudah di-plan.

    Args:
        mission_id: ID mission yang akan dijalankan

    Returns:
        Response dari API start
    """
    log(f"Menjalankan mission {mission_id}")
    resp = requests.post(f"{API_BASE}/api/v1/missions/{mission_id}/start")
    resp.raise_for_status()
    data = resp.json()
    log(f"Mission dimulai: status={data['status']}")
    return data


def stop_mission(mission_id: int):
    """
    Menghentikan mission yang sedang berjalan.

    Args:
        mission_id: ID mission yang akan dihentikan
    """
    log(f"Menghentikan mission {mission_id}")
    requests.post(f"{API_BASE}/api/v1/missions/{mission_id}/stop")


def get_mission_status(mission_id: int) -> dict:
    """
    Mengambil status terkini mission.

    Args:
        mission_id: ID mission yang akan dicek

    Returns:
        Dictionary status mission
    """
    resp = requests.get(f"{API_BASE}/api/v1/missions/{mission_id}")
    resp.raise_for_status()
    return resp.json()


def monitor_mission(mission_id: int, interval: int = MONITOR_INTERVAL,
                    max_duration: int = MAX_MISSION_DURATION):
    """
    Memantau progress mission secara berkala.

    Args:
        mission_id: ID mission yang dimonitor
        interval: Interval pengecekan dalam detik
        max_duration: Timeout maksimum monitoring dalam detik
    """
    log(f"Memantau mission {mission_id} (maks {max_duration}s)")
    start_time = time.time()

    while time.time() - start_time < max_duration:
        try:
            # Ambil status mission
            status = get_mission_status(mission_id)
            s = status.get("status", "?")
            visited = status.get("visited_locations", 0)
            total = status.get("total_locations", 0)
            progress = status.get("progress_percent", 0)

            # Ambil log terakhir
            try:
                logs_resp = requests.get(f"{API_BASE}/api/v1/missions/{mission_id}/logs")
                logs = logs_resp.json()
                latest_log = logs[-1]["message"] if isinstance(logs, list) and logs else "none"
            except:
                latest_log = "none"

            # Ambil jumlah scan
            try:
                scans_resp = requests.get(f"{API_BASE}/api/v1/missions/{mission_id}/scans?page=1&page_size=1")
                scans = scans_resp.json()
                scan_count = scans.get("total", 0)
            except:
                scan_count = 0

            elapsed = int(time.time() - start_time)
            log(f"[{elapsed}s] status={s} visited={visited}/{total} ({progress}%) scans={scan_count} | {latest_log}")

            # Berhenti jika mission selesai
            if s in ("COMPLETED", "FAILED", "STOPPED"):
                log(f"Mission berakhir: status={s}")
                break

        except Exception as e:
            log(f"Error monitoring: {e}")

        time.sleep(interval)


# ============================================================================
# FUNGSI KONFIGURASI GPS
# ============================================================================

def set_gps_provider(provider_type: str):
    """
    Mengupdate konfigurasi GPS provider di file .env.

    Args:
        provider_type: Tipe provider ("cli", "mock", "moving_mock", "serial")
    """
    log(f"Mengatur GPS provider ke: {provider_type}")

    env_path = Path(ENV_FILE)
    lines = env_path.read_text().splitlines()

    new_lines = []
    for line in lines:
        if line.startswith("GPS_PROVIDER="):
            new_lines.append(f"GPS_PROVIDER={provider_type}")
        elif line.startswith("MOCK_GPS_SPEED_MS=") and provider_type == "moving_mock":
            new_lines.append("MOCK_GPS_SPEED_MS=50")  # Default 50 m/s
        else:
            new_lines.append(line)

    env_path.write_text("\n".join(new_lines) + "\n")
    log(f"Konfigurasi GPS diupdate di {ENV_FILE}")


def build_waypoints_string(locations: list[dict]) -> str:
    """
    Mengubah list lokasi menjadi string waypoints untuk MOCK_GPS_WAYPOINTS.

    Format: "lat,lon:lat,lon:..."

    Args:
        locations: List dictionary lokasi tower

    Returns:
        String waypoints
    """
    return ":".join(f"{loc['latitude']},{loc['longitude']}" for loc in locations)


def update_waypoints_in_env(waypoints_str: str):
    """
    Mengupdate MOCK_GPS_WAYPOINTS di file .env.

    Args:
        waypoints_str: String waypoints yang sudah di-build
    """
    env_path = Path(ENV_FILE)
    lines = env_path.read_text().splitlines()
    new_lines = []
    for line in lines:
        if line.startswith("MOCK_GPS_WAYPOINTS="):
            new_lines.append(f"MOCK_GPS_WAYPOINTS={waypoints_str}")
        else:
            new_lines.append(line)
    env_path.write_text("\n".join(new_lines) + "\n")
    log("MOCK_GPS_WAYPOINTS diupdate di .env")


def restart_backend():
    """
    Merestart backend service untuk apply perubahan konfigurasi .env.
    """
    log("Merestart backend...")

    # Hentikan process uvicorn yang sedang berjalan
    subprocess.run(["pkill", "-f", "uvicorn app.main"], capture_output=True)
    time.sleep(2)

    # Start backend baru di background
    subprocess.Popen(
        ["bash", "-c", f"cd {BACKEND_DIR} && source .venv/bin/activate && nohup .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8001 > /tmp/backend.log 2>&1 &"],
        stdout=open("/dev/null", "w"),
        stderr=subprocess.STDOUT,
    )
    time.sleep(3)

    # Verifikasi restart berhasil
    try:
        resp = requests.get(f"{API_BASE}/health")
        if resp.status_code == 200:
            log("Backend berhasil direstart")
        else:
            log("PERINGATAN: Backend mungkin tidak restart dengan benar")
    except:
        log("PERINGATAN: Tidak bisa verifikasi restart backend")


# ============================================================================
# FUNGSI UTAMA - WORKFLOW MISSION
# ============================================================================

def run_mission(start_lat: float, start_lon: float, name: str = "AUTO-MISSION",
                count: int = 5, min_dist: int = 200, max_dist: int = 400):
    """
    Workflow utama untuk menjalankan mission otonom.

    Args:
        start_lat, start_lon: Koordinat awal device
        name: Nama mission
        count: Jumlah tower
        min_dist: Jarak minimum tower (meter)
        max_dist: Jarak maksimum tower (meter)

    Returns:
        Mission ID jika berhasil, None jika gagal
    """
    mission_id = None

    try:
        # =========================================================================
        # STEP 1: Generate lokasi tower
        # =========================================================================
        log("Menghasilkan lokasi tower...")
        locations = generate_tower_locations(start_lat, start_lon, count, min_dist, max_dist)

        # Tampilkan detail setiap tower
        for i, loc in enumerate(locations):
            dist = haversine_m(start_lat, start_lon, loc["latitude"], loc["longitude"])
            log(f"  Tower {i+1}: {loc['cellular_tower_name']} di ({loc['latitude']}, {loc['longitude']}) - {dist:.0f}m dari start")

        # =========================================================================
        # STEP 2: Buat mission baru
        # =========================================================================
        mission_id = create_mission(name, f"Auto-generated mission dengan {count} tower")

        # =========================================================================
        # STEP 3: Upload lokasi ke backend
        # =========================================================================
        upload_locations(mission_id, locations)

        # =========================================================================
        # STEP 4: Plan route untuk optimasi urutan kunjungan
        # =========================================================================
        plan_mission(mission_id)

        # =========================================================================
        # STEP 5: Setup Mock GPS dan restart backend
        # =========================================================================
        # Build string waypoints dari lokasi tower
        waypoints_str = build_waypoints_string(locations)

        # Set provider ke moving_mock
        set_gps_provider("moving_mock")

        # Update waypoints di .env
        update_waypoints_in_env(waypoints_str)

        # Restart backend agar konfigurasi baru apply
        restart_backend()
        time.sleep(3)

        # =========================================================================
        # STEP 6: Mulai mission
        # =========================================================================
        start_mission(mission_id)

        # =========================================================================
        # STEP 7: Monitor progress
        # =========================================================================
        monitor_mission(mission_id, interval=MONITOR_INTERVAL, max_duration=MAX_MISSION_DURATION)

    except Exception as e:
        log(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # =========================================================================
        # STEP 8: Teardown - Hentikan mission dan revert GPS
        # =========================================================================
        if mission_id:
            stop_mission(mission_id)

        # Revert ke GPS real (CLI provider)
        set_gps_provider("cli")
        restart_backend()
        log("GPS dikembalikan ke provider real (/dev/ttyAMA0)")

    return mission_id


# ============================================================================
# ENTRY POINT
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="Autonomous Mission Script - Cellular Discovery")
    parser.add_argument("--lat", type=float, help="Override GPS latitude (opsional)")
    parser.add_argument("--lon", type=float, help="Override GPS longitude (opsional)")
    parser.add_argument("--name", default="AUTO-MISSION", help="Nama mission")
    parser.add_argument("--count", type=int, default=5, help="Jumlah tower (default: 5)")
    parser.add_argument("--min-dist", type=int, default=200, help="Jarak minimum tower meter (default: 200)")
    parser.add_argument("--max-dist", type=int, default=400, help="Jarak maksimum tower meter (default: 400)")
    args = parser.parse_args()

    log("="*60)
    log("Mission Autonomy Script")
    log("="*60)

    # Tentukan koordinat awal
    if args.lat and args.lon:
        # Gunakan override dari parameter
        start_lat, start_lon = args.lat, args.lon
        log(f"Menggunakan koordinat override: {start_lat}, {start_lon}")
    else:
        # Ambil dari GPS real
        start_lat, start_lon = get_real_gps_location()

    # Jalankan mission
    mission_id = run_mission(
        start_lat, start_lon,
        name=args.name,
        count=args.count,
        min_dist=args.min_dist,
        max_dist=args.max_dist
    )

    log("="*60)
    if mission_id:
        log(f"Mission selesai: id={mission_id}")
    else:
        log("Mission gagal")
    log("="*60)


if __name__ == "__main__":
    main()

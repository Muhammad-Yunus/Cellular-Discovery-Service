# Mission Autonomy Script

Script ini digunakan untuk menjalankan misi scanning seluler secara otomatis pada **Cellular-Discovery-Service**. Script ini menangani workflow lengkap dari deteksi GPS, penentuan lokasi tower, planning route, simulasi pergerakan (mock GPS), hingga monitoring progress misi.

## Konteks & Workflow

Script ini mendeteksi posisi GPS real dari device (`/dev/ttyAMA0`), kemudian:
1. Menghasilkan lokasi-lokasi tower pada jarak 200-400m dari posisi device
2. Membuat misi baru via API backend
3. Upload lokasi tower ke backend
4. Menjalankan route planning untuk optimasi urutan kunjungan
5. Mengaktifkan **Mock GPS (moving_mock)** dengan waypoints sesuai lokasi tower
6. Menjalankan misi dan memonitor progress
7. Setelah selesai, mengembalikan GPS ke provider real (CLI)

### Tahapan Detail

| Step | Deskripsi |
|------|-----------|
| **STEP 1** | Generate lokasi tower di sekitar posisi device (5 arah kompas: 0°, 72°, 144°, 216°, 288°) |
| **STEP 1.5** | Validasi jarak device ke tower terdekat (harus ≤ 3km) |
| **STEP 1.6** | Update `MOCK_GPS_START_LAT/LON` di `.env` ke posisi GPS real |
| **STEP 2** | Buat mission baru via API (`POST /api/v1/missions`) |
| **STEP 3** | Upload lokasi tower dalam format CSV ke backend |
| **STEP 4** | Plan route untuk optimasi urutan kunjungan (TSP solver) |
| **STEP 5** | Setup Mock GPS (moving_mock) dan restart backend |
| **STEP 6** | Mulai misi (`POST /api/v1/missions/{id}/start`) |
| **STEP 7** | Monitor progress setiap 5 detik |
| **STEP 8** | Teardown: stop misi dan revert GPS ke CLI provider |

### GPS Retry Logic

Saat startup, script akan mencoba membaca GPS real dengan **retry logic**:
- Maksimal **5x percobaan** dengan **interval 3 detik** antar retry
- Jika semua attempt gagal, fallback ke koordinat `MOCK_GPS_START_LAT/LON` di `.env`
- Output setiap attempt akan ditampilkan:
  ```
  [HH:MM:SS]   Attempt 1/5...
  [HH:MM:SS]   ⚠️ Attempt 1 gagal: Tidak ada GPS fix
  [HH:MM:SS]   Menunggu 3s sebelum retry...
  ```

## Cara Penggunaan

### Persyaratan

- Backend service berjalan di `http://localhost:8001`
- GPS hardware terhubung ke `/dev/ttyAMA0` (serial)
- Python 3.13+ dengan dependencies terinstall
- Akses sudo untuk restart service systemd

### Mode 1: GPS Real (Default)

```bash
cd /home/pi/Cellular-Discovery-Service/scripts
python3 run_mission.py --name TEST-001
```

Script akan otomatis mendeteksi GPS real dari `/dev/ttyAMA0`.

### Mode 2: Koordinat Override (Tanpa GPS)

```bash
python3 run_mission.py --name TEST-002 --lat -6.175 --lon 106.827
```

### Mode 3: Custom Parameters

```bash
python3 run_mission.py --name TEST-003 --count 10 --min-dist 100 --max-dist 500 --speed 30
```

### Parameter Lengkap

| Parameter | Tipe | Default | Deskripsi |
|-----------|------|---------|-----------|
| `--lat` | float | Auto | Override latitude GPS |
| `--lon` | float | Auto | Override longitude GPS |
| `--name` | str | "AUTO-MISSION" | Nama misi |
| `--count` | int | 5 | Jumlah tower yang di-generate |
| `--min-dist` | int | 200 | Jarak minimum tower (meter) |
| `--max-dist` | int | 400 | Jarak maksimum tower (meter) |
| `--speed` | float | 50.0 | Mock GPS cruise speed (m/s) |

## Konfigurasi

File konfigurasi utama: `/home/pi/Cellular-Discovery-Service/backend/.env`

### Parameter yang Diatur Script

| Environment Variable | Deskripsi |
|---------------------|-----------|
| `GPS_PROVIDER` | Tipe provider GPS (`cli`, `mock`, `moving_mock`, `serial`) |
| `MOCK_GPS_START_LAT` | Latitude awal mock GPS |
| `MOCK_GPS_START_LON` | Longitude awal mock GPS |
| `MOCK_GPS_WAYPOINTS` | Rute waypoints (format: `lat,lon:lat,lon:...`) |
| `MOCK_GPS_SPEED_MS` | Kecepatan巡航 mock GPS (m/s) |
| `MOCK_GPS_LOITER_RADIUS_M` | Radius loiter di setiap waypoint |
| `MOCK_GPS_LOITER_LAPS` | Jumlah lap loiter |

### Arah Kompas untuk Tower

Tower di-generate pada 5 arah kompas:
- 0° = Utara
- 72° = Timur Laut
- 144° = Selatan
- 216° = Barat Daya
- 288° = Barat Laut

## Common Issues & Troubleshooting

### 1. GPS Fix Gagal / No GPS Signal

**Gejala:**
```
ERROR mendapatkan GPS: Tidak ada GPS fix
Fallback ke MOCK_GPS_START_LAT/LON dari .env
```

**Penyebab:**
- GPS hardware tidak terhubung
- Baud rate tidak sesuai
- Satellite fix belum stabil

**Solusi:**
```bash
# Cek koneksi GPS hardware
sudo systemctl status lte-scanner

# Test GPS CLI secara manual
/home/pi/GPS/build/gps -d /dev/ttyAMA0 -b 9600 -w -j -c 5

# Jika gagal, cek permissions
sudo chmod 666 /dev/ttyAMA0

# Atau gunakan koordinat override
python3 run_mission.py --lat -6.175 --lon 106.827
```

### 2. Tower Terlalu Jauh (> 3km)

**Gejala:**
```
ERROR: Tower terdekat terlalu jauh (8344m > 3000m)
Abort mission!
```

**Penyebab:**
- Koordinat start di `.env` tidak sinkron dengan GPS real
- Backend belum di-restart setelah perubahan konfigurasi

**Solusi:**
```bash
# Verifikasi posisi GPS real saat ini
curl -s http://localhost:8001/api/v1/device/location | jq '.'

# Pastikan .env memiliki koordinat yang benar
grep MOCK_GPS_START backend/.env

# Restart backend untuk apply perubahan
sudo systemctl restart lte-scanner

# Jalankan ulang dengan GPS real
python3 run_mission.py --name TEST-FIX
```

### 3. Mock GPS Tidak Bergerak

**Gejala:**
- Mission berjalan tapi posisi device tidak berubah
- Log menunjukkan `status=IDLE` terus-menerus

**Penyebab:**
- Provider GPS masih set ke `cli` (bukan `moving_mock`)
- Backend belum di-restart setelah perubahan `.env`

**Solusi:**
```bash
# Cek provider saat ini
curl -s http://localhost:8001/api/v1/device/location | jq '.provider'

# Pastikan MOCK_GPS_WAYPOINTS di-set
grep MOCK_GPS_WAYPOINTS backend/.env

# Restart backend
sudo systemctl restart lte-scanner

# Verifikasi mock GPS bergerak
curl -s http://localhost:8001/api/v1/device/location | jq '.'
```

### 4. Backend Tidak Bisa Direstart (Port Occupied)

**Gejala:**
```
PERINGATAN: Backend mungkin tidak restart dengan benar
```

**Penyebab:**
- Port 8001 masih digunakan proses lama
- Zombie process belum terminate

**Solusi:**
```bash
# Cari dan kill process di port 8001
sudo fuser -k 8001/tcp

# Tunggu sebentar lalu restart manual
sleep 2
sudo systemctl restart lte-scanner

# Verifikasi
curl -s http://localhost:8001/health
```

### 5. Mission Gagal di Tengah Jalan (SCAN_ERROR)

**Gejala:**
```
mission_skipped reason=SCAN_ERROR
```

**Penyebab:**
- Scan CLI timeout
- GPS location tidak valid saat visit
- Target terlalu jauh dari radius geofence

**Solusi:**
```bash
# Cek log mission
curl -s "http://localhost:8001/api/v1/missions/{ID}/logs" | jq '.[-20:]'

# Cek status GPS device
curl -s http://localhost:8001/api/v1/device/location | jq '.'

# Pastikan mock GPS bergerak dan valid
journalctl -u lte-scanner -f | grep "Device location"
```

### 6. GPS CLI Command Gagal

**Gejala:**
```
INFO:Calling GPS CLI: /home/pi/GPS/build/gps -d /dev/ttyAMA0 -b 9600 -w -j -c 15 | jq ...
```

**Solusi:**
```bash
# Test GPS CLI secara manual
/home/pi/GPS/build/gps -d /dev/ttyAMA0 -b 9600 -w -j -c 5

# Cek GPS device ada
ls -la /dev/ttyAMA0

# Jika tidak ada, cek serial port configuration
dmesg | grep ttyAMA
```

## Monitoring & Debugging

### Cek Status Backend

```bash
# Health check
curl -s http://localhost:8001/health

# Device location saat ini
curl -s http://localhost:8001/api/v1/device/location | jq '.'

# List semua mission
curl -s http://localhost:8001/api/v1/missions | jq '.[] | {id, name, status}'
```

### Cek Log Mission

```bash
# Log mission tertentu
curl -s "http://localhost:8001/api/v1/missions/{ID}/logs" | jq '.'

# Scan history
curl -s "http://localhost:8001/api/v1/missions/{ID}/scans?page=1&page_size=10" | jq '.'
```

### Monitor System Logs

```bash
# Live tail backend logs
journalctl -u lte-scanner -f

# Filter GPS-related logs
journalctl -u lte-scanner | grep -i "gps\|location\|tower"
```

### Debug Mock GPS

```bash
# Cek konfigurasi GPS di .env
grep -E "^GPS_PROVIDER|^MOCK_GPS" /home/pi/Cellular-Discovery-Service/backend/.env

# Test mock GPS provider secara manual
cd backend && source .venv/bin/activate
python3 -c "
from app.gps.moving_mock_provider import MovingMockGPSProvider
import time
provider = MovingMockGPSProvider(
    start_lat=-6.1507, start_lon=106.8967,
    waypoints=[(-6.1462, 106.8967), (-6.1488, 106.9026), (-6.1571, 106.9013)],
    cruise_speed_ms=20.0
)
for i in range(10):
    loc = provider.get_location()
    print(f'{i*5}s: lat={loc.latitude:.6f}, lon={loc.longitude:.6f}')
    time.sleep(1)
"
```

## Struktur File

```
scripts/
├── run_mission.py          # Main script untuk autonomous mission
└── README.md              # Dokumentasi ini
```

## Dependensi

Python packages:
- `requests` - HTTP client
- `pathlib` - File path manipulation (stdlib)
- `json` - JSON parsing (stdlib)
- `math` - Haversine formula (stdlib)

External tools:
- `jq` - Command-line JSON processor (untuk parsing GPS output)
- `/home/pi/GPS/build/gps` - GPS CLI tool untuk hardware serial

System services:
- `lte-scanner.service` - Backend FastAPI service (systemd)

## Catatan Penting

1. **Koordinat harus sinkron**: Pastikan `MOCK_GPS_START_LAT/LON` di `.env` sesuai dengan posisi GPS real saat script dijalankan

2. **Validasi jarak otomatis**: Script akan abort jika tower terdekat > 3km dari posisi device

3. **GPS fallback**: Jika GPS real gagal, script akan fallback ke koordinat di `.env`

4. **Auto-revert**: Setelah mission selesai, GPS akan otomatis dikembalikan ke provider CLI (real hardware)

5. **Timezone**: Semua timestamp menggunakan UTC (+07:00 untuk Indonesia)

## License

Internal use only - Cellular Discovery Service Project

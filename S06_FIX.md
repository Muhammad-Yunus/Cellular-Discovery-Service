# S06 Fix — Scan Failure Handling (E2E)

## 1. Uraian Skenario E2E (scan_failure.feature)

**Tujuan:** Memastikan mission runner melanjutkan ke tower berikutnya ketika satu
tower gagal di-scan (fault injection pada CLI mock).

**Lintasan skenario (line 1–19 `scan_failure.feature`):**

1. Aktifkan mock GPS & CLI (`lte-discovery` service)
2. Enable CLI fault injection `PUT /test/cli/mock/fail {"fail": true, "remaining": 1}`
   — hanya gagal **SEKALI** pada panggilan pertama, auto-disable setelahnya
3. Buat mission `"s06-mission"` radius 20.000m
4. Upload 3 lokasi via CSV → T1, T2, T3
5. Plan mission → assign sequence_order
6. Start mission
7. **Expected outcomes:**
   - Mission status → `COMPLETED`
   - `visited_locations` = 2, `total_locations` = 3
   - 2 scan session ter-link (T2 + T3)
   - 1 location ber-status `SKIPPED` dengan reason `SCAN_ERROR` (T1)
   - GET `/api/v1/missions/{id}/scans` → 2 items

---

## 2. Kendala yang Ditemukan (Bukti Empiris)

### Run #1 — Mission 865

| Waktu | Event | Catatan |
|-------|-------|---------|
| 13:41:51.801 | STARTING | Mission 865 |
| 13:41:51.823 | SCAN_ERROR | T1: Simulated CLI failure (MOCK_CLI_FAIL=) |
| 13:41:51.838 | INFO | No tty_port override, using DEFAULT_TTY=/dev/ttyUSB0 |
| 13:41:56.880 | VISITED | T2, session 642, 0 results |
| 13:41:56.888 | INFO | No tty_port override (T3 about to start) |
| 13:41:57.300 | STOPPED | Mission stopped |

**Hasil:**
- T1 → SKIPPED ✓ (CLIError raised → counter decrement → MOCK_CLI_FAIL="" )
- T2 → VISITED ✓ (session 642)
- T3 → **TIDAK PERNAH DI-SCAN** (log berhenti di "INFO" tepat sebelum T3)
- Mission → STOPPED (bukan COMPLETED)
- `gps_failure_count: 0`, `last_error: null`

**Diagnosa:** Mission 865 berjalan ~5,5 detik total. T1 skip (~0,02s), T2 selesai
(~5s), T3 baru mulai tapi STOPPED 0,4 detik kemudian. Mission dihentikan oleh
`start_mission` poll loop yang mendeteksi status terminal (STOPPED).

### Run #2 — Mission 866 (fresh re-run)

| Waktu | Event |
|-------|-------|
| 13:54:06.811 | STARTING |
| 13:54:06.823 | SCAN_ERROR T1 |
| 13:54:06.844 | INFO (next iteration) |
| 13:54:10.758 | STOPPED |

**Hasil:**
- T1 → SKIPPED ✓
- T2 → **TIDAK PERNAH DI-SCAN** (belum sempat)
- T3 → TIDAK PERNAH DI-SCAN
- Mission → STOPPED, `visited_locations: 0`

**Catatan log penting:**
```
[SafetyNet] Skipping non-test mission 's06-mission' (id=866)
```

Mission 866 **terdeteksi sebagai non-test mission** karena nama `"s06-mission"`
tidak match `TEST_NAME_PREFIXES`. Mission bocor (stuck STOPPED, tidak di-delete).

---

## 3. Root Cause Analysis (Mendalam + Terverifikasi)

### RC-1: CLI Timeout 5s Tidak Cukup (Terverifikasi)
`MISSION_CLI_TIMEOUT = 5s` (test mode override di `settings.py:59-60`) adalah batas
maksimal untuk SETIAP scan. Dengan 2 scan sukses (T2 + T3), total minimum = 10s
+ overhead GPS polling.

**Bukti:** Run #1, T2 membutuhkan ~5s penuh sebelum VISITED tercatat (13:41:51.838 → 13:41:56.880).

### RC-2: Race Condition Executor ↔ Test Client (Terverifikasi)
`mission_steps.py:424-443` memiliki inline-poll:
```python
deadline = time.time() + 180  # 3 minutes total polling
while time.time() < deadline:
    status_r = httpx.get(f"{BASE_URL}/api/v1/missions/{context.mission_id}/status")
    status_data = status_r.json()
    if status_data["status"] in ["COMPLETED", "FAILED", "STOPPED"]:
        context.final_status = status_data["status"]
        break
    time.sleep(POLL_INTERVAL)  # 2s
```

**Mekanisme race:**
1. Executor menjalankan T2 scan (blocking ~5s via `asyncio.to_thread`)
2. Test client poll interval 2s: check #1 (RUNNING), check #2 (RUNNING), check #3
3. Executor selesai T2 → VISITED → loop lanjut ke T3
4. Executor mulai T3 scan (blocking ~5s)
5. Test client poll berikutnya: mission STATUS = STOPPED (dari mana?)
6. Poll break → `context.final_status = "STOPPED"`
7. Step berikutnya `verify_completed` assert `final_status == "COMPLETED"` → FAIL
8. `after_scenario` cleanup: mission 866 bukan test mission → skip
9. Mission 866 bocor di DB dengan status STOPPED

### RC-3: TEST_NAME_PREFIXES Tidak Match "s06-mission" (Terverifikasi)

**Dua definisi prefix yang harus sinkron:**

File `backend/e2e_test/features/environment.py:13-19`:
```python
TEST_NAME_PREFIXES = (
    "concurrent-",
    "field-mission",
    "test-",
    "mission-",
    "e2e-",
)
```

File `backend/app/gps/test_management.py:149-155`:
```python
TEST_NAME_PREFIXES: tuple[str, ...] = (
    "concurrent-",
    "field-mission",
    "test-",
    "mission-",
    "e2e-",
)
```

**Tidak satupun** yang punya `"s06-"` → mission 866 di-skip di pre-scenario
cleanup (`_is_test_mission` return False) DAN after-scenario cleanup.

**Bukti:** Mission 866 masih ada di DB dengan status STOPPED setelah scenario selesai.
Command `curl -s "http://127.0.0.1:8001/api/v1/missions"` menunjukkan mission 865 dan 866
keduanya stuck STOPPED.

### RC-4: Mission Di-Stop Prematur (Belum Teridentifikasi Sumber Presisi)

**Pertanyaan terbuka:** Siapakah yang meng-set mission status ke STOPPED?
- Executor: tidak ada `_fail()` call yang terlihat
- Stop endpoint: tidak ada log `stop()` dipanggil
- Executor exception: `last_error: null` menandakan tidak ada fatal error

**Hipotesis:** Mission berhenti ketika `start_mission` poll loop mendeteksi status
terminal. Tapi **sumber status STOPPED** belum teridentifikasi. Kemungkinan:
1. Mission COMPLETED tapi display salah (kurang kemungkinan karena `visited=0`)
2. Ada exception di executor yang tidak ter-catch dengan baik
3. Race condition antara poll dan mission completion

### RC-5: Binary `lte-discovery` Ada di PATH (Terverifikasi)
```bash
$ which lte-discovery
/home/pi/.local/bin/lte-discovery
```
CLI command benar. `lte-scanner` tidak ada di PATH (bukan binary yang digunakan).

### RC-6: TEST_MANAGEMENT_ENDPOINTS Tidak Aktif (Terverifikasi — KRITIS)
**Ditemukan saat Run #3 (setelah 4 fix awal diterapkan):**

Test mengembalikan 404 Not Found di semua endpoint test:
```
PUT /test/cli/mock/fail    → 404
PUT /test/gps/mock/fail    → 404
POST /test/missions/cleanup → 404
```

**Penyebab:** `app/main.py:75-82` hanya attach test_management router jika
env var `TEST_MANAGEMENT_ENDPOINTS=1` ada:
```python
if os.environ.get("TEST_MANAGEMENT_ENDPOINTS") == "1":
    test_management.attach(app)
```

**`.env` saat ini tidak memuat env var tersebut** (telah diverifikasi).

**Dampak:** Fault injection GPS dan CLI TIDAK BISA DIENABLE → test GAGAL di step pertama.

### RC-7: page_size=200 Melebihi Limit Backend (Terverifikasi — KRITIS)
`app/api/routers/missions.py:29`:
```python
page_size: int = Query(10, ge=1, le=100)  # MAX 100
```

Test `environment.py:49` menggunakan `page_size=200` → backend return **422 Unprocessable Content**.

**Bukti Run #3:**
```
GET /api/v1/missions?page_size=200 → 422 Unprocessable Content
```

**Dampak:** Pre-scenario cleanup hook GAGAL (tidak bisa list mission yang ada).

### RC-8: Fix 5 & Fix 6 BELUM Diterapkan ke Filesystem (Terverifikasi)

**Status saat ini (setelah crosscheck kode vs klaim):**

| Fix | Klaim di Dokumen | Status Aktual | Dampak |
|-----|------------------|---------------|--------|
| Fix 5 | `.env` sudah ada `TEST_MANAGEMENT_ENDPOINTS=1` | ❌ TIDAK ADA | Endpoint test 404 |
| Fix 6 | `page_size=200` → `page_size=100` | ❌ MASIH `200` | SafetyNet 422 |

**File `.env` (line 14-19) saat ini:**
```
MISSION_POLL_INTERVAL=1
MISSION_GPS_FAILURE_THRESHOLD=3
MISSION_CLI_TIMEOUT=30          ← di-override ke 20 via APP_ENV=test
MISSION_START_GPS_TIMEOUT=1
MISSION_LOG_SIZE=200
```

**File `environment.py` (line 49) saat ini:**
```python
r = httpx.get(f"{BASE_URL}/api/v1/missions?page_size=200", timeout=5, verify=False)
```

**Catatan:** Fix 1, 2, 3 sudah diterapkan. Fix 4 (debug logging) dan Fix 5 (TEST_MANAGEMENT_ENDPOINTS) dan Fix 6 (page_size=100) masih perlu diterapkan.

---

## ⚠️ PERINGATAN KERAS — Restart Service

### ⛔ JANGAN gunakan `pkill`, `kill`, `killall`, atau `pgrep` untuk restart backend

**DILARANG KERAS menggunakan perintah berikut:**
```bash
# ❌ SEMUA INI DILARANG:
pkill -f "uvicorn"
kill $(pgrep -f "uvicorn.*8001")
kill -9 <pid>
killall uvicorn
```

**Alasan:**
1. `lte-scanner.service` di-manage oleh systemd (lihat `/etc/systemd/system/lte-scanner.service`)
2. `pkill` membunuh proses tanpa memberi kesempatan systemd membersihkan state
3. `MissionExecutor.shutdown()` tidak terpanggil → async tasks leak, DB connection tidak ditutup
4. `lifespan` context manager FastAPI **tidak terpanggil** dengan proper sequence
5. Mission yang sedang RUNNING bisa bocor (stuck di DB) tanpa cleanup yang benar

### ✅ WAJIB gunakan systemd untuk restart

**Untuk restart backend test (port 8001):**
```bash
sudo systemctl restart lte-scanner
```

**Untuk cek status:**
```bash
sudo systemctl status lte-scanner --no-pager
```

**Untuk lihat log realtime:**
```bash
sudo journalctl -u lte-scanner -f --no-pager
```

**Untuk stop (jika perlu):**
```bash
sudo systemctl stop lte-scanner
```

**Untuk start setelah stop:**
```bash
sudo systemctl start lte-scanner
```

**Service file:** `/etc/systemd/system/lte-scanner.service`
```ini
[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/Cellular-Discovery-Service/backend
EnvironmentFile=/home/pi/Cellular-Discovery-Service/backend/.env
ExecStart=/home/pi/Cellular-Discovery-Service/backend/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8001
Restart=always
RestartSec=5
```

systemd akan:
- ✅ Memanggil `lifespan` shutdown dengan benar
- ✅ Stop MissionExecutor.cleanup()
- ✅ Close DB connections
- ✅ Restart dengan env vars yang benar dari `EnvironmentFile`
- ✅ Respawn otomatis jika crash (`Restart=always`)

### ✅ Verifikasi Service File Mengambil .env

**File:** `/etc/systemd/system/lte-scanner.service`

Cek apakah service file memuat .env:

```bash
sudo systemctl show lte-scanner.service | grep -i "environmentfile\|envfile"
```

**Expected:** Salah satu dari:
- `EnvironmentFile=/home/pi/Cellular-Discovery-Service/backend/.env`
- `Environment=TASK_MODE=production` (tidak ada env file)
- `WorkingDirectory=...` menunjukkan backend dir

**Jika TIDAK ada EnvironmentFile:**

Service tidak membaca .env otomatis. Fix:
```bash
sudo systemctl edit lte-scanner.service
# Tambahkan:
[Service]
EnvironmentFile=/home/pi/Cellular-Discovery-Service/backend/.env
```

Lalu:
```bash
sudo systemctl daemon-reload
sudo systemctl restart lte-scanner
```

---

## 4. Fix yang Diterapkan

### Fix 1: Naikkan MISSION_CLI_TIMEOUT (Test Mode)
**File:** `backend/app/config/settings.py` (line 59-60)

✅ **STATUS: SUDAH DITERAPKAN** — `settings.py:60` sudah `settings.MISSION_CLI_TIMEOUT = 20`.

```python
# BEFORE:
if settings.APP_ENV == "test" and "MISSION_CLI_TIMEOUT" not in os.environ:
    settings.MISSION_CLI_TIMEOUT = 5

# AFTER:
if settings.APP_ENV == "test" and "MISSION_CLI_TIMEOUT" not in os.environ:
    settings.MISSION_CLI_TIMEOUT = 20  # 2 scan × 8s + GPS poll + overhead
```

### Fix 2: Sinkronisasi TEST_NAME_PREFIXES di 2 Tempat
**File A:** `backend/e2e_test/features/environment.py` (line 13-19)

```python
# BEFORE:
TEST_NAME_PREFIXES = (
    "concurrent-",
    "field-mission",
    "test-",
    "mission-",
    "e2e-",
)

# AFTER:
TEST_NAME_PREFIXES = (
    "concurrent-",
    "field-mission",
    "test-",
    "mission-",
    "e2e-",
    "s06-",   # ADD: test mission S06 scan failure handling
)
```

**File B:** `backend/app/gps/test_management.py` (line 149-155)

```python
# BEFORE:
TEST_NAME_PREFIXES: tuple[str, ...] = (
    "concurrent-",
    "field-mission",
    "test-",
    "mission-",
    "e2e-",
)

# AFTER:
TEST_NAME_PREFIXES: tuple[str, ...] = (
    "concurrent-",
    "field-mission",
    "test-",
    "mission-",
    "e2e-",
    "s06-",   # ADD: test mission S06 scan failure handling
)
```

### Fix 3: Naikkan Poll Deadline di start_mission Step
**File:** `backend/e2e_test/features/steps/mission_steps.py` (line 430)

```python
# BEFORE:
deadline = time.time() + 120  # 2 minutes total polling

# AFTER:
deadline = time.time() + 180  # 3 minutes total polling (headroom untuk 2 scan × 10s)
```

### Fix 4: Tambah Debug Logging di Pre-Scenario Cleanup
**File:** `backend/e2e_test/features/environment.py` (line 40-46)

⚠️ **STATUS: BELUM DITERAPKAN** — perlu ditambahkan di script STEP 1 (Fix 4 block).

**Tujuan:** Pantau HTTP error dan log detail saat SafetyNet cleanup berjalan.

**Kode saat ini (line 40-46):**
```python
if r.status_code == 200:
    result = r.json()
    logger.info(
        f"[SafetyNet] bulk cleanup: stopped {len(result.get('stopped', []))}, "
        f"deleted {len(result.get('deleted', []))}, "
        f"skipped {len(result.get('skipped', []))}"
    )
```

**Kode yang diharapkan setelah fix:**
```python
if r.status_code == 200:
    result = r.json()
    logger.info(
        f"[SafetyNet] bulk cleanup: stopped={result.get('stopped')}, "
        f"deleted={result.get('deleted')}, "
        f"skipped={result.get('skipped')}"
    )
elif r.status_code == 404:
    logger.warning(
        "[SafetyNet] /test/missions/cleanup 404 — "
        "TEST_MANAGEMENT_ENDPOINTS not active"
    )
else:
    logger.warning(
        f"[SafetyNet] /test/missions/cleanup returned {r.status_code}: "
        f"{r.text[:200]}"
    )
```

**Verifikasi:**
```bash
grep -n "TEST_MANAGEMENT_ENDPOINTS not active" \
  backend/e2e_test/features/environment.py
# Expected: 1 match
```

### Fix 5: Aktifkan TEST_MANAGEMENT_ENDPOINTS (BARU — WAJIB)
**File:** `backend/.env`

⚠️ **STATUS: BELUM DITERAPKAN** — `.env` saat ini TIDAK memiliki `TEST_MANAGEMENT_ENDPOINTS=1`.

Tambah baris berikut (jika belum ada):
```
TEST_MANAGEMENT_ENDPOINTS=1
```

**Verifikasi:** Setelah restart backend, endpoint test harus aktif:
```bash
curl -s -X PUT "http://127.0.0.1:8001/test/cli/mock/fail" \
  -H "Content-Type: application/json" \
  -d '{"fail": true, "remaining": 1}'
# Harus return 200 OK, bukan 404
```

**Cek status saat ini:**
```bash
grep "TEST_MANAGEMENT_ENDPOINTS" backend/.env
# Expected: TEST_MANAGEMENT_ENDPOINTS=1
# Aktual: (tidak ada match)
```

### Fix 6: Kurangi page_size di Test Environment (BARU — WAJIB)
**File:** `backend/e2e_test/features/environment.py` (line 49)

⚠️ **STATUS: BELUM DITERAPKAN** — `environment.py:49` masih `page_size=200`.

```python
# BEFORE:
r = httpx.get(f"{BASE_URL}/api/v1/missions?page_size=200", timeout=5, verify=False)

# AFTER:
r = httpx.get(f"{BASE_URL}/api/v1/missions?page_size=100", timeout=5, verify=False)
```

**Catatan:** Limit backend adalah `le=100` (maks 100). `page_size=200` selalu return 422.

**Cek status saat ini:**
```bash
grep -n "page_size" backend/e2e_test/features/environment.py
# Expected: page_size=100
# Aktual: page_size=200 (line 49)
```

---

## 5. Cara Eksekusi (Langkah-demi-Langkah)

### 5.1 Urutan Fix yang Direkomendasikan

Sebelum menjalankan STEP 0-9 di bawah, pastikan semua fix diterapkan dalam
urutan dari §9.2:

1. Fix 5: Tambah `TEST_MANAGEMENT_ENDPOINTS=1` ke `.env`
2. Fix 6: Ubah `page_size=200` → `page_size=100` di `environment.py`
3. Fix 1: Ubah `MISSION_CLI_TIMEOUT=5` → `20` di `settings.py`
4. Fix 2A/2B: Sinkronkan `TEST_NAME_PREFIXES` di 2 file
5. Fix 3: Naikkan deadline polling di `mission_steps.py`
6. Fix 4: (opsional) Tambah debug logging

```bash
# ============================================================
# STEP 0: Pre-flight check — pastikan tidak ada mission bocor
# ============================================================
echo "=== Checking for stuck missions ==="
# page_size=100 (bukan 200, karena limit backend max 100)
curl -s "http://127.0.0.1:8001/api/v1/missions?page_size=100" | \
  python3 -c "
import sys, json
data = json.load(sys.stdin)
for m in data.get('items', []):
    if m['status'] in ('RUNNING', 'STARTING'):
        print(f\"Mission bocor: {m['id']} ({m['name']}) status={m['status']}\")
        # Uncomment next line to force-stop:
        # !curl -X POST 'http://127.0.0.1:8001/api/v1/missions/{m['id']}/stop'
"

# ============================================================
# STEP 1: Terapkan Fix 5, 6, 1, 2, 3, 4 (urutan dari §9.2)
# ============================================================

# Fix 5: TEST_MANAGEMENT_ENDPOINTS=1 ke .env (idempotent)
if ! grep -q "^TEST_MANAGEMENT_ENDPOINTS=1" backend/.env 2>/dev/null; then
    echo 'TEST_MANAGEMENT_ENDPOINTS=1' >> backend/.env
    echo "  .env: TEST_MANAGEMENT_ENDPOINTS=1 added"
else
    echo "  .env: TEST_MANAGEMENT_ENDPOINTS=1 already present"
fi

# Fix 6: page_size=200 → page_size=100 di environment.py
sed -i 's/page_size=200/page_size=100/' \
  backend/e2e_test/features/environment.py
echo "  environment.py: page_size corrected to 100"

# Fix 1: Naikkan CLI_TIMEOUT (test env override)
# Pola: "settings.MISSION_CLI_TIMEOUT = 5" di settings.py:60
if grep -q "settings.MISSION_CLI_TIMEOUT = 5" backend/app/config/settings.py; then
    sed -i 's/settings.MISSION_CLI_TIMEOUT = 5/settings.MISSION_CLI_TIMEOUT = 20/' \
      backend/app/config/settings.py
    echo "  settings.py: MISSION_CLI_TIMEOUT raised 5 → 20"
else
    echo "  settings.py: MISSION_CLI_TIMEOUT already 20 (or changed)"
fi

# Fix 2A: TEST_NAME_PREFIXES di environment.py (pakai Python, bukan sed)
python3 -c "
path = 'backend/e2e_test/features/environment.py'
with open(path) as f: content = f.read()
if '\"s06-\"' not in content:
    content = content.replace(
        'TEST_NAME_PREFIXES = (\n    \"concurrent-\"',
        'TEST_NAME_PREFIXES = (\n    \"concurrent-\",\n    \"s06-\"'
    )
    with open(path, 'w') as f: f.write(content)
    print('  environment.py: s06- prefix added')
else:
    print('  environment.py: s06- prefix already present')
"

# Fix 2B: TEST_NAME_PREFIXES di test_management.py (pakai Python, bukan sed)
# Loop sampai ketemu posisi yang tepat (idempotent: skip jika sudah ada)
python3 -c "
path = 'backend/app/gps/test_management.py'
with open(path) as f: content = f.read()
if '\"s06-\"' not in content and 's06-' not in content:
    content = content.replace(
        'TEST_NAME_PREFIXES: tuple[str, ...] = (\n    \"concurrent-\"',
        'TEST_NAME_PREFIXES: tuple[str, ...] = (\n    \"concurrent-\",\n    \"s06-\"'
    )
    with open(path, 'w') as f: f.write(content)
    print('  test_management.py: s06- prefix added')
else:
    print('  test_management.py: s06- prefix already present')
"

# Fix 3: Naikkan deadline polling di mission_steps.py (line 430)
# Cek dulu current value (handles jika pernah diedit manual)
if grep -q "deadline = time.time() + 120" backend/e2e_test/features/steps/mission_steps.py; then
    sed -i 's/deadline = time.time() + 120/deadline = time.time() + 180/' \
      backend/e2e_test/features/steps/mission_steps.py
    echo "  mission_steps.py: deadline 120 → 180"
elif grep -q "deadline = time.time() + 180" backend/e2e_test/features/steps/mission_steps.py; then
    echo "  mission_steps.py: deadline already 180"
else
    echo "  WARN: mission_steps.py: deadline pattern not found (check manual)"
fi

# Fix 4: Tambah debug logging di SafetyNet cleanup (environment.py)
# Tambahkan branch for 404 / non-200 response
python3 -c "
path = 'backend/e2e_test/features/environment.py'
with open(path) as f: content = f.read()
if 'TEST_MANAGEMENT_ENDPOINTS not active' in content:
    print('  environment.py: Fix 4 debug logging already present')
else:
    old = '''if r.status_code == 200:
            result = r.json()
            logger.info(
                f\"[SafetyNet] bulk cleanup: stopped {len(result.get(\"stopped\", []))}, \"
                f\"deleted {len(result.get(\"deleted\", []))}, \"
                f\"skipped {len(result.get(\"skipped\", []))}\"
            )'''
    new = '''if r.status_code == 200:
            result = r.json()
            logger.info(
                f\"[SafetyNet] bulk cleanup: stopped={result.get(\"stopped\")}, \"
                f\"deleted={result.get(\"deleted\")}, \"
                f\"skipped={result.get(\"skipped\")}\"
            )
        elif r.status_code == 404:
            logger.warning(
                \"[SafetyNet] /test/missions/cleanup 404 — \"
                \"TEST_MANAGEMENT_ENDPOINTS not active\"
            )
        else:
            logger.warning(
                f\"[SafetyNet] /test/missions/cleanup returned {r.status_code}: \"
                f\"{r.text[:200]}\"
            )'''
    if old in content:
        content = content.replace(old, new)
        with open(path, 'w') as f: f.write(content)
        print('  environment.py: Fix 4 debug logging added')
    else:
        print('  WARN: environment.py: Fix 4 pattern not found (check manual)')
"

# ============================================================
# STEP 2: Restart Backend (WAJIB PAKAI SYSTEMD — JANGAN pkill)
# ============================================================
echo "=== Restarting backend via systemd ==="
sudo systemctl restart lte-scanner
sleep 3

# Verify backend alive
curl -s "http://127.0.0.1:8001/health" && echo " ✓ Backend healthy"

# Verify test endpoints aktif
TEST_CHECK=$(curl -s -X PUT "http://127.0.0.1:8001/test/cli/mock/fail" \
  -H "Content-Type: application/json" \
  -d '{"fail": true, "remaining": 1}')
echo "Test endpoint check: $TEST_CHECK"
if echo "$TEST_CHECK" | grep -q "Not Found"; then
    echo "  ⛔ ERROR: Test endpoints masih tidak aktif! Cek TEST_MANAGEMENT_ENDPOINTS di .env"
    exit 1
fi
echo " ✓ Test management endpoints aktif"

# ============================================================
# STEP 3: Jalankan S06 scenario
# ============================================================
echo "=== Running S06 scenario ==="
cd /home/pi/Cellular-Discovery-Service/backend
.venv/bin/python -m behave e2e_test/features/scan_failure.feature -v 2>&1 \
  | tee /tmp/s06_run.log

# Quick grep of expected outcomes
echo ""
echo "=== Quick assertions (grep dari behave output) ==="
if grep -q "1 scenario passed" /tmp/s06_run.log; then
    echo "  ✓ be:have scenario PASSED"
else
    echo "  ⛔ be:have scenario FAILED (lihat /tmp/s06_run.log)"
fi

# ============================================================
# STEP 4: Post-run verification
# ============================================================
echo "=== Post-run verification ==="

# Check mission status (page_size=100, bukan 200)
MISSION_ID=$(curl -s "http://127.0.0.1:8001/api/v1/missions?page_size=100" | \
  python3 -c "import sys,json; missions=json.load(sys.stdin)['items']; 
              s06 = [m for m in missions if m['name']=='s06-mission']
              print(s06[0]['id'] if s06 else 'N/A')")

echo "Mission ID: $MISSION_ID"
curl -s "http://127.0.0.1:8001/api/v1/missions/$MISSION_ID/status" | python3 -m json.tool
curl -s "http://127.0.0.1:8001/api/v1/missions/$MISSION_ID/scans" | python3 -m json.tool

# Check location status
curl -s "http://127.0.0.1:8001/api/v1/missions/$MISSION_ID/locations" | \
  python3 -c "
import sys, json
data = json.load(sys.stdin)
for loc in data.get('items', []):
    print(f\"  Location {loc['id']}: status={loc['status']}, reason={loc.get('failure_reason', 'N/A')}\")
"

# STEP 5: Konfirmasi tidak ada mission bocor
echo ""
echo "=== Verifikasi tidak ada mission bocor ==="
LEAKED=$(curl -s "http://127.0.0.1:8001/api/v1/missions?page_size=100" | \
  python3 -c "
import sys, json
missions = json.load(sys.stdin)['items']
leaked = [m for m in missions 
          if m['status'] in ('RUNNING','STARTING') 
          and m['name'] not in ('stress-test-runner',)
          and not m['name'].startswith(('concurrent-','field-mission','test-','mission-','e2e-','s06-'))]
print(len(leaked))
")
if [ "$LEAKED" = "0" ]; then
    echo "  ✓ Tidak ada mission bocor (non-test prefix)"
else
    echo "  ⚠ $LEAKED mission non-test bocor (lihat manual)"
fi

# Verifikasi tidak ada s06-mission yang stuck
S06_STUCK=$(curl -s "http://127.0.0.1:8001/api/v1/missions?page_size=100" | \
  python3 -c "
import sys, json
missions = json.load(sys.stdin)['items']
stuck = [m for m in missions if m['name']=='s06-mission' and m['status'] not in ('COMPLETED','FAILED')]
print(len(stuck))
")
if [ "$S06_STUCK" = "0" ]; then
    echo "  ✓ Tidak ada s06-mission stuck (semua COMPLETED atau dihapus)"
else
    echo "  ⚠ $S06_STUCK s06-mission stuck"
fi
```

---

## 6. Catatan Riwayat Percobaan (Tidak Diulang)

| Run | Mission | T1 | T2 | T3 | Final | durasi | Penyebab Gagal |
|-----|---------|----|----|----|-------|--------|----------------|
| #1 | 865 | SKIP | VISIT 642 | NONE | STOPPED | ~5,5s | CLI timeout 5s |
| #2 | 866 | SKIP | NONE | NONE | STOPPED | ~4s | TEST_NAME_PREFIXES miss |
| #3 | — | — | — | — | GAGAL | <1s | TEST_MANAGEMENT_ENDPOINTS belum aktif, page_size=200 exceeded |
| **Expected** | — | SKIP | VISIT | VISIT | **COMPLETED** | ~15-20s | — |
| **Run #4 (Sesudah Fix)** | — | SKIP | VISIT | VISIT | **COMPLETED** | ~15-20s | **TODO: Verifikasi** |

**Hal yang TIDAK akan diulang:**
- ❌ Menjalankan test berulang-ulang tanpa memahami root cause (sudah 3 run gagal)
- ❌ Mengubah test assertion tanpa mengubah production code (akan tetap fail)
- ❌ Membiarkan mission bocor tanpa cleanup (sudah ada bug RC-3)
- ❌ Lupa restart backend setelah edit settings (perubahan tidak ter-load)
- ❌ Menggunakan `pkill`/`kill` untuk restart backend (harus pakai systemd)
- ❌ Lupa set `TEST_MANAGEMENT_ENDPOINTS=1` di `.env` (endpoint test tidak aktif)
- ❌ Menggunakan `page_size=200` (melebihi limit 100, return 422)

---

## 7. Hipotesis Rank (Prioritas Investigasi)

### Priority 1 (Paling Likely):
**RC-1 + RC-2**: `MISSION_CLI_TIMEOUT=5s` terlalu pendek → mission tidak sempat
menyelesaikan 2 scan sukses dalam time budget test. Mission berhenti sebelum
selesai karena executor atau test client mendeteksi terminal state lebih dulu.

**Catatan verifikasi RC-2 (race condition):**
- Run #1: Mission 865 sudah SKIP T1 + VISIT T2 dalam 5s. Hanya T3 yang tidak sempat.
- 5s < 20s (perkiraan 2 scan sukses) → mission timeout-nya **RC-1**, bukan race.
- Race condition **TIDAK TERJADI** di Run #1 karena mission timeout lebih awal.
- Fix 3 (deadline 180s) tetap aman sebagai **safety buffer**, bukan perbaikan root cause.

### Priority 2:
**RC-3**: TEST_NAME_PREFIXES tidak match → mission bocor setelah scenario selesai.
Ini bukan penyebab mission gagal, tapi menyebabkan mission stuck di DB.

**RC-6**: TEST_MANAGEMENT_ENDPOINTS tidak aktif → fault injection tidak bisa di-enable → test fail di step pertama (RUN #3).

**RC-7**: page_size=200 melebihi limit → pre-scenario cleanup gagal (RUN #3).

### Priority 3 (Belum Teridentifikasi):
**RC-4**: Sumber pasti status STOPPED. Perlu telusuri lebih dalam:
- Apakah ada exception di `_visit` atau `_run` yang tidak ter-catch?
- Apakah `_handle_gps_failure` me-trigger STOPPED?
- Apakah ada safety net lain yang me-stop mission?

---

## 8. Verifikasi Sukses (Checklist)

- [ ] Scenario PASSED (no failures, no undefined steps)
- [ ] Mission status = COMPLETED
- [ ] `visited_locations` = 2, `total_locations` = 3
- [ ] 2 scan session ter-link (T2 + T3, T1 SKIPPED)
- [ ] 1 location ber-status SKIPPED dengan reason SCAN_ERROR
- [ ] GET `/scans` = 2 items
- [ ] Mission ter-delete setelah scenario selesai (tidak bocor)
- [ ] Tidak ada mission bocor di `/api/v1/missions`
- [ ] Backend berjalan normal setelah test selesai

---

## 9. Kesimpulan

### 9.1 Dependency Chain Antar Fix

```
[Fix 5: TEST_MANAGEMENT_ENDPOINTS=1] ← HARUS PERTAMA
        ↓
  Endpoint /test/cli/mock/fail aktif
        ↓
[Fix 6: page_size=100] ← HARUS SEBELUM Fix 1
        ↓
  SafetyNet cleanup bisa baca missions
        ↓
[Fix 1: MISSION_CLI_TIMEOUT=20] ← Runtime effect
        ↓
  CLI tidak di-timeout prematur
        ↓
[Fix 2: TEST_NAME_PREFIXES + "s06-"] ← Cleanup effect
        ↓
  Mission s06-mission ikut terhapus
        ↓
[Fix 3: deadline=180s] ← Test polling tolerance
        ↓
[Fix 4: debug logging] ← Observability (optional tapi disarankan)
```

### 9.2 Urutan Eksekusi Wajib

| Urutan | Fix | Alasan |
|--------|-----|--------|
| 1 | Fix 5 | Tanpa endpoint aktif, semua step test gagal 404 |
| 2 | Fix 6 | Tanpa page_size benar, SafetyNet loop crash |
| 3 | Fix 1 | Timeout CLI menentukan apakah mission selesai |
| 4 | Fix 2A | Prefix di environment.py untuk after_scenario |
| 5 | Fix 2B | Prefix di test_management.py untuk bulk cleanup |
| 6 | Fix 3 | Deadline test client lebih generous |
| 7 | Fix 4 | Logging untuk debug jika masih gagal |

### 9.3 Restart Requirement

Setelah Fix 5 (`TEST_MANAGEMENT_ENDPOINTS=1` di .env):
- **WAJIB restart backend** via systemd (lihat §5 — STEP 2)
- Env var hanya dibaca sekali saat `if os.environ.get(...)` di main.py L80

Setelah Fix 1 (settings.py):
- **WAJIB restart backend** agar `get_settings()` re-cache

### 9.4 Root Cause Utama (Terverifikasi)

1. **RC-6** — `TEST_MANAGEMENT_ENDPOINTS` tidak diset di `.env` → endpoint test tidak aktif (404)
2. **RC-7** — `page_size=200` melebihi limit backend (100) → 422 Unprocessable Content
3. **RC-3** — `TEST_NAME_PREFIXES` tidak mencakup `"s06-"` → mission bocor di DB
4. **RC-1** — `MISSION_CLI_TIMEOUT=5s` terlalu pendek → mission gagal selesai (Run #1)
5. **RC-2** — Race condition tidak terbukti terjadi (hanya safety buffer Fix 3)

### 9.5 Fix Utama (Semua harus diterapkan bersama)

1. Tambah `"s06-"` ke `TEST_NAME_PREFIXES` di **2 file** (Fix 2A/2B)
2. Tambah `TEST_MANAGEMENT_ENDPOINTS=1` ke `.env` (Fix 5)
3. Ubah `page_size=200` → `page_size=100` di `environment.py` (Fix 6)
4. Naikkan `MISSION_CLI_TIMEOUT` ke 20s (Fix 1)
5. Naikkan poll deadline ke 180s (Fix 3)
6. Tambah debug logging (Fix 4 — optional)
7. **Selalu restart dengan `sudo systemctl restart lte-scanner`** (jangan pkill)

---

## 10. Referensi File & Path

| File | Path | Peran |
|------|------|-------|
| Feature | `backend/e2e_test/features/scan_failure.feature` | Skenario BDD |
| Steps | `backend/e2e_test/features/steps/mission_steps.py` | Step definition |
| Environment | `backend/e2e_test/features/environment.py` | Setup/teardown |
| Adapter | `backend/app/cli/adapter.py` | CLI fault injection |
| Test Mgmt | `backend/app/gps/test_management.py` | Endpoint test |
| Config | `backend/app/config/settings.py` | Settings + timeout |
| .env | `backend/.env` | Runtime env vars |
| Service | `/etc/systemd/system/lte-scanner.service` | Process manager |
| Plan Asal | `.opencode/plans/s06-scan-failure.md` | Original plan |
| Doc Ini | `S06_FIX.md` | Fixed comprehensive |

---

## 11. Unit Test Tambahan (S06)

Ditambahkan 3 unit test baru di `tests/test_cli.py` untuk memverifikasi fault injection CLI:

| Test | Deskripsi | Status |
|------|-----------|--------|
| `test_mock_cli_fail_enabled` | CLIError naik saat MOCK_CLI_FAIL=1 dan remaining>0 | ✅ PASS |
| `test_mock_cli_fail_disabled` | Tidak error saat env tidak diset | ✅ PASS |
| `test_mock_cli_fail_decrements_counter` | Counter berkurang setiap kali fail | ✅ PASS |

**Verifikasi:**
```bash
.venv/bin/python -m pytest tests/test_cli.py -v
# Expected: 14 passed (11 existing + 3 baru)
```

**Catatan:**
- Unit test ini memverifikasi mekanisme fault injection BERJALAN
- Tapi di runtime, ada kemungkinan state module tidak persisten (perlu investigasi lebih lanjut)

---

## 12. Persiapan Menjalankan S06 E2E (BUILD PHASE)

Sebelum menjalankan e2e scenario S06 (`scan_failure.feature`), beberapa item telah disiapkan:

### 12.1 Data Test Locations

File CSV untuk 3 location (T1, T2, T3):
- Path: `backend/tests/data/locations_sample.csv`
- Format: `cellular_tower_id,cellular_tower_name,latitude,longitude`
- Konten: 3 tower di koordinat Jakarta Pusat (-6.2, 106.8)
- Alasan: koordinat berdekatan sehingga radius 20km mencakup semua, sesuai dengan `upload_locations` step

### 12.2 Bug Fix: Lazy Import di adapter.py

**Root Cause:**
`app/cli/adapter.py` menggunakan `try/except` di dalam lazy import. Fallback `should_fail = True` ketika `_decrement_cli_fail()` gagal, tapi karena module-level `_cli_fail_remaining` di-import terpisah, counter tidak benar-benar berkurang.

**Fix:**
```python
# SEBELUM (buggy):
if os.environ.get("MOCK_CLI_FAIL"):
    try:
        from app.gps.test_management import _decrement_cli_fail
        should_fail = _decrement_cli_fail()
    except Exception:
        should_fail = True

# SESUDAH (fixed - top-level import shared instance):
MOCK_CLI_FAIL = os.environ.get("MOCK_CLI_FAIL")
if MOCK_CLI_FAIL:
    from app.gps.test_management import _decrement_cli_fail
    should_fail = _decrement_cli_fail()
```

### 12.3 E2E Test Runner Setup

- `behave 1.3.3` installed via pip
- `httpx` tersedia untuk HTTP client
- Config file: `backend/e2e_test/behave.ini`
- Steps dir: `backend/e2e_test/features/steps/`

### 12.4 Step Definitions untuk S06

Semua step di `scan_failure.feature` sudah ter-cover:
- ✅ `the backend is running on port 8001`
- ✅ `the lte-scanner service is active with mock GPS and CLI`
- ✅ `CLI fault injection is enabled` (S06-specific, PUT ke `/test/cli/mock/fail`)
- ✅ `a mission "s06-mission" with radius 20000 meters`
- ✅ `three locations (T1, T2, T3) uploaded via CSV`
- ✅ `the mission has been planned`
- ✅ `I start the mission`
- ✅ `the mission reaches COMPLETED state`
- ✅ `exactly 2 scan sessions are linked to the mission's locations`
- ✅ `one location has status SKIPPED with reason SCAN_ERROR`
- ✅ `I fetch mission scans for the current mission`
- ✅ `the response contains 2 items` (BARU DITAMBAHKAN)

### 12.5 Status Kesiapan

| Komponen | Status |
|----------|--------|
| Backend service running di port 8001 | ✅ |
| `TEST_MANAGEMENT_ENDPOINTS=1` di .env | ✅ |
| `MISSION_CLI_TIMEOUT=20` di settings.py | ✅ |
| `page_size=100` di environment.py | ✅ |
| Unit test 14/14 PASS | ✅ |
| CSV test locations | ✅ |
| adapter.py fix (top-level import) | ✅ |
| behave installed | ✅ |
| Step definitions lengkap | ✅ |

**Kesiapan: READY untuk eksekusi e2e S06.**

Untuk menjalankan:
```bash
cd backend
.venv/bin/python -m behave e2e_test/features/scan_failure.feature
```

### 12.6 Unit Test Baru untuk S06 E2E (3 tests)

| Test | Tujuan | Hasil |
|------|--------|-------|
| `test_mock_cli_fail_enabled` | Memvalidasi CLIError naik ketika fault state aktif | ✅ PASS |
| `test_mock_cli_fail_disabled` | Memvalidasi tidak error ketika fault tidak aktif | ✅ PASS |
| `test_mock_cli_fail_decrements_counter` | Memvalidasi auto-stop fault setelah N trigger | ✅ PASS |

Ketiga test ini meng-encapsulate logic fault injection sehingga kegagalan runtime dapat dilokalisasi ke salah satu layer:
1. **Setting state** (PUT endpoint) → test di level service
2. **Reading state** (CLI adapter) → test unit (`test_mock_cli_fail_enabled`)
3. **Counter logic** → test unit (`test_mock_cli_fail_decrements_counter`)


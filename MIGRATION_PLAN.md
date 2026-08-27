# MIGRATION PLAN: lte-discovery → lte-scan (RTL-SDR)

## ⚠️ PENTING: JANGAN PERNAH PAKAI lte-discovery LAGI!

**SELALU GUNAKAN `lte-scan` CLI BERBASIS RTL-SDR.**

Command yang harus digunakan:
```bash
lte-scan balance 8 --json --gain 43
lte-scan fast 5 --json --gain 43
```

---

## CONTEXT

Sistem ini awalnya menggunakan `lte-discovery` CLI yang berbasis **USB Modem Serial** (`/dev/ttyUSB0`).
Sekarang beralih ke `lte-scan` CLI yang berbasis **RTL-SDR Dongle** (USB radio receiver).

**PERUBAHAN FUNDAMENTAL:**
- ❌ **LAMA**: Scan berdasarkan port modem (`/dev/ttyUSB0`)
- ✅ **BARU**: Scan berdasarkan LTE Band (`4`, `5`, `8`, `20`, `40`)

---

## OUTPUT FORMAT PERUBAHAN

### lte-discovery (LAMA - TIDAK DIGUNAKAN):
```json
{
  "results": [
    {"operator_name": "Telkomsel", "mcc": "510", "mnc": "10", "rat": "GSM", "status": "Forbidden"}
  ]
}
```

### lte-scan (BARU - WAJIB PAKAI):
```json
{
  "scan_info": {
    "band": 8,
    "gain_db": 43,
    "mode": "balance",
    "total_cells": 7,
    "timestamp": "2026-08-26T02:59:01.767184+00:00"
  },
  "cells": [
    {
      "frequency_mhz": 929.8,
      "earfcn": 3498,
      "band": "8",
      "pci": 1,
      "mcc": 510,
      "mnc": 10,
      "rsrp": -15.2,
      "operator": "Telkomsel",
      "country": "Indonesia"
    }
  ]
}
```

---

## FILES YANG HARUS DIUBAH

### 1. CONFIG & SETTINGS
| File | Perubahan |
|------|----------|
| `app/config/settings.py` | `LTE_DISCOVERY_COMMAND` → `LTE_SCAN_COMMAND` |
| `.env` | Update command dari `lte-discovery` ke `lte-scan balance 8 --json --gain 43` |

### 2. CLI ADAPTER
| File | Perubahan |
|------|----------|
| `app/cli/adapter.py` | Ubah command args: `scan --port` → `balance <band> --json --gain` |
| `app/cli/schemas.py` | Tambah field: `band`, `pci`, `frequency_mhz`, `rsrp`, `earfcn` |
| `app/cli/adapter.py` | Update parser untuk format baru `cells` array |

### 3. DATABASE SCHEMA
| File | Perubahan |
|------|----------|
| `app/db/models/scan_session.py` | `tty_port` → `band` (String, max 10) |
| `app/db/models/scan_result.py` | Tambah: `pci`, `frequency_mhz`, `earfcn`, `rsrp` |
| Migration SQL | ALTER TABLE + backup data lama |

### 4. API REQUEST SCHEMA
| File | Perubahan |
|------|----------|
| `app/schemas/scan.py` | `ScanRequest.tty` → `band` (int, required: 4,5,8,20,40) |
| `app/schemas/scan.py` | `ScanSessionResponse.tty_port` → `band` |

### 5. SERVICES
| File | Perubahan |
|------|----------|
| `app/services/scan_service.py` | `execute_scan(port=...)` → `execute_scan(band=...)` |
| `app/services/history_service.py` | Update field mapping |

### 6. REPOSITORIES
| File | Perubahan |
|------|----------|
| `app/repositories/scan_session_repository.py` | `tty_port` → `band` |
| `app/repositories/scan_result_repository.py` | Tambah field mapping baru |

### 7. TESTS
| File | Perubahan |
|------|----------|
| `tests/test_cli.py` | Semua mock dari `lte-discovery` → `lte-scan` |
| `tests/test_scan_*` | Update request body dari `tty` ke `band` |

### 8. MISSION (OPTIONAL)
| File | Perubahan |
|------|----------|
| `app/schemas/mission.py` | `tty_port` → tetap untuk GPS, atau hapus jika tidak relevan |
| `app/core/mission_executor.py` | Update error messages |

---

## MIGRATION STEPS

### Phase 1: Documentation (DILAKUKAN SEKARANG)
- [x] Create this migration plan
- [ ] Update AGENT.md dengan instruksi PENTING
- [ ] Update README.md

### Phase 2: Configuration
- [ ] Update `settings.py` - rename variable
- [ ] Update `.env` - change command
- [ ] Update `.env.example`

### Phase 3: Core Logic
- [ ] Update `CLIAdapter` - command args baru
- [ ] Update `CLIScanResult` schema - fields baru
- [ ] Update `_parse_output()` - parser format baru
- [ ] Update `ScanService` - parameter `band` instead of `port`

### Phase 4: Database
- [ ] Create migration script
- [ ] Backup existing data
- [ ] ALTER TABLE scan_sessions (tty_port → band)
- [ ] ALTER TABLE scan_results (tambah kolom baru)

### Phase 5: API & Schemas
- [ ] Update `ScanRequest` schema
- [ ] Update `ScanSessionResponse` schema
- [ ] Update router endpoints

### Phase 6: Tests
- [ ] Update all test mocks
- [ ] Add new tests for lte-scan format
- [ ] Run full test suite

### Phase 7: Cleanup
- [ ] Remove `lte-discovery` references
- [ ] Update mock CLI scripts
- [ ] Verify all imports

---

## COMPATIBILITY NOTES

### Breaking Changes:
1. **API Request**: `{tty: "/dev/ttyUSB0"}` → `{band: 8}`
2. **Database**: Column `tty_port` renamed to `band`
3. **CLI Command**: `lte-discovery scan --port /dev/ttyUSB0 --json` → `lte-scan balance 8 --json --gain 43`

### Non-Breaking:
- Response structure tetap similar (operator_name, mcc, mnc, rat)
- History/service layer dapat diadaptasi dengan minimal change

---

## VALIDATION CHECKLIST

Setelah migration selesai:
- [ ] `lte-scan --help` berjalan normal
- [ ] RTL-SDR device terdeteksi (`rtl_test -t`)
- [ ] API `/api/v1/scan` dengan `{band: 8}` return results
- [ ] Database menyimpan data dengan band baru
- [ ] Tests passing 100%
- [ ] No references to `lte-discovery` di codebase

---

## RISK ASSESSMENT

| Risk | Level | Mitigation |
|------|-------|------------|
| Data loss dari migration DB | 🔴 HIGH | Backup sebelum migrate |
| RTL-SDR hardware not detected | 🟡 MEDIUM | Verify `rtl_test` before deploy |
| API breaking changes | 🔴 HIGH | Update frontend/docs |
| Test failures | 🟡 MEDIUM | Full test suite before release |

---

## TIMELINE ESTIMASI

- Phase 1-2: 30 menit
- Phase 3-4: 1 jam
- Phase 5-6: 45 menit
- Phase 7: 15 menit
- **TOTAL: ~3 jam**

---

## CRITICAL REMINDER

> **JANGAN PERNAH KEMBALI KE `lte-discovery`!**
> 
> Sistem ini 100% berbasis RTL-SDR sekarang.
> Semua referensi ke `lte-discovery`, `tty_port`, `/dev/ttyUSB0` harus dihapus/diganti.
> 
> Command yang valid hanya: `lte-scan {fast,balance,full} {band} --json [--gain N]`

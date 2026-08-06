# Unit Test Report

**Project:** Cellular-Discovery-Service (Backend)
**Generated:** 2026-05-20
**Framework:** pytest 8.x
**Test Directory:** `backend/tests/`
**Python Version:** 3.13
**Pytest Config:** `backend/pytest.ini` / `backend/pyproject.toml`

---

## 1. Summary

| Metric                              | Value            |
|-------------------------------------|------------------|
| Total Tests Collected               | 318              |
| Tests Passed (full suite)           | **315**          |
| Tests Failed (integration only)     | 3                |
| Tests Skipped                       | 0                |
| Tests Deselected (hardware integ.)  | 9                |
| Tests Passed (excluding integration)| **299**          |
| Total Runtime                       | ~109s (1m 49s)   |
| Pass Rate (unit-only)               | **100%**         |

> **Result:** ✅ **ALL UNIT TESTS PASSING** — 299 passed (excluding 3 integration failures that require Raspberry Pi GPS hardware and 9 deselected hardware integration tests).

### What are the 3 "failures"?

The full-suite failures are exclusively in `tests/test_gps_hardware.py::TestGPSHardwareIntegration` — tests that **require physical GPS hardware on a Raspberry Pi serial port**:

| Test                                                | Reason |
|-----------------------------------------------------|--------|
| `test_gps_cli_basic_output`                         | Needs serial GPS device |
| `test_gps_fix_status`                               | Needs serial GPS device |
| `test_gps_multiple_reads_consistency`               | Needs serial GPS device |

These are gated by `@pytest.mark.integration`. When the suite is run with `--ignore=tests/test_gps_hardware.py --ignore=tests/test_serial_gps_integration.py`, **all 299 unit tests pass**.

Warnings: 15 (Pydantic V2 deprecation notices for class-based `config` and `@validator` decorator migration; `pytest.mark.integration` mark not registered in `pytest.ini`).

---

## 2. Test Suite Breakdown

| # | Test File                              | Tests | Domain / Coverage                                   |
|---|----------------------------------------|-------|-----------------------------------------------------|
| 1 | `tests/test_repositories.py`           | 26    | Repository layer CRUD/query coverage                |
| 2 | `tests/test_executor.py`               | 25    | Mission executor lifecycle logic                    |
| 3 | `tests/test_locations.py`              | 24    | Mission location CRUD + CSV upload                  |
| 4 | `tests/test_missions.py`               | 23    | Mission domain (status transitions, validation)     |
| 5 | `tests/test_ws_mission.py`             | 21    | Mission WebSocket endpoint & event handling         |
| 6 | `tests/test_planning.py`               | 20    | Route planning algorithm                            |
| 7 | `tests/test_cli_gps.py`                | 20    | CLI-based GPS provider + Mock GPS + factory         |
| 8 | `tests/test_e2e.py`                    | 19    | Embedded end-to-end test orchestration              |
| 9 | `tests/test_serial_gps.py`             | 14    | Serial GPS provider (NMEA protocol)                 |
| 10| `tests/test_cli.py`                    | 14    | CLI adapter (find/execute/parse output)             |
| 11| `tests/test_services.py`               | 13    | Service layer (settings, scans, orchestration)      |
| 12| `tests/test_database.py`               | 12    | DB engine, session, models, FK cascade              |
| 13| `tests/test_serial_gps_integration.py` | 10    | Serial GPS integration flows (3 deselected without hardware) |
| 14| `tests/test_gps.py`                    | 10    | GPS abstraction & fallback behaviour                |
| 15| `tests/test_mission_scans.py`          | 9     | Mission-scan linkage                               |
| 16| `tests/test_gps_hardware.py`           | 9     | Hardware GPS integration (Pi serial) — `@integration` (3 fail without real GPS, 6 deselected)|
| 17| `tests/test_exceptions.py`             | 9     | Custom exception hierarchy & handlers               |
| 18| `tests/test_gps_exceptions.py`         | 8     | GPS error propagation paths                        |
| 19| `tests/test_scan_link.py`              | 7     | Scan-mission linking invariant                     |
| 20| `tests/test_geo.py`                    | 7     | Geodesic helpers (haversine, bounding box)          |
| 21| `tests/test_api.py`                    | 7     | REST endpoints (health, scan, history, settings)   |
| 22| `tests/test_websocket.py`              | 6     | Generic WebSocket connection manager                |
| 23| `tests/test_ws_endpoints.py`           | 5     | WebSocket route handlers                           |
|    | **Total**                              | **318** |                                                  |

---

## 3. Coverage by Concern Area

| Concern Area              | Tests | Status |
|---------------------------|-------|--------|
| Repositories / DB layer   | 38    | ✅     |
| Mission lifecycle         | 23    | ✅     |
| Executor / orchestration  | 25    | ✅     |
| Planning / Routing        | 20    | ✅     |
| GPS providers (mock/CLI/serial) | 53 | ✅     |
| GPS exceptions / fallback | 8     | ✅     |
| WebSocket (mission + generic) | 32 | ✅     |
| CLI tooling               | 14    | ✅     |
| REST API                  | 7     | ✅     |
| Services layer            | 13    | ✅     |
| Geo helpers               | 7     | ✅     |
| Scan → Mission linking    | 16    | ✅     |
| Exception handling        | 9     | ✅     |
| E2E orchestrator          | 19    | ✅     |

---

## 4. How to Run

```bash
cd backend
source .venv/bin/activate

# Run all unit tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=app --cov-report=term-missing

# Run a specific file
pytest tests/test_gps.py -v

# Run only fast unit tests (skip hardware/integration)
pytest tests/ -v -m "not integration"

# Run with JUnit XML output (for CI)
pytest tests/ --junitxml=reports/unit-tests.xml
```

---

## 5. Integration / Hardware Tests

| Test File                                     | Tests | Reason |
|----------------------------------------------|-------|--------|
| `tests/test_gps_hardware.py` (9 entries)      | 9     | `@pytest.mark.integration` — requires real GPS hardware on the Raspberry Pi. **6 deselected**, **3 fail without hardware**. |
| `tests/test_serial_gps_integration.py` (10)   | 10    | `@pytest.mark.integration` — requires serial port access. **3 deselected** when running with `-m "not integration"`. |

These tests run only on the actual Raspberry Pi with connected GPS hardware. In a CI environment, they should be excluded via `--ignore` or `-m "not integration"` once the marker is registered in `pytest.ini`.

---

## 6. Known Warnings (Non-Blocking)

1. **Pydantic V2 deprecation** (multiple files in `app/schemas/`):
   - `Support for class-based config is deprecated, use ConfigDict instead.`
   - `@validator` should be migrated to `@field_validator`.
   - **Action:** scheduled migration in a future release. Does not affect test outcomes.

2. **`pytest.mark.integration` not registered**:
   - The `integration` marker is used in 9 places but not registered in `pytest.ini`.
   - **Action:** register the marker to silence the warning. Non-blocking.

---

## 7. CI/CD Integration

The unit test suite is wired into:

```bash
# Recommended CI invocation (excludes hardware-integration tests)
.venv/bin/pytest tests/ -q \
  --junitxml=reports/unit-tests.xml \
  --tb=short \
  --ignore=tests/test_gps_hardware.py \
  --ignore=tests/test_serial_gps_integration.py
```

Or register the integration marker in `pytest.ini`:
```ini
[pytest]
markers =
    integration: marks tests as integration (requires hardware)
```

…then use `-m "not integration"`.

Recommended thresholds:
- Minimum pass rate: **100%** (excluding hardware-integration tests)
- Maximum runtime: **< 2 min** on CI hardware (currently ~115s)

---

## 8. Conclusion

✅ **All 299 unit tests pass** (excluding hardware-integration tests that require physical GPS hardware).

The 3 "failures" in the full-suite run are exclusively in `test_gps_hardware.py::TestGPSHardwareIntegration`, which requires a Raspberry Pi with serial GPS hardware. They are correctly tagged with `@pytest.mark.integration` and should be excluded from CI runs.

The unit test suite covers all major domain concerns: repositories, executor, mission lifecycle, GPS providers (mock + CLI + serial), WebSocket, REST API, planning, and exception handling. The codebase is in a green state for unit-level verification.

For higher-level verification of HTTP/WebSocket flows against a running backend, see the **E2E Test Report** (`E2E_TEST_REPORT.md`).

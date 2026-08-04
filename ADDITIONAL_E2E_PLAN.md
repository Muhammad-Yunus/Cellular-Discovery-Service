# Additional End-to-End (E2E) Test Plan & Checklist

This document tracks **end-to-end test scenarios that are NOT yet covered** by the
existing `e2e_test/features/mission_flow.feature`. Each item is a candidate scenario
that should be implemented in Behave Gherkin and live alongside the current feature
file.

The list is ordered by **criticality** (impact on business / frequency of failure /
risk of regression). The currently passing scenario is the *happy path*; this plan
focuses on state-transition edge cases, guards, error paths, and operator workflows.

---

## Priority Legend

| Tier    | Meaning                                                                                  |
|---------|------------------------------------------------------------------------------------------|
| **P0**  | Critical — production-breaking if broken. Must cover before any release.                 |
| **P1**  | High — common operator workflow / guard that is easy to break with refactors.            |
| **P2**  | Medium — useful guard / error path; lower volume but still user-visible.                 |
| **P3**  | Low — nice-to-have for completeness, low risk to ship without.                            |

---

## P0 — Critical (correctness & state safety)

- [ ] **S01. Concurrent mission guard** — Two missions must not run at the same time.
  - Create `M-A` (planned, ready).
  - Start `M-A` → 200 RUNNING.
  - Create `M-B` (planned, ready) and `POST /missions/{B}/start` → expect **409 Conflict** with `Another mission is already running`.

- [ ] **S02. Pause → Resume → COMPLETED flow** — Validate state transitions across pause/resume.
  - Start mission with N locations, where one location takes longer than the others (e.g. mocked delay).
  - `POST /missions/{id}/pause` → status `PAUSED`, visited count frozen.
  - Sleep, verify status stays `PAUSED` and executor is idle.
  - `POST /missions/{id}/resume` → status `RUNNING`.
  - Wait → COMPLETED. Verify all locations visited and linked to scan sessions.

- [ ] **S03. Stop during RUNNING** — Operator aborts an in-progress mission.
  - Start mission.
  - During RUNNING, `POST /missions/{id}/stop` → 200, status `STOPPED`, `stopped_at` set.
  - Subsequent `POST /start` → 409 (cannot start while STOPPED without re-plan).

- [ ] **S04. Cannot start without plan** — Guard against running an un-planned mission.
  - Create mission, upload locations, **skip** `/plan`.
  - `POST /missions/{id}/start` → expect **422 / 409** with message indicating mission must be planned first.

- [ ] **S05. Cannot start with zero locations** — Boundary guard.
  - Create mission with no locations uploaded.
  - `POST /missions/{id}/start` → expect **422** with message `Mission has no locations to plan` (or equivalent).

- [ ] **S06. Mission failure (scan failure mid-run)** — Validate scan failure → location `SKIPPED`, mission may continue / complete.
  - Configure mock scanner to fail on the 2nd tower.
  - Run mission → expect COMPLETED with `visited_locations = N-1` and one location marked `SKIPPED` with reason `SCAN_ERROR`.

---

## P1 — High (common operator workflows)

- [ ] **S07. Reorder route manually** — Operator changes the planned sequence.
  - Plan mission with 5 locations.
  - Capture original sequence.
  - `POST /missions/{id}/route/reorder` with new ordering.
  - `GET /missions/{id}/route` → reflects new sequence; distances/bearings recomputed.

- [ ] **S08. Skip a location mid-planning** — Operator excludes a tower before running.
  - Plan mission with 4 locations.
  - `POST /missions/{id}/route/skip` with one location id.
  - Verify location status = `SKIPPED`, sequence removed, total_locations decremented.

- [ ] **S09. Delete single mission location** — Remove one tower from upload before running.
  - Upload 5 locations.
  - `DELETE /missions/{id}/locations/{loc_id}` → 200.
  - `GET /missions/{id}/locations` → returns 4 items.

- [ ] **S10. Bulk delete locations by batch** — Remove a whole batch in one call.
  - Upload CSV with batch-id "batch-A" (3 rows) + "batch-B" (2 rows).
  - `POST /missions/{id}/locations/bulk-delete` with `batch_id="batch-A"` → 3 deleted, 2 remain.

- [ ] **S11. Delete a mission (IDLE → 200)** — Full lifecycle cleanup.
  - Create + upload + plan (status READY).
  - `DELETE /missions/{id}` → 200 with `Mission deleted successfully`.
  - `GET /missions/{id}` → 404.

- [ ] **S12. Delete a mission on RUNNING → 409** — Guard against unsafe delete.
  - Start a mission, `DELETE /missions/{id}` → expect **409 Conflict**.

- [ ] **S13. Patch mission while IDLE (valid fields)** — Update name / radius / tty / start location.
  - Create + upload + plan.
  - `PATCH /missions/{id}` with `{name, radius_meters, tty_port, start_location_id}` → 200, fields reflected.
  - Verify sequence cleared if structural fields changed.

- [ ] **S14. Patch mission while RUNNING ��� 409** — Guard.
  - Start a mission.
  - `PATCH /missions/{id}` with `{"name": "x"}` → expect **409**.

- [ ] **S15. GET /status during RUNNING** — Validate live progress payload.
  - Start mission, poll `/status` every 2s.
  - Verify `status`, `visited_locations`, `total_locations`, `progress_percent`, `current_location_id` change over time and reach 100%.

- [ ] **S16. GET /logs after mission** — Verify structured log capture.
  - Run a mission to completion.
  - `GET /missions/{id}/logs` → returns array of log entries (timestamps, levels, messages) including `MISSION_START`, `VISIT`, `MISSION_COMPLETED`.

---

## P2 — Medium (filters, exports, error paths)

- [ ] **S17. Mission scans pagination** �� Validate `page` + `page_size`.
  - Run mission producing >10 scan results.
  - `GET /missions/{id}/scans?page=1&page_size=5` → 5 items, `total=12`, `pages=3`.
  - `GET ...?page=2&page_size=5` → next 5 items, no overlap.

- [ ] **S18. Mission scans filter by RAT** — Filter by radio access tech.
  - `GET /missions/{id}/scans?rat=GSM` → only GSM items.
  - `GET /missions/{id}/scans?rat=LTE` → only LTE items.

- [ ] **S19. Mission scans search** — ILIKE search across operator name.
  - `GET /missions/{id}/scans?search=telkomsel` → matches operator rows.

- [ ] **S20. Mission scans time range** — Filter by `start_time` / `end_time`.
  - Insert scans with known timestamps.
  - `GET /missions/{id}/scans?start_time=...&end_time=...` → correct subset.

- [ ] **S21. Mission CSV export with filters** — Filters apply to export.
  - `GET /missions/{id}/scans/export?rat=GSM` → CSV contains only GSM rows.
  - Header line includes `cellular_tower_id,cellular_tower_name,mission_location_id`.

- [ ] **S22. History list + export (global)** — Across all missions.
  - `GET /api/v1/history?page=1&page_size=10` → paginated.
  - `GET /api/v1/history/export` → CSV with all results.

- [ ] **S23. Settings GET / PUT** — Operator config persistence.
  - `GET /api/v1/settings` → returns list.
  - `PUT /api/v1/settings` with `{key, value}` list → 200, persists, then re-GET reflects values.

- [ ] **S24. Reject upload with bad CSV header** — Validation guard.
  - `POST /missions/{id}/locations/upload` with file using wrong header → expect **422** with `Invalid CSV header`.

- [ ] **S25. Reject upload to non-existent mission** — 404 path.
  - `POST /missions/99999/locations/upload` → expect **404 Mission not found`.

- [ ] **S26. Reject upload while RUNNING** — Guard.
  - Start a mission.
  - `POST /missions/{id}/locations/upload` → expect **409 Conflict: Cannot modify locations while mission is running**.

- [ ] **S27. GET mission detail with valid data** — Detail payload shape.
  - Create + upload + plan.
  - `GET /missions/{id}` → contains `locations` array ordered by `sequence_order`, includes `progress_percent`, `current_location_id` (null when IDLE).

- [ ] **S28. GET non-existent mission → 404** — Error path.
  - `GET /missions/99999` → 404 with `Mission not found`.

- [ ] **S29. List missions with status filter** — `?status=RUNNING`, `?status=COMPLETED`.
  - Create 3 missions in different states.
  - `GET /api/v1/missions?status=COMPLETED` → only completed missions.

- [ ] **S30. List missions with invalid status → 422** — Validation.
  - `GET /api/v1/missions?status=BOGUS` → expect **422 Invalid mission status: BOGUS**.

---

## P1 — High (error paths for non-existent missions)

- [ ] **S41. Export scans for non-existent mission → 404**
  - `GET /missions/999999/scans/export` → expect **404** with `Mission not found`.
  - Verifies export endpoint validates mission existence before streaming CSV.

- [ ] **S42. Upload locations to non-existent mission → 404**
  - `POST /missions/999999/locations/upload` with a valid CSV file → expect **404**.
  - Verifies upload endpoint validates mission existence before parsing CSV.

- [ ] **S43. Bulk-delete locations for non-existent mission → 404**
  - `POST /missions/999999/locations/bulk-delete` with `{"upload_batch_id": "test"}` → expect **404**.
  - Verifies bulk-delete endpoint validates mission existence before operation.

- [ ] **S44. Mission route reorder for non-existent mission → 404**
  - `POST /missions/999999/route/reorder` with `{"order": [1,2]}` → expect **404**.
  - Verifies reorder endpoint validates mission existence.

- [ ] **S45. Mission route skip for non-existent mission → 404**
  - `POST /missions/999999/route/skip` with `{"location_id": 1}` → expect **404**.
  - Verifies skip endpoint validates mission existence.

- [ ] **S46. Mission control start for non-existent mission → 404**
  - `POST /missions/999999/start` → expect **404**.
  - Verifies start control validates mission existence.

- [ ] **S47. Mission control pause for non-existent mission → 404**
  - `POST /missions/999999/pause` → expect **404**.
  - Verifies pause control validates mission existence.

- [ ] **S48. Mission control stop for non-existent mission → 404**
  - `POST /missions/999999/stop` → expect **404**.
  - Verifies stop control validates mission existence.

- [ ] **S49. Mission logs for non-existent mission → 404**
  - `GET /missions/999999/logs` → expect **404**.
  - Verifies logs endpoint validates mission existence.

## P3 — Low (completeness / nice-to-have)

- [ ] **S31. WebSocket mission events (full sequence)** — Validate the WS envelope types during a real run.
  - Connect to `ws://host/api/v1/ws/missions`.
  - Start mission, observe `mission_started`, `mission_progress`, `mission_visit`, `mission_completed`.
  - Disconnect mid-run, reconnect, receive remaining events.

- [ ] **S32. Single-location mission** — Edge case: exactly 1 tower.
  - Upload 1 location, plan, start → COMPLETED, 1 scan session linked.

- [ ] **S33. Mission with duplicate tower IDs (idempotent re-upload)** — Verify upsert behavior at the API level.
  - Upload CSV, then upload same CSV again.
  - Verify total_locations unchanged (upsert, not duplicate).

- [ ] **S34. Scan CLI failure returns error to caller** — Direct scan endpoint.
  - Configure mock CLI to fail.
  - `POST /api/v1/scan` → 200 with `status=Forbidden` (or appropriate), error reflected in session.

- [ ] **S35. Health endpoint reports 200 / 503** — Liveness probe.
  - `GET /health` → 200 with `{"status":"ok"}`.

- [ ] **S36. OpenAPI docs available** — Schema exposure.
  - `GET /docs` → 200 HTML.
  - `GET /openapi.json` → 200 JSON containing `/api/v1/missions` paths.

- [ ] **S37. Mission with many locations (stress)** — Plan and complete a mission with 20+ towers to validate ordering stability.

- [ ] **S38. Recover orphaned STARTING mission on restart** — On `startup()` any leftover `STARTING`/`RUNNING`/`PAUSED` becomes `STOPPED`.
  - Insert mission in DB with status `STARTING`.
  - Restart backend, verify status flipped to `STOPPED`.

- [ ] **S39. Get route before planning → 422** — Validation.
  - `GET /missions/{id}/route` before `/plan` → 422.

- [ ] **S40. Plan twice → deterministic sequence** — Re-running plan should give same order for stable inputs.

---

## Implementation Notes

- All scenarios should live under `backend/e2e_test/features/` as `.feature` files, sharing the step definitions in `mission_steps.py` (or new step files split per domain: `mission_control_steps.py`, `mission_locations_steps.py`, `mission_scans_steps.py`, etc.).
- Each scenario MUST run against the live dev backend on `http://127.0.0.1:8001` (configured via `BACKEND_URL` env var), so background executors and WebSocket paths are exercised — not just the FastAPI request/response layer.
- Each scenario MUST clean up after itself where possible (delete the created mission at the end) to keep the dev DB stable across runs.
- Use unique mission names per run (e.g. include timestamp) to avoid cross-run interference.
- Polling helper should support a configurable timeout (default 120s) for long missions.

## Suggested Order of Implementation

1. **P0**: S01, S02, S03, S04, S05, S06  → unblocks safe release of executor.
2. **P1**: S07–S16 → covers all major operator workflows.
3. **P2**: S17–S30 → covers filters, exports, validation guards.
4. **P3**: S31–S40 → completeness, WS, schema, edge cases.

After each batch, re-run:
```bash
.venv/bin/behave e2e_test/features/ -v
```
and confirm all scenarios (old + new) pass.
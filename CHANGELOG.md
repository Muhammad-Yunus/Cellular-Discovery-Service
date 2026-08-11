# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Added
- GPS retry logic (5 attempts, 3s interval) before fallback
- MovingMockGPSProvider with waypoint support
- GPS validation and README documentation for run_mission.py
- Systemd-based backend restart for mission executor
- Independent device location endpoint (`GET /api/v1/device/location`)
- Multi-field sorting on scan results (`operator_name`, `mcc`, `mnc`, `rat`, `scan_time`)
- Cell sort keys: `cellular_tower_id`, `cellular_tower_name`
- Mission logs pagination endpoint (`GET /api/v1/missions/{id}/logs`)
- Mission scans with pagination, filtering, sorting, and CSV export
- Mission location download template endpoint
- E2E test coverage (S01-S49) with Behave BDD framework
- API documentation for mission endpoints in `Doc/API.md`
- Database schema documentation (`Doc/SCHEMA.md`)

### Changed
- Default GPS_PROVIDER changed from `mock` to `cli` with `/dev/ttyAMA0`
- GPS provider now uses jq pipeline + multi-read for valid fix acquisition
- Mission planner anchors TSP route on device GPS position
- Upload endpoint response normalized to consistent flat format
- Validation errors flattened to project standard format
- DELETE /missions/{id} restricted to IDLE, STOPPED, FAILED status only
- Sort parameter mapping and order_by fixed in scan result repository
- `.opencode/` folder added to `.gitignore`

### Fixed
- `dist_match` variable scope in log sampling
- INFO log sampling interval (5s)
- Pagination: return empty results for page > total_pages
- Device location path: `/device/location` (not `/device/location`)
- GPS retry on connection lost with exponential backoff
- Mission executor: prevent concurrent execution with state guard
- Mission stop signal propagation to executor loop
- Scan location matching: use closest location within radius_meters
- Mission logs: use event_type from logs instead of scan status
- Location status updates on scan completion

### Removed
- Legacy GPS provider code paths
- Unnecessary fallback mechanisms

---

## [0.1.0] - 2026-07-27

### Added
- Initial project setup with FastAPI backend
- LTE scan via USB modem CLI integration
- Scan history management (list, get, delete, export)
- Mission CRUD operations
- Mission location management (upload, download, bulk delete)
- Mission planning with TSP algorithm
- Mission execution with GPS navigation
- WebSocket support for real-time updates
- Database schema with PostgreSQL + Alembic migrations
- Application settings management
- GPS provider abstraction (Mock, Serial)
- Unit and integration test infrastructure
- API documentation
- Deployment documentation
- Systemd service configuration

---

## [0.2.0] - 2026-08-11

### Added
- **Mission Logs**: Full audit trail for mission lifecycle events
  - Event types: `STARTED`, `GPS_FIX`, `SCANNING`, `ARRIVED`, `SKIPPED`, `FAILED`, `COMPLETED`, `STOPPED`, `PAUSED`, `RESUMED`
  - Paginated endpoint: `GET /api/v1/missions/{id}/logs`
  - Database table: `mission_logs` with indexes on `mission_id` and `timestamp`

- **Cell Sort Keys**: Additional sort fields for mission scans
  - `cellular_tower_id` and `cellular_tower_name`
  - Available in both mission scans and scan history endpoints

- **GPS Enhancements**:
  - Retry logic with 5 attempts and 3s interval
  - MovingMockGPSProvider with waypoint support
  - jq pipeline for robust GPS CLI parsing
  - Altitude extraction from GPS output

- **Test Coverage**:
  - E2E tests: S01-S49 covering all mission flow scenarios
  - Unit tests: GPS providers, mission planner, executor
  - Integration tests: Mission CRUD, location management, scan linking
  - Test report: 120+ tests passing

- **Documentation**:
  - Database schema documentation (`Doc/SCHEMA.md`)
  - Architecture documentation updated
  - API documentation for new endpoints
  - README updates with new features

### Changed
- GPS default provider: `mock` → `cli`
- Mission execution now logs all lifecycle events
- Scan results include tower ID and name
- Migration history now complete (3 migrations)

### Fixed
- Multiple bug fixes in GPS parsing, mission execution, and pagination
- Database schema alignment (mission_logs table)
- Test assertions to match actual implementation

---

## [0.3.0] - Planned

### Planned Features
- [ ] Health check endpoint (`/healthz`)
- [ ] Multiple modem support
- [ ] Scheduled/automatic scans
- [ ] Authentication & user management (JWT)
- [ ] Prometheus metrics endpoint
- [ ] CSV/JSON export for missions
- [ ] Frontend integration with new API

---

## [0.4.0] - Planned

### Planned Features
- [ ] Real-time scan notifications via WebSocket
- [ ] Auto-trigger scan on modem hotplug
- [ ] Advanced dashboard with heatmap visualization
- [ ] Mobile-responsive frontend

---

## [0.5.0] - Planned

### Planned Features
- [ ] Cloud sync and backup
- [ ] Multi-device coordination
- [ ] API rate limiting
- [ ] Advanced analytics and reporting

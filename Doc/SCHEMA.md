# Database Schema Documentation

## Overview

All tables are created in the `app` schema (not public) in PostgreSQL 15+.
Database migrations are managed by Alembic.

---

## Table Diagram

```
┌─────────────────┐
│    missions     │
│─────────────────│
│ id (PK)         │
│ name            │
│ description     │
│ status          │
│ radius_meters   │
│ tty_port        │
│ start_location_id (FK)
│ current_location_id (FK)
│ total_locations │
│ visited_locations │
│ started_at      │
│ completed_at    │
│ stopped_at      │
│ created_at      │
│ updated_at      │
└────────┬────────┘
         │
         │ 1:N
         ▼
┌─────────────────────┐
│  mission_locations  │
│─────────────────────│
│ id (PK)             │
│ mission_id (FK)     │
│ cellular_tower_id   │
│ cellular_tower_name │
│ latitude            │
│ longitude           │
│ upload_batch_id     │
│ sequence_order      │
│ status              │
│ distance_from_prev  │
│ bearing_from_prev   │
│ estimated_arrival   │
│ actual_visit_time   │
│ scan_session_id (FK)
│ visited_at          │
│ created_at          │
│ updated_at          │
└──────────┬──────────┘
           │
           │ 1:N (via scan_session)
           ▼
┌─────────────────┐
│  scan_sessions  │
│─────────────────│
│ id (PK)         │
│ scan_time       │
│ tty_port        │
│ latitude        │
│ longitude       │
│ mission_location_id (FK)
│ created_at      │
└────────┬────────┘
         │
         │ 1:N
         ▼
┌─────────────────┐
│  scan_results   │
│─────────────────│
│ id (PK)         │
│ session_id (FK) │
│ operator_name   │
│ mcc             │
│ mnc             │
│ rat             │
│ status          │
└─────────────────┘

┌─────────────────┐
│   mission_logs  │
│─────────────────│
│ id (PK)         │
│ mission_id (FK) │
│ timestamp       │
│ event_type      │
│ message         │
│ created_at      │
│ updated_at      │
└─────────────────┘

┌─────────────────┐
│    settings     │
│─────────────────│
│ key (PK)        │
│ value           │
│ updated_at      │
└─────────────────┘
```

---

## Table Definitions

### `missions`

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | INTEGER | NO | SERIAL | Primary key |
| `name` | VARCHAR(255) | NO | - | Mission name |
| `description` | TEXT | YES | - | Mission description |
| `status` | VARCHAR(20) | NO | 'IDLE' | Current state: IDLE, PLANNING, READY, STARTING, RUNNING, PAUSED, COMPLETED, STOPPED, FAILED |
| `radius_meters` | INTEGER | YES | 20 | Proximity radius for location matching |
| `tty_port` | VARCHAR(50) | YES | - | USB modem port path |
| `start_location_id` | INTEGER | YES | - | FK → mission_locations.id |
| `current_location_id` | INTEGER | YES | - | FK → mission_locations.id |
| `total_locations` | INTEGER | NO | 0 | Total number of locations in mission |
| `visited_locations` | INTEGER | NO | 0 | Number of locations visited |
| `started_at` | TIMESTAMP | YES | - | Mission start timestamp |
| `completed_at` | TIMESTAMP | YES | - | Mission completion timestamp |
| `stopped_at` | TIMESTAMP | YES | - | Mission stop timestamp |
| `created_at` | TIMESTAMP | NO | now() | Record creation time |
| `updated_at` | TIMESTAMP | NO | now() | Record update time |

**Constraints:**
- `ck_missions_status`: status IN ('IDLE','PLANNING','READY','STARTING','RUNNING','PAUSED','COMPLETED','STOPPED','FAILED')
- `ck_missions_radius_positive`: radius_meters > 0

**Indexes:**
- `idx_missions_current_loc` ON `current_location_id`
- `idx_missions_start_loc` ON `start_location_id`
- `idx_missions_status` ON `status`

---

### `mission_locations`

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | INTEGER | NO | SERIAL | Primary key |
| `mission_id` | INTEGER | NO | - | FK → missions.id (CASCADE DELETE) |
| `cellular_tower_id` | VARCHAR(100) | NO | - | Unique tower identifier |
| `cellular_tower_name` | VARCHAR(255) | YES | - | Human-readable tower name |
| `latitude` | FLOAT | NO | - | GPS latitude (-90 to 90) |
| `longitude` | FLOAT | NO | - | GPS longitude (-180 to 180) |
| `upload_batch_id` | VARCHAR(36) | YES | - | UUID batch identifier for bulk uploads |
| `sequence_order` | INTEGER | YES | - | Position in mission route |
| `status` | VARCHAR(20) | NO | 'PENDING' | Current state: PENDING, IN_PROGRESS, VISITED, SKIPPED |
| `distance_from_previous_meters` | FLOAT | YES | - | Distance to previous location |
| `bearing_from_previous_degrees` | FLOAT | YES | - | Bearing to previous location |
| `estimated_arrival_time` | TIMESTAMP | YES | - | ETAs calculated by planner |
| `actual_visit_time` | TIMESTAMP | YES | - | When location was actually visited |
| `scan_session_id` | INTEGER | YES | - | FK → scan_sessions.id (SET NULL on delete) |
| `visited_at` | TIMESTAMP | YES | - | Alias for actual_visit_time |
| `created_at` | TIMESTAMP | NO | now() | Record creation time |
| `updated_at` | TIMESTAMP | NO | now() | Record update time |

**Constraints:**
- `ck_mission_locations_status`: status IN ('PENDING','IN_PROGRESS','VISITED','SKIPPED')
- `ck_mission_locations_latitude_range`: latitude BETWEEN -90 AND 90
- `ck_mission_locations_longitude_range`: longitude BETWEEN -180 AND 180
- `uq_mission_location_tower`: UNIQUE (mission_id, cellular_tower_id)
- `uq_mission_locations_scan_session_id`: UNIQUE (scan_session_id)

**Indexes:**
- `idx_mission_locations_batch` ON `upload_batch_id`
- `idx_mission_locations_mission` ON `mission_id`
- `idx_mission_locations_scan_session` ON `scan_session_id`
- `idx_mission_locations_sequence` ON (`mission_id`, `sequence_order`)
- `idx_mission_locations_status` ON `status`

---

### `mission_logs`

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | INTEGER | NO | SERIAL | Primary key |
| `mission_id` | INTEGER | NO | - | FK → missions.id (CASCADE DELETE) |
| `timestamp` | TIMESTAMP | NO | - | Event timestamp |
| `event_type` | VARCHAR(50) | NO | - | Event type: STARTED, GPS_FIX, SCANNING, ARRIVED, SKIPPED, FAILED, COMPLETED, STOPPED, PAUSED, RESUMED |
| `message` | TEXT | YES | - | Descriptive message |
| `created_at` | TIMESTAMP | NO | now() | Record creation time |
| `updated_at` | TIMESTAMP | NO | now() | Record update time |

**Indexes:**
- `ix_mission_logs_mission_id` ON `mission_id`
- `ix_mission_logs_timestamp` ON `timestamp`

---

### `scan_sessions`

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | INTEGER | NO | SERIAL | Primary key |
| `scan_time` | TIMESTAMP | NO | now() | Scan execution time |
| `tty_port` | VARCHAR(50) | NO | - | USB modem port path |
| `latitude` | FLOAT | YES | - | GPS latitude |
| `longitude` | FLOAT | YES | - | GPS longitude |
| `mission_location_id` | INTEGER | YES | - | FK → mission_locations.id (SET NULL on delete) |
| `created_at` | TIMESTAMP | NO | now() | Record creation time |

**Indexes:**
- `ix_scan_sessions_mission_location_id` ON `mission_location_id`

---

### `scan_results`

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | INTEGER | NO | SERIAL | Primary key |
| `session_id` | INTEGER | NO | - | FK → scan_sessions.id (CASCADE DELETE) |
| `operator_name` | VARCHAR(100) | YES | - | Network operator name |
| `mcc` | VARCHAR(10) | YES | - | Mobile Country Code |
| `mnc` | VARCHAR(10) | YES | - | Mobile Network Code |
| `rat` | VARCHAR(50) | YES | - | Radio Access Type: GSM, UMTS, LTE, 5G |
| `status` | VARCHAR(50) | YES | - | Cell status |

---

### `settings`

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `key` | VARCHAR(100) | NO | - | Setting key (Primary Key) |
| `value` | VARCHAR(500) | YES | - | Setting value |
| `updated_at` | TIMESTAMP | NO | now() | Record update time |

---

## Migration History

| Revision | Date | Description | Tables Affected |
|----------|------|-------------|-----------------|
| `c7db929421f6` | 2026-07-27 | Initial tables | `scan_sessions`, `settings`, `scan_results` |
| `6f2b2fd5c9fe` | 2026-07-31 | Mission tables | `missions`, `mission_locations`, added `mission_location_id` to `scan_sessions` |
| `9306296c5560` | 2026-08-11 | Add mission_logs | `mission_logs` (stamped, table already existed) |

### Current Migration State

```bash
# Check current migration
alembic current
# Output: 9306296c5560 (head)

# View migration history
alembic history
# Output:
#   6f2b2fd5c9fe -> 9306296c5560 (head), add mission_logs table
#   c7db929421f6 -> 6f2b2fd5c9fe, mission_tables
#   <base> -> c7db929421f6, initial tables
```

---

## Database Maintenance

### Backup
```bash
sudo -u postgres pg_dump lte_scanner > lte_scanner_backup_$(date +%Y%m%d).sql
```

### Restore
```bash
sudo -u postgres psql lte_scanner < lte_scanner_backup_20260811.sql
```

### Reset (Development Only)
```bash
sudo -u postgres psql lte_scanner -c "DROP SCHEMA app CASCADE; CREATE SCHEMA app;"
alembic upgrade head
```

# FEATURE_IMPROVEMENT_01_DATABASE_SCHEMA.md

> Mission Planner Epic — Phase 1: Database Schema

| Field | Value |
|-------|-------|
| **Epic** | Mission Planner (Improvement_Epic/) |
| **Phase** | 1 of 10 |
| **Dependencies** | none |
| **Estimated LOC** | ~180 |
| **Complexity** | Low |
| **Status** | Draft |
| **Target** | Dev backend at `~/Cellular-Discovery-Service/backend` |

---

## 📑 Table of Contents

1. [Goals](#1-goals)
2. [Backend Tasks](#2-backend-tasks)
3. [File Changes](#3-file-changes)
4. [API Specs](#4-api-specs)
5. [Database Specs](#5-database-specs)
6. [Acceptance Criteria](#6-acceptance-criteria)

---

## 1. Goals

- Introduce the **2 new tables** that the entire Mission Planner feature depends on:
  - `missions` — mission **header/master**: name, status, radius, tty override, counters, timestamps.
  - `mission_locations` — mission **detail rows**: each row = 1 line from the uploaded CSV (tower id, name, lat, lon). One mission → many locations (**1-to-many**). Also carries the planned visit order + visit status + 1-to-1 scan link.
- Add **one nullable column** `mission_location_id` to the existing `scan_sessions` table.
- Guarantee **zero breaking changes**: all modifications are additive-only (`ADD COLUMN IF NOT EXISTS`, new tables only).
- Establish the relationship graph that later phases (location management, mission CRUD, planner, executor) build on.

> **Design note (merged tables):** In the original `IMPROVEMENT_FEATURE.md` draft, ordered visit sequence lived in a separate `mission_planners` junction table. Under the revised model, `mission_locations` is per-mission CSV data, so the planner columns (`sequence_order`, `status`, `distance_from_previous_meters`, `bearing_from_previous_degrees`, `scan_session_id`, `visited_at`) are **folded into `mission_locations`**. The `mission_planners` table is **removed**.

---

## 2. Backend Tasks

1. [ ] Create SQLAlchemy model `Mission` in `app/db/models/mission.py`.
2. [ ] Create SQLAlchemy model `MissionLocation` in `app/db/models/mission_location.py`.
3. [ ] Add nullable `mission_location_id` column + relationship to `ScanSession` model (`app/db/models/scan_session.py`).
4. [ ] Register all new models in `app/db/models/__init__.py`.
5. [ ] Ensure models import through `app/db/base.py` so Alembic `autogenerate` sees them.
6. [ ] Generate Alembic migration via `alembic revision --autogenerate -m "mission_tables"`.
7. [ ] Review migration and **manually add** `if not column_exists` / `if not table_exists` guards for idempotency.
8. [ ] Resolve circular FK: `mission_locations.mission_id` → `missions` is created inline; `missions.start_location_id` / `current_location_id` → `mission_locations` must be added via `ALTER TABLE ... ADD CONSTRAINT` in the migration.
9. [ ] Run `alembic upgrade head` against dev DB.
10. [ ] Verify indexes, constraints, and FKs exist via psql/query.

---

## 3. File Changes

### New files
| Path | Description |
|------|-------------|
| `backend/app/db/models/mission.py` | `Mission` ORM model (header) |
| `backend/app/db/models/mission_location.py` | `MissionLocation` ORM model (detail rows) |
| `backend/alembic/versions/XXXX_mission_tables.py` | Auto-generated migration + manual guards |

### Modified files
| Path | Description |
|------|-------------|
| `backend/app/db/models/scan_session.py` | Add `mission_location_id` column + `mission_location` relationship |
| `backend/app/db/models/__init__.py` | Import + export new models |

---

## 4. API Specs

**No API changes in this phase.** This phase is data-model only.

Affected *future* phases that depend on these tables: `02_LOCATION_MANAGEMENT`, `03_MISSION_CRUD`, `04_PLANNER_ALGORITHM`, `06_BACKGROUND_EXECUTOR`, `08_MISSION_SCOPED_QUERIES`.

---

## 5. Database Specs

Schema namespace: `app` (same as existing tables).

### 5.1 New table `app.missions` — header / master

Single row per mission; tracks overall state and counters.

```sql
CREATE TABLE app.missions (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'IDLE'
        CHECK (status IN ('IDLE','PLANNING','READY','STARTING','RUNNING','PAUSED','COMPLETED','STOPPED','FAILED')),
    radius_meters INTEGER DEFAULT 20 CHECK (radius_meters > 0),
    tty_port VARCHAR(50),
    start_location_id INTEGER,                -- FK added via ALTER (circular dep)
    current_location_id INTEGER,              -- FK added via ALTER (circular dep)
    total_locations INTEGER DEFAULT 0,
    visited_locations INTEGER DEFAULT 0,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    stopped_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_missions_status ON app.missions(status);
CREATE INDEX idx_missions_start_loc ON app.missions(start_location_id);
CREATE INDEX idx_missions_current_loc ON app.missions(current_location_id);
```

### 5.2 New table `app.mission_locations` — detail rows (CSV upload)

Each row = 1 line from the uploaded CSV for one mission. Also serves as the visit plan.

```sql
CREATE TABLE app.mission_locations (
    id SERIAL PRIMARY KEY,
    mission_id INTEGER NOT NULL REFERENCES app.missions(id) ON DELETE CASCADE,
    cellular_tower_id VARCHAR(100) NOT NULL,          -- External TMS id (unique per mission)
    cellular_tower_name VARCHAR(255),
    latitude FLOAT NOT NULL CHECK (latitude BETWEEN -90 AND 90),
    longitude FLOAT NOT NULL CHECK (longitude BETWEEN -180 AND 180),
    upload_batch_id VARCHAR(36),                      -- Group rows from one CSV upload
    sequence_order INTEGER,                           -- Planned visit order (null = unplanned)
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING'
        CHECK (status IN ('PENDING','IN_PROGRESS','VISITED','SKIPPED')),
    distance_from_previous_meters FLOAT,
    bearing_from_previous_degrees FLOAT,
    estimated_arrival_time TIMESTAMPTZ,
    actual_visit_time TIMESTAMPTZ,
    scan_session_id INTEGER UNIQUE REFERENCES app.scan_sessions(id) ON DELETE SET NULL,
    visited_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT uq_mission_location_tower UNIQUE (mission_id, cellular_tower_id)
);

CREATE INDEX idx_mission_locations_mission ON app.mission_locations(mission_id);
CREATE INDEX idx_mission_locations_sequence ON app.mission_locations(mission_id, sequence_order);
CREATE INDEX idx_mission_locations_status ON app.mission_locations(status);
CREATE INDEX idx_mission_locations_scan_session ON app.mission_locations(scan_session_id);
CREATE INDEX idx_mission_locations_batch ON app.mission_locations(upload_batch_id);
```

### 5.3 Circular FK resolution

`missions` ↔ `mission_locations` reference each other. Create in this order:

```sql
-- Step 1: mission_locations created first (its mission_id FK targets missions,
--         which does not exist yet) → so create missions WITHOUT the two FK columns,
--         then ALTER them in AFTER mission_locations exists.
-- (See 5.1: start_location_id / current_location_id are plain INTEGER at CREATE time.)

-- Step 2: after app.mission_locations exists:
ALTER TABLE app.missions
    ADD CONSTRAINT fk_missions_start_location
    FOREIGN KEY (start_location_id) REFERENCES app.mission_locations(id) ON DELETE SET NULL;

ALTER TABLE app.missions
    ADD CONSTRAINT fk_missions_current_location
    FOREIGN KEY (current_location_id) REFERENCES app.mission_locations(id) ON DELETE SET NULL;
```

### 5.4 Modified table `app.scan_sessions` (additive-only)

```sql
ALTER TABLE app.scan_sessions
    ADD COLUMN IF NOT EXISTS mission_location_id INTEGER
        REFERENCES app.mission_locations(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS ix_scan_sessions_mission_location_id
    ON app.scan_sessions(mission_location_id);
```

### 5.5 Relationship summary

```
missions          1 ──── N mission_locations   (ON DELETE CASCADE; mission_locations.mission_id)
mission_locations 1 ──── 1 scan_sessions        (mission_locations.scan_session_id UNIQUE, 1-to-1)
scan_sessions     1 ──── 1 mission_locations    (scan_sessions.mission_location_id nullable, back-ref)
missions          1 ──── 1 mission_locations    (start_location_id / current_location_id, SET NULL)
```

**Key constraints to enforce:**

- `mission_locations.mission_id` NOT NULL + `ON DELETE CASCADE` → deleting a mission removes its location rows.
- `mission_locations.scan_session_id` is `UNIQUE` → each scan session belongs to at most one location visit.
- `scan_sessions.mission_location_id` is nullable → legacy scans remain valid (backward compatible).
- `UNIQUE (mission_id, cellular_tower_id)` → duplicate tower ids within one mission are impossible (UPSERT target).
- `missions.status` uses a CHECK constraint → state machine enforced at DB level.
- `mission_locations.latitude/longitude` CHECK → invalid coordinates rejected at DB level.
- `missions.start_location_id`/`current_location_id` → SET NULL when a location row is deleted.

### 5.6 ORM model mapping notes

- Use `schema="app"` in `__table_args__` (same pattern as existing models).
- Use `server_default=func.now()` for `created_at` / `updated_at` (same pattern as `ScanSession`).
- `MissionLocation.mission_id` → `ForeignKey("app.missions.id", ondelete="CASCADE")`, `nullable=False`.
- `MissionLocation.scan_session_id` → `ForeignKey("app.scan_sessions.id", ondelete="SET NULL")`, `unique=True`.
- `ScanSession.mission_location_id` → `ForeignKey("app.mission_locations.id", ondelete="SET NULL")`, `nullable=True`.
- `Mission.start_location_id` / `current_location_id` → `ForeignKey("app.mission_locations.id", ondelete="SET NULL")`.
- Relationships:
  - `Mission.locations` → `uselist=True`, `cascade="all, delete-orphan"`, `order_by="MissionLocation.sequence_order"`.
  - `MissionLocation.mission` → `uselist=False`, `back_populates="locations"`.
  - `MissionLocation.scan_session` → `uselist=False`, `back_populates="mission_location"`.
  - `ScanSession.mission_location` → `uselist=False`, `back_populates="scan_session"`.

### 5.7 Migration idempotency guards

```python
def upgrade() -> None:
    op.create_table("missions", ...)             # status CHECK, FKs added after
    op.create_table("mission_locations", ...)    # mission_id FK inline
    op.create_foreign_key("fk_missions_start_location", ...)
    op.create_foreign_key("fk_missions_current_location", ...)
    # scan_sessions column with existence check:
    conn = op.get_bind()
    result = conn.execute(
        text("SELECT 1 FROM information_schema.columns "
             "WHERE table_schema='app' AND table_name='scan_sessions' AND column_name='mission_location_id'")
    )
    if result.scalar() is None:
        op.add_column("scan_sessions", sa.Column("mission_location_id", sa.Integer(), nullable=True))
        op.create_foreign_key(
            "fk_scan_sessions_mission_location_id_mission_locations",
            "scan_sessions", "mission_locations", ["mission_location_id"], ["id"],
            source_schema="app", referent_schema="app", ondelete="SET NULL",
        )
        op.create_index("ix_scan_sessions_mission_location_id", "scan_sessions", ["mission_location_id"], schema="app")


def downgrade() -> None:
    op.drop_constraint("fk_missions_current_location", "missions", type_="foreignkey", schema="app")
    op.drop_constraint("fk_missions_start_location", "missions", type_="foreignkey", schema="app")
    op.drop_column("scan_sessions", "mission_location_id", schema="app")
    op.drop_table("mission_locations", schema="app")
    op.drop_table("missions", schema="app")
```

---

## 6. Acceptance Criteria

### 6.1 Unit tests

| # | Test | Expectation |
|---|------|-------------|
| U01 | `Mission` model mapped to `app.missions` | Status CHECK rejects invalid value (e.g. `'NONSENSE'`) on flush/commit |
| U02 | `MissionLocation` model mapped to `app.mission_locations` | `mission_id` required; `UNIQUE (mission_id, cellular_tower_id)` enforced |
| U03 | 1-to-many | Creating a mission + 3 location rows yields `mission.locations` count 3 |
| U04 | `ScanSession.mission_location_id` | Nullable; legacy row insert without it succeeds |
| U05 | Relationship navigation | `location.mission`, `location.scan_session`, `mission.locations` order_by sequence |
| U06 | FK cascade | Deleting a mission deletes its location rows (CASCADE) |
| U07 | 1-to-1 uniqueness | Assigning same `scan_session_id` to 2 location rows raises IntegrityError |
| U08 | Coordinate CHECK | Inserting `latitude=95` raises IntegrityError |
| U09 | Circular FK | `mission.start_location_id` / `current_location_id` set + cleared on location delete (SET NULL) |
| U10 | Migrations upgrade + downgrade round-trip | `alembic upgrade head` then `downgrade base` then `upgrade head` leaves clean state |

### 6.2 End-to-end / migration tests

| # | Test | Expectation |
|---|------|-------------|
| E01 | Run `alembic upgrade head` on a **fresh** DB | Both new tables + new column created, no errors |
| E02 | Run `alembic upgrade head` on the **existing dev DB** (with legacy rows) | Idempotent; existing `scan_sessions` rows untouched; column added with NULL |
| E03 | Run `alembic upgrade head` a **second time** | No-op, no error (idempotency guards work) |
| E04 | psql verification query | `SELECT column_name FROM information_schema.columns WHERE table_schema='app' AND table_name='scan_sessions' AND column_name='mission_location_id'` returns 1 row |
| E05 | Run `pytest tests/test_database.py` and full suite | All existing tests still pass (no regressions) |
| E06 | App startup (`uvicorn`) | Boots cleanly; models import without circular-import errors |

### 6.3 Verification commands

```bash
cd ~/Cellular-Discovery-Service/backend

# 1. Generate migration
.venv/bin/alembic revision --autogenerate -m "mission_tables"

# 2. Review + apply manual guards, then:
.venv/bin/alembic upgrade head

# 3. Verify tables
.venv/bin/python -c "from app.db.database import engine; from sqlalchemy import inspect; \
print(sorted(inspect(engine).get_table_names(schema='app')))"

# 4. Verify column
.venv/bin/python -c "from app.db.database import engine; from sqlalchemy import text; \
r=engine.connect().execute(text(\"SELECT column_name FROM information_schema.columns WHERE table_schema='app' AND table_name='scan_sessions' AND column_name='mission_location_id'\")); \
print('OK' if r.scalar() else 'MISSING')"

# 5. Full test suite (no regressions)
.venv/bin/pytest -q
```

---

### Checklist

- [ ] `Mission` and `MissionLocation` models created and imported through `app/db/models/__init__.py`
- [ ] `scan_sessions.mission_location_id` added (nullable)
- [ ] Circular FK resolved (ALTER TABLE for `missions.start/current_location_id`)
- [ ] Migration generated, reviewed, guarded, applied
- [ ] Downgrade path tested
- [ ] Existing tests pass
- [ ] This doc's Acceptance Criteria satisfied

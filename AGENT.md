# AGENT.md

# ⚠️ CRITICAL: RTL-SDR MIGRATION - NO lte-discovery ALLOWED ⚠️

## MASAALUKU: JANGAN PERNAH PAKAI `lte-discovery` LAGI!

**Sistem ini TELAH BERALIH KE `lte-scan` CLI BERBASIS RTL-SDR.**

Semua referensi ke `lte-discovery`, `tty_port`, `/dev/ttyUSB0` untuk scan LTE **HARUS DIHAPUS**.

### Command yang Valid (HANYA INI):
```bash
lte-scan balance 8 --json --gain 43
lte-scan fast 5 --json --gain 43
lte-scan full <band> --json --gain 43
```

### Hardware yang Digunakan:
- ✅ **RTL-SDR Dongle** (Realtek RTL2832U) - Terdeteksi di `/dev/bus/usb/*`
- ✅ GPS UART via `/dev/ttyAMA0` (UBLOX NEO M6)
- ❌ **TIDAK ADA** USB Modem LTE untuk scanning

### Output Format Baru:
```json
{
  "scan_info": { "band": 8, "gain_db": 43, "mode": "balance" },
  "cells": [
    { "mcc": 510, "mnc": 10, "operator": "Telkomsel", "pci": 1, "rsrp": -15.2 }
  ]
}
```

**Lihat MIGRATION_PLAN.md untuk detail lengkap.**

---

# RTL-SDR LTE Network Discovery Web Backend

**Backend Framework:** Python FastAPI  
**Operating System:** Raspberry Pi OS 64-bit (Headless)  
**Target Hardware:** Raspberry Pi 5  
**Database:** PostgreSQL  
**ORM:** SQLAlchemy 2.x  
**Migration:** Alembic  
**Validation:** Pydantic v2  
**Architecture:** Clean Architecture + KISS  
**Python:** 3.12+

---

# Objective

Develop a REST API backend for the RTL-SDR LTE Network Discovery Web Application.

The backend **DOES NOT** implement LTE scanning itself.

The backend acts as an orchestration layer that:

- receives requests from the frontend
- executes the existing CLI application
- parses CLI output
- stores scan history
- provides REST API
- provides GPS location
- manages application settings
- provides future realtime WebSocket services

The existing CLI project is considered the authoritative LTE scanning engine.

---

# Target Platform

The backend application is designed exclusively for

- Raspberry Pi OS 64-bit
- Raspberry Pi 5
- Linux
- Headless environment

The application SHALL NOT assume

- Windows
- macOS
- Docker
- Kubernetes

The backend runs directly on Raspberry Pi OS using a native Python Virtual Environment.

Production deployment SHALL use:

- Python Virtual Environment
- systemd service

---

# Design Principles

Always follow these principles.

- KISS (Keep It Simple)
- Clean Architecture
- Modular
- Composition over Inheritance
- Dependency Injection (manual)
- Small classes
- Small functions
- Strong typing
- SOLID where practical
- Explicit dependencies
- No magic
- Easily testable
- No duplicated logic

---

# Database Configuration

The PostgreSQL database is prepared manually.

The backend application is **NOT** responsible for creating the database or PostgreSQL schema.

The developer is responsible for creating

Database

```
lte_scanner
```

Database User

```
lte_scanner
```

Password

```
engen1us
```

PostgreSQL Schema

```
app
```

The backend SHALL connect to the existing database and create all application tables inside the existing PostgreSQL schema.

---

# Environment Configuration

The repository SHALL contain

```
.env.example
```

Developers SHALL copy

```
.env.example
```

to

```
.env
```

before running the application.

Required environment variables

```env
DATABASE_HOST=localhost
DATABASE_PORT=5432
DATABASE_NAME=lte_scanner
DATABASE_USER=lte_scanner
DATABASE_PASSWORD=engen1us
DATABASE_SCHEMA=app

GPS_PROVIDER=cli           # Valid: cli | mock | moving_mock | serial
DEFAULT_GPS_TTY=/dev/ttyAMA0

LTE_SCAN_COMMAND=lte-scan
LTE_SCAN_BANDS=5,8         # Comma-separated LTE bands to scan
LTE_SCAN_GAIN_DB=43
LTE_SCAN_MODE=balance      # fast | balance | full
SCAN_TIMEOUT=90

LOG_LEVEL=INFO

APP_ENV=production
APP_HOST=0.0.0.0
APP_PORT=8000

TIMEZONE=Asia/Jakarta
```

All application configuration MUST come from environment variables.

No hardcoded configuration is allowed.

---

# ORM and Migration Policy

SQLAlchemy ORM is the single source of truth for the database structure.

Every application table SHALL be defined using SQLAlchemy Declarative ORM.

The backend SHALL NEVER define tables using raw SQL.

Alembic SHALL generate and manage every database migration.

The backend SHALL NEVER call

```
Base.metadata.create_all()
```

under any circumstance.

Database initialization workflow

```
SQLAlchemy ORM Models

        │

        ▼

Alembic Revision

        │

        ▼

Alembic Upgrade

        │

        ▼

PostgreSQL
```

Every schema modification MUST include

- SQLAlchemy model update
- Alembic migration
- Repository update
- Unit tests if applicable

---

# PostgreSQL Schema

Every SQLAlchemy model MUST explicitly define

```python
__table_args__ = {
    "schema": "app"
}
```

No application table may be created inside

```
public
```

schema.

---

# Deployment Policy

The backend SHALL run natively on Raspberry Pi OS 64-bit.

Container-based deployment is outside the scope of this project.

Deployment workflow

```
git clone

↓

python -m venv .venv

↓

source .venv/bin/activate

↓

pip install -r requirements.txt

↓

cp .env.example .env

↓

alembic upgrade head

↓

systemctl start lte-scanner.service
```

---

# Startup

The backend SHALL automatically start after Raspberry Pi boots.

Deployment SHALL include a systemd service.

Example

```
lte-scanner.service
```

The service SHALL

- use Python Virtual Environment
- load environment variables from `.env`
- automatically restart on failure
- start after PostgreSQL service
- execute Uvicorn as the application server

---

# Architecture

```
                 REST API
                     │
             FastAPI Controllers
                     │
               Application Service
                     │
     ┌───────────────┴───────────────┐
     │                               │
 CLI Adapter                  GPS Provider
     │                               │
CLI Process               Mock / Serial GPS
     │
RTL-SDR LTE Discovery CLI
```

Business logic must never execute shell commands directly.

Shell execution belongs only inside

```
CLIAdapter
```

---

# Development Phases

## Phase 1

Project Skeleton

Implement

- FastAPI
- PostgreSQL
- SQLAlchemy
- Alembic
- Configuration
- Logging
- Python Virtual Environment
- systemd service

No LTE functionality.

---

## Phase 2

CLI Adapter

Responsible for executing

```
lte-scan balance 8 --json --gain 43
```

Responsibilities

- execute CLI
- timeout handling
- stdout capture
- stderr capture
- JSON parsing
- exception mapping

Only CLIAdapter may execute subprocesses.

---

## Phase 3

GPS Provider

GPS must be provider-based.

Interface

```
GPSProvider
```

Implementations

```
MockGPSProvider

SerialGPSProvider
```

Current implementation

Latitude

```
-6.150676643667096
```

Longitude

```
106.89665223346297
```

Update interval

```
10 seconds
```

The rest of the application must never know where GPS coordinates originate.

---

## Phase 4

Scan Service

Workflow

```
Receive Request

↓

Read GPS

↓

Execute CLI

↓

Parse CLI Result

↓

Store Database

↓

Return API Response
```

The Scan Service orchestrates the workflow.

JSON parsing belongs exclusively inside CLIAdapter.

---

## Phase 5

History Service

Provide

- Pagination
- Searching
- Sorting

Search by

- Operator
- MCC
- MNC
- RAT
- Date

---

## Phase 6

Settings Service

Manage

- LTE band to scan
- GPS provider
- Scan timeout
- Future application settings

---

## Phase 7

Realtime

Future implementation

```
/ws/gps

/ws/scan
```

---

# Folder Structure

```
backend/

app/

    api/
        routers/
        dependencies/

    services/

    repositories/

    cli/

    gps/

    db/
        database.py
        session.py
        base.py

        models/
            scan_session.py
            scan_result.py
            setting.py

    schemas/

    config/

    core/

    utils/

tests/

alembic/

scripts/
    install.sh
    run.sh
    update.sh

.env.example
```

---

# Layers

## API Layer

Responsible only for

- Request validation
- Response generation
- Dependency Injection

No business logic.

---

## Service Layer

Contains application use cases.

Examples

- ScanService
- HistoryService
- SettingsService

---

## Repository Layer

Responsible only for database access.

No business logic.

---

## CLI Layer

Responsible only for

- subprocess
- timeout
- stdout
- stderr
- parsing

---

## GPS Layer

Responsible only for GPS providers.

---

# REST API

## POST

```
/api/v1/scan
```

Request

```json
{}
```

Note: Scan uses `LTE_SCAN_COMMAND` and `LTE_SCAN_BANDS` from environment. No tty_port needed.

Workflow

```
GPS

↓

CLI

↓

Database

↓

Response
```

---

## GET

```
/api/v1/scans
```

Supports

- page
- page_size
- search
- sort

---

## GET

```
/api/v1/scans/{id}
```

Return complete scan detail.

---

## DELETE

```
/api/v1/scans/{id}
```

Delete scan history.

---

## GET

```
/api/v1/settings
```

---

## PUT

```
/api/v1/settings
```

---

# Database Entities

## scan_sessions

```
id
scan_time
band
latitude
longitude
created_at
```

---

## scan_results

```
id
session_id
operator_name
mcc
mnc
rat
status
```

Relationship

```
One Scan Session

↓

Many Scan Results
```

---

## settings

```
key
value
updated_at
```

---

# Dependency Rules

Allowed

```
API

↓

Service

↓

Repository

↓

Database
```

Allowed

```
Service

↓

CLI Adapter
```

Allowed

```
Service

↓

GPS Provider
```

Forbidden

```
API

↓

Database
```

Forbidden

```
Repository

↓

CLI
```

Forbidden

```
CLI

↓

Database
```

Forbidden

```
Repository

↓

GPS
```

---

# Error Handling

Never expose

- traceback
- subprocess stderr
- SQLAlchemy exception

Always return standardized API responses.

---

# Logging

Log

- API requests
- CLI execution time
- timeout
- database errors

Never log

- passwords
- secrets

---

# Testing

Unit Tests

- Services
- CLI Adapter
- GPS Provider
- Repository

Integration Tests

- REST API
- PostgreSQL

The test suite MUST NOT require an RTL-SDR dongle.

CLI execution SHALL be mocked.

---

# Future Extensions

- Serial GPS
- Scheduled scan
- Automatic scan
- WebSocket
- CSV Export
- JSON Export
- Authentication
- User Management
- Prometheus Metrics
- Health Check Endpoint

---

# Definition of Done

A feature is complete only when

- implementation finished
- typed
- tested
- documented
- follows folder structure
- follows dependency rules
- Alembic migration generated
- passes lint
- passes unit tests
- contains no duplicated logic
- contains no hardcoded configuration
- code reviewed


---

# Runtime Service Topology — REMEMBER THIS

> **IMPORTANT:** There are **TWO** independent backend services running on this host. They are **different codebases** on **different ports** and **must BOTH be running** during frontend development.

| Service Name                       | Backend Folder                                                                                              | Port  | Venv / Path                                        |
| ---------------------------------- | ----------------------------------------------------------------------------------------------------------- | ----- | -------------------------------------------------- |
| `lte-scanner-production.service`   | `/home/pi/production-backend/Cellular-Discovery-Service`                                                    | 8000  | `.venv_prod/bin/uvicorn` (production frozen build) |
| `lte-scanner.service`              | `/home/pi/Cellular-Discovery-Service`                                                                       | 8001  | `backend/.venv/bin/uvicorn` (active dev repo)      |

**Key rules:**

- Port 8000 belongs **exclusively** to `lte-scanner-production.service` deployed under `/home/pi/production-backend/Cellular-Discovery-Service` (formerly referenced as `/home/pi/production/service/Cellular-Discovery-Service`).
- Port 8001 belongs **exclusively** to `lte-scanner.service` deployed under `/home/pi/Cellular-Discovery-Service` (the active repo the agent is working in).
- The two services are **separate codebases** — they do not share venv, do not share `.env`, do not share process.
- **Both services MUST be `active (running)` while frontend development is in progress** for compatibility with the remaining FE work.
- If asked about "the service", check `ss -tlnp` to identify which port is listening before assuming.
- DO NOT confuse `lte-scanner-production.service` (port 8000, production folder) with `lte-scanner.service` (port 8001, dev folder).

**Verification commands:**

```bash
# Both services must show 'active (running)'
systemctl status lte-scanner-production.service --no-pager
systemctl status lte-scanner.service --no-pager

# Both ports must show LISTEN
ss -tlnp | grep -E "8000|8001"

# Quick health probes
curl -s http://localhost:8000/docs -o /dev/null -w "8000 docs: HTTP %{http_code}\n"
curl -s http://localhost:8001/docs -o /dev/null -w "8001 docs: HTTP %{http_code}\n"
```

If only one is running, bring the other one up:

```bash
sudo systemctl enable lte-scanner.service
sudo systemctl start  lte-scanner.service
```

(Ditto for `lte-scanner-production.service` when applicable.)

**Frontend wiring (Nuxt):**

```env
NUXT_PUBLIC_API_BASE=http://localhost:8001     # dev FE → dev BE
# During production FE tests: http://<host>:8000
```

---

# Pagination Fix (2026-08-10)

## Fixed: Mission Logs Pagination

**Issue:** Page > total_pages returned last page's data instead of empty results.

**Root Cause:** 
1. Missing import: `MissionLogsResponse` from wrong path
2. `page = max(1, min(page, total_pages))` clamped page before checking

**Fix in** `app/core/mission_executor.py`:
```python
# ✅ CORRECT - Check BEFORE clamping
if page > total_pages:
    return MissionLogsResponse(
        items=[],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages
    )
# Removed: page = max(1, min(page, total_pages))  # WRONG - clamps page
```

**Import fix:**
```python
from app.schemas.mission_log import MissionLogsResponse  # ✅ CORRECT
# NOT: from app.db.models.mission_log import MissionLogsResponse  # WRONG
```

**Tested (Mission 2158 - 1,357 logs):**
| Page | Result |
|------|--------|
| 137 | ✅ Empty (correct) |
| 999 | ✅ Empty (correct) |
| 136 | ✅ 7 items (last page) |
| 1 | ✅ 10 items (first page) |

**Commits:**
- `e4ed77e` - fix(pagination): return empty results for page > total_pages


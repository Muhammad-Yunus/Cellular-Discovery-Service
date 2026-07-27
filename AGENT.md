# AGENT.md

# USB Modem LTE Network Discovery Web Backend

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

Develop a REST API backend for the USB Modem LTE Network Discovery Web Application.

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

GPS_PROVIDER=mock
DEFAULT_TTY=/dev/ttyUSB0
SCAN_TIMEOUT=30

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
USB Modem LTE Discovery CLI
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
lte-discovery scan \
    --port /dev/ttyUSB0 \
    --json
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

- Default USB modem
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
{
    "tty": "/dev/ttyUSB0"
}
```

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
tty_port
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

The test suite MUST NOT require a physical USB modem.

CLI execution SHALL be mocked.

---

# Future Extensions

- Multiple modem support
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

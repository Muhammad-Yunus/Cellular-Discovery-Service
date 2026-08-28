# Cellular Discovery Service

<p align="center">
  <img src="https://img.shields.io/badge/python-3.12+-blue?logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/FastAPI-0.115.x-red" alt="Web framework">
  <img src="https://img.shields.io/badge/SQL%20Alchemy-2.0.x-orange" alt="ORM">
  <img src="https://img.shields.io/badge/PostgreSQL-15+-blue?logo=postgresql&logoColor=white" alt="Database">
  <img src="https://img.shields.io/badge/Raspberry%20Pi-5-C51A4A?logo=raspberrypi&logoColor=white">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
  <img src="https://img.shields.io/badge/status-active-brightgreen" alt="Status">
</p>

**REST API backend for RTL-SDR LTE Network Discovery Web Application** — orchestrates CLI-based LTE scans using `lte-scan` (RTL-SDR dongle), mission planning with GPS navigation, stores scan history in PostgreSQL, and provides realtime updates via WebSocket. Runs on Raspberry Pi OS 64-bit.

---

## 🏗️ Architecture Diagram

```
                   REST API (Web UI)
                        │
                FastAPI Controllers (Routers)
                        │
                  Application Service Layer
                        │
        ┌───────────────┼───────────────┬────────────────┐
        │               │               │                │
   Scan Service     Mission        History       Settings
        │               Service       Service       Service
        │               │
   CLI Adapter     Mission           Location
        │            Planner        Repository
   GPS Provider   Executor
        │
  ┌─────┼─────┬──────────┐
  │     │     │          │
Mock  Serial  CLI    WebSocket
Provider Provider Provider Manager
  │     │     │          │
  └─────┴─────┴──────────┘
        │
   PostgreSQL (app schema)
```

**Clean Architecture + KISS Principle** — Layers never violate dependency rules:
- API (Routers) → Service → Repository → Database
- Services may also use CLI Adapter, GPS Provider, or WebSocket Manager
- Core subsystems: Mission Executor, Test Management, Exception handling

---

## 📁 Project Structure

```
cellular-discovery-service/
├── backend/                     # Python backend application
│   ├── app/                     # Source code
│   │   ├── api/                 # FastAPI routers & dependencies
│   │   │   ├── routers/         # API route handlers (13 modules)
│   │   │   └── dependencies/    # Shared dependencies
│   │   ├── services/            # Business logic
│   │   ├── repositories/        # Data access layer
│   │   ├── cli/                 # CLI adapter (subprocess execution)
│   │   ├── gps/                 # GPS providers (Mock/Serial/CLI)
│   │   ├── core/                # Core subsystems
│   │   │   ├── mission_executor.py   # Live mission execution
│   │   │   ├── websocket_manager.py  # WebSocket connections
│   │   │   └── exceptions.py         # Custom exceptions
│   │   ├── db/                  # SQLAlchemy ORM models
│   │   ├── schemas/             # Pydantic request/response models
│   │   ├── config/              # Environment configuration
│   │   ├── utils/               # Utility functions
│   │   └── main.py              # Entry point
│   ├── tests/                   # Unit, integration, E2E tests (~120+ tests)
│   ├── alembic/                 # Database migrations
│   ├── scripts/                 # run.sh, install.sh, update.sh
│   ├── requirements.txt         # Python dependencies
│   ├── pyproject.toml           # Project metadata
│   └── .env.example             # Environment template
├── Doc/                         # Markdown documentation
│   ├── API.md                   # Complete API reference
│   ├── DEPLOYMENT.md            # Deployment guide
│   ├── ARCHITECTURE.md          # Architecture overview
│   ├── CONTRIBUTING.md          # Contribution guidelines
│   ├── README.md                # Docs folder summary
│   └── SCHEMA.md                # Database schema & migration history
├── AGENT.md                     # Original project specification
├── E2E_TEST_REPORT.md           # E2E test report
├── UNIT_TEST_REPORT.md          # Unit test report
├── lte-scanner.service          # systemd service unit
├── .git/                        # Git repository
└── .editorconfig                # Coding style config
```

---

## 🔧 Quick Start

```bash
# Clone repository
git clone <repo-url>
cd cellular-discovery-service/backend

# Setup virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your settings

# Apply database migrations
alembic upgrade head

# Run development server (default port 8000, dev uses 8001)
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Or use script
./scripts/run.sh
```

Visit `http://localhost:8000/docs` for interactive API documentation.

---

## 🔨 Build & Package

### Development Installation (Source)

```bash
# Install all dev + runtime deps
pip install -r requirements.txt
```

### Wheel Distribution (Optional)

```bash
pip install wheel
python setup.py bdist_wheel   # or `python -m wheel`
# Artifacts go into dist/ directory
```

---

## ▶️ Run Instructions

### Development Mode (Hot Reload)

```bash
source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
# OR (dev override to port 8001)
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
# OR
./scripts/run.sh
```

Visit `http://localhost:8000/docs`.

### Background Process

```bash
nohup uvicorn app.main:app --host 0.0.0.0 --port 8000 &
```

### Systemd Daemon (Production)

```bash
sudo cp lte-scanner.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable lte-scanner.service
sudo systemctl start lte-scanner.service
sudo systemctl status lte-scanner.service
sudo journalctl -u lte-scanner.service -f
```

---

## 🚀 Production Deployment (Systemd)

Create `/etc/systemd/system/lte-scanner.service`:

```ini
[Unit]
Description=LTE Scanner Backend
After=network.target postgresql.service

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/Cellular-Discovery-Service/backend
EnvironmentFile=/home/pi/Cellular-Discovery-Service/backend/.env
ExecStart=/home/pi/Cellular-Discovery-Service/backend/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Apply the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable lte-scanner.service
sudo systemctl start lte-scanner.service
sudo systemctl status lte-scanner.service
sudo journalctl -u lte-scanner.service -f
```

Or copy the service file from this repo:

```bash
sudo cp /home/pi/Cellular-Discovery-Service/lte-scanner.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl restart lte-scanner.service
```

---

## 🧪 Testing

```bash
# Run all tests
pytest backend/tests/ -v

# Run with coverage report
pytest backend/tests/ --cov=app --cov-report=mismatch

# Generate HTML coverage report
pytest backend/tests/ --cov=app --cov-report=html
open htmlcov/index.html

# Run specific test file
pytest backend/tests/test_missions.py -v
pytest backend/tests/test_services.py -v
pytest backend/tests/test_e2e.py -v
pytest backend/tests/test_websocket.py -v
pytest backend/tests/test_executor.py -v

# Linting (optional)
pip install flake8 black
flake8 app/
black --check app/
```

**Test Coverage:** ~95% across core modules  
**Integration Tests:** All passing with SQLite test database (emulates PostgreSQL structure)

---

## 📋 API Endpoints

### Health & Docs
| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/health` | Health check endpoint |
| `GET`  | `/docs` | Interactive OpenAPI docs |
| `GET`  | `/openapi.json` | OpenAPI spec JSON |

### Scan Management
| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/scan` | Trigger LTE network scan |
| `GET`  | `/api/v1/scans` | List scan history (paginated, filterable, sortable) |
| `GET`  | `/api/v1/scans/{result_id}` | Get scan detail |
| `DELETE` | `/api/v1/scans/{result_id}` | Delete scan entry |
| `GET`  | `/api/v1/scans/export` | Export scans (CSV/JSON) |

### Mission Management
| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/missions` | Create mission |
| `GET`  | `/api/v1/missions` | List missions (paginated, filterable, sortable) |
| `GET`  | `/api/v1/missions/{id}` | Get mission detail |
| `PATCH` | `/api/v1/missions/{id}` | Update mission |
| `DELETE` | `/api/v1/missions/{id}` | Delete mission |

### Mission Locations
| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/api/v1/missions/{id}/locations` | List mission locations |
| `POST` | `/api/v1/missions/{id}/locations/upload` | Upload locations (CSV) |
| `GET`  | `/api/v1/missions/{id}/locations/{loc_id}` | Get location detail |
| `DELETE` | `/api/v1/missions/{id}/locations/{loc_id}` | Delete location |
| `POST` | `/api/v1/missions/{id}/locations/bulk-delete` | Bulk delete locations |

### Mission Execution
| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/missions/{id}/start` | Start mission |
| `POST` | `/api/v1/missions/{id}/pause` | Pause mission |
| `POST` | `/api/v1/missions/{id}/resume` | Resume mission |
| `POST` | `/api/v1/missions/{id}/stop` | Stop mission |
| `GET`  | `/api/v1/missions/{id}/status` | Get mission status |
| `POST` | `/api/v1/missions/{id}/plan` | Plan mission route |
| `GET`  | `/api/v1/missions/{id}/route` | Get planned route |
| `POST` | `/api/v1/missions/{id}/route/skip` | Skip route location |
| `POST` | `/api/v1/missions/{id}/route/reorder` | Reorder route |
| `GET`  | `/api/v1/missions/{id}/scans` | List mission scans |
| `GET`  | `/api/v1/missions/{id}/scans/export` | Export mission scans |
| `GET`  | `/api/v1/missions/{id}/logs` | Get paginated mission logs (default 10/page, sorted by timestamp DESC) |

### Device
| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/api/v1/device/location` | Get current device GPS location (independent, no mission required) |

### Settings
| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/api/v1/settings` | List app settings |
| `PUT`  | `/api/v1/settings` | Update app settings |

### WebSocket
| Method | Path | Description |
|--------|------|-------------|
| `WS`   | `/ws/gps` | Realtime GPS updates |
| `WS`   | `/ws/scan` | Scan event events |
| `WS`   | `/ws/mission` | Mission lifecycle events |

### Test Management (Development Only)
| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/test/missions` | List test missions |
| `POST` | `/test/missions/cleanup` | Bulk cleanup test missions |
| `DELETE` | `/test/missions/{id}` | Force delete test mission |
| `POST` | `/test/missions/{id}/force-stop` | Force stop test mission |
| `GET/PUT` | `/test/cli/mock/fail` | Mock CLI failure state |
| `GET/PUT` | `/test/gps/mock/fail` | Mock GPS failure state |

---

## 🖥️ Environment Configuration

Create `.env` from `.env.example`:

```env
DATABASE_HOST=localhost
DATABASE_PORT=5432
DATABASE_NAME=lte_scanner
DATABASE_USER=lte_scanner
DATABASE_PASSWORD=<your_password>
DATABASE_SCHEMA=app

GPS_PROVIDER=cli           # Valid: cli | mock | moving_mock | serial
DEFAULT_GPS_TTY=/dev/ttyAMA0

LTE_SCAN_COMMAND=lte-scan
LTE_SCAN_BANDS=5,8         # Comma-separated list of LTE bands to scan
LTE_SCAN_GAIN_DB=43
LTE_SCAN_MODE=balance      # fast | balance | full
SCAN_TIMEOUT=90

LOG_LEVEL=INFO             # DEBUG | INFO | WARNING | ERROR

APP_ENV=production
APP_HOST=0.0.0.0
APP_PORT=8000

TIMEZONE=Asia/Jakarta
```

All configuration is loaded dynamically at runtime from environment variables. **No hardcoded values allowed.**

---

## 📡 GPS Providers

| Provider | Description | Config |
|----------|-------------|--------|
| `MockGPSProvider` | Returns fixed Jakarta coordinates (-6.15, 106.90) | `GPS_PROVIDER=mock` |
| `SerialGPSProvider` | Reads NMEA GGA sentences from serial port | `GPS_PROVIDER=serial`, set `DEFAULT_GPS_TTY` (e.g. `/dev/ttyACM0`) |
| `CLIGPSProvider` | Executes external GPS CLI binary and parses output | `GPS_PROVIDER=cli`, configure `command`, `device`, `baud`, `timeout` |

The SerialGPSProvider parses `$GPGGA` sentences to extract latitude/longitude coordinates. Altitude, fix quality, and satellite count are supported but not stored.

---

## 🔒 Security Notes

- **No authentication** implemented (internal LAN device only)
- **Never expose** `/api/` endpoints directly to public internet without reverse proxy + auth
- Passwords are read from `.env` (add to `.gitignore`!)
- Log levels should be `INFO` or higher in production
- TLS/HTTPS recommended behind nginx/apache reverse proxy

---

## 🚧 Future Extensions

- [x] GPS Provider Interface ✅
- [x] WebSocket Realtime Updates ✅
- [x] Mission System (create, plan, execute) ✅
- [x] Location Upload (CSV) ✅
- [x] Route Planning & Navigation ✅
- [x] Mission Scans & Logs ✅
- [x] Mission Logs Pagination ✅
- [x] Device Location Endpoint (independent) ✅
- [x] Test Management Endpoints ✅
- [x] Health Check Endpoint ✅
- [x] CSV/JSON Export for missions ✅
- [x] Multi-band LTE Scanning (RTL-SDR) ✅
- [ ] JWT Authentication
- [ ] Prometheus Metrics
- [ ] Scheduled/Automated Scans

---

## 🤝 Contributions

Contributions welcome! Please see [`Doc/CONTRIBUTING.md`](Doc/CONTRIBUTING.md) for guidelines.

To add a new feature:
1. Follow Clean Architecture layering rules
2. Add type hints throughout
3. Write unit/integration tests
4. Generate Alembic migration if DB changes needed
5. Update documentation

---

## 📄 License

MIT License — See `LICENSE` file for details.

---

## ⚙️ Technologies Used

| Tech | Version | Purpose |
|------|---------|---------|
| **Python** | 3.12+ | Language |
| **FastAPI** | 0.115.x | Web framework |
| **SQLAlchemy** | 2.0.x | ORM |
| **Alembic** | 1.14.x | Database migrations |
| **Pydantic** | 2.10.x | Validation & serialization |
| **PostgreSQL** | 15+ | Database |
| **psycopg2** | 2.9.x | PostgreSQL driver |
| **Uvicorn** | 0.34.x | ASGI server |
| **Systemd** | - | Auto-start service |
| **Raspberry Pi OS 64-bit** | - | Target OS |

---

**Built on Raspberry Pi 5 • Headless Linux Deployment • Clean Architecture**

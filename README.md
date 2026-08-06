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

**REST API backend for USB Modem LTE Network Discovery Web Application** — orchestrates CLI-based LTE scans, stores scan history in PostgreSQL, provides realtime GPS updates via WebSocket. Runs on Raspberry Pi OS 64-bit.

---

## 🏗️ Architecture Diagram

```
                  REST API (Web UI)
                       │
               FastAPI Controllers
                       │
                 Application Service Layer
                       │
         ┌─────────────┴───────────────┐
         │                             │
   CLI Adapter                   GPS Provider
         │                             │
    CLI Process               Mock / Serial GPS
         │
USB Modem LTE Discovery Engine (External CLI)
```

**Clean Architecture + KISS Principle** — Layers never violate dependency rules:
- API → Service → Repository → Database
- Services may also use CLI Adapter or GPS Provider

---

## 📁 Project Structure

```
cellular-discovery-service/
├── backend/                     # Python backend application
│   ├── app/                     # Source code
│   │   ├── api/                 # FastAPI routers & dependencies
│   │   ├── services/            # Business logic (ScanService, HistoryService)
│   │   ├── repositories/        # Data access layer
│   │   ├── cli/                 # CLI adapter (subprocess execution)
│   │   ├── gps/                 # GPS providers (Mock/Serial)
│   │   ├── db/                  # SQLAlchemy ORM models
│   │   ├── schemas/             # Pydantic request/response models
│   │   ├── config/              # Environment configuration
│   │   └── main.py              # Entry point
│   ├── tests/                   # Unit, integration, E2E tests (~110 tests)
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
│   └── README.md                # Docs folder summary
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

# Run development server
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
pytest tests/ -v

# Run with coverage report
pytest tests/ --cov=app --cov-report=mismatch

# Generate HTML coverage report
pytest tests/ --cov=app --cov-report=html
open htmlcov/index.html

# Run specific test file
pytest tests/test_cli.py -v
pytest tests/test_services.py -v
pytest tests/test_e2e.py -v

# Linting (optional)
pip install flake8 black
flake8 app/
black --check app/
```

**Test Coverage:** ~95% across core modules  
**Integration Tests:** All passing with SQLite test database (emulates PostgreSQL structure)

---

## 📋 API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/scan` | Trigger LTE network scan |
| `GET`  | `/api/v1/scans` | List scan history (with pagination) |
| `GET`  | `/api/v1/scans/{id}` | Get scan detail |
| `DELETE`| `/api/v1/scans/{id}` | Delete scan entry |
| `GET`  | `/api/v1/settings` | List app settings |
| `PUT`  | `/api/v1/settings` | Update app settings |
| `GET`  | `/health` | Health check endpoint |
| `GET`  | `/docs` | Interactive OpenAPI docs |
| `GET`  | `/openapi.json` | OpenAPI spec JSON |
| `WS`   | `/ws/gps` | Realtime GPS WebSocket |
| `WS`   | `/ws/scan` | Scan event WebSocket |

---

## 🖥️ Environment Configuration

Create `.env` from `.env.example`:

```env
DATABASE_HOST=localhost
DATABASE_PORT=5432
DATABASE_NAME=lte_scanner
DATABASE_USER=lte_scanner
DATABASE_PASSWORD=engen1us
DATABASE_SCHEMA=app

GPS_PROVIDER=mock          # Valid: mock | serial
DEFAULT_TTY=/dev/ttyUSB0
SCAN_TIMEOUT=30

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
| `SerialGPSProvider` | Reads NMEA GGA sentences from serial port | `GPS_PROVIDER=serial`, set `DEFAULT_TTY` to `/dev/ttyUSB0` or `/dev/ttyACM0` |

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
- [x] Unit Test Suite (110 tests) ✅
- [ ] JWT Authentication
- [ ] Prometheus Metrics
- [ ] CSV/JSON Export
- [ ] Multiple Modem Support
- [ ] Scheduled/Automated Scans
- [ ] Health Check Endpoint

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

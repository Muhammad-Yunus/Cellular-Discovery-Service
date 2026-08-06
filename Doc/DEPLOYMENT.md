# Deployment Documentation

## Overview

This project is a REST API backend for USB Modem LTE Network Discovery, running on Raspberry Pi OS 64-bit with Python 3.12+, FastAPI, and PostgreSQL.

---

## Prerequisites

- Raspberry Pi OS 64-bit (Headless)
- Raspberry Pi 5 or compatible hardware
- Python 3.12+
- PostgreSQL 15+
- USB LTE Modem (supporting `lte-discovery` CLI tool)

---

## Installation

### 1. Clone Repository

```bash
git clone <repo-url> /home/pi/Cellular-Discovery-Service
cd Cellular-Discovery-Service/backend
```

### 2. Create Virtual Environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment

```bash
cp .env.example .env
# Edit .env with your configuration
nano .env
```

### 5. Database Setup

**Create database and schema manually:**

```bash
sudo -u postgres psql -c "CREATE DATABASE lte_scanner;"
sudo -u postgres psql -d lte_scanner -c "CREATE SCHEMA app;"
sudo -u postgres psql -d lte_scanner -c "CREATE USER lte_scanner WITH PASSWORD 'engen1us';"
sudo -u postgres psql -d lte_scanner -c "GRANT ALL ON SCHEMA app TO lte_scanner;"
```

### 6. Run Migrations

```bash
alembic upgrade head
```

### 7. Install Scripts

```bash
chmod +x scripts/*.sh
./scripts/install.sh      # Full automated install
./scripts/run.sh          # Start in dev mode
./scripts/update.sh       # Update production
```

---

## Systemd Service

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

Enable and start the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable lte-scanner.service
sudo systemctl start lte-scanner.service
sudo systemctl status lte-scanner.service
```

---

## Configuration

### Environment Variables (`.env`)

| Variable | Default | Description |
|---------|---------|-------------|
| `DATABASE_HOST` | localhost | PostgreSQL host |
| `DATABASE_PORT` | 5432 | PostgreSQL port |
| `DATABASE_NAME` | lte_scanner | Database name |
| `DATABASE_USER` | lte_scanner | DB username |
| `DATABASE_PASSWORD` | engen1us | DB password |
| `DATABASE_SCHEMA` | app | Schema name |
| `GPS_PROVIDER` | mock | GPS provider: mock/serial |
| `DEFAULT_TTY` | /dev/ttyUSB0 | USB modem path |
| `SCAN_TIMEOUT` | 30 | Scan timeout (seconds) |
| `LOG_LEVEL` | INFO | Logging level |
| `APP_ENV` | production | App environment |
| `APP_HOST` | 0.0.0.0 | Bind address |
| `APP_PORT` | 8000 | Server port |
| `TIMEZONE` | Asia/Jakarta | Timezone |

---

## Directory Structure

```
backend/
├── app/                  # Main application
│   ├── api/              # FastAPI routers & dependencies
│   │   └── routers/      # REST & WebSocket endpoints
│   ├── services/         # Business logic layers
│   ├── repositories/     # Data access layer
│   ├── cli/              # CLI adapter (LTE discovery engine)
│   ├── gps/              # GPS providers
│   ├── db/               # SQLAlchemy ORM & migrations
│   ├── schemas/          # Pydantic models
│   ├── config/           # Application settings
│   └── main.py           # Entry point
├── tests/                # Unit & integration tests
├── alembic/              # Database migrations
├── scripts/              # Utility scripts
# (lte-scanner.service lives at project root, not inside backend/)
├── requirements.txt      # Python dependencies
├── .env.example          # Environment template
└── pyproject.toml       # Project metadata
```

---

## Testing

### Run All Tests

```bash
pytest tests/ -v
```

### Test Coverage

```bash
pytest tests/ --cov=app --cov-report=html
```

Open `htmlcov/index.html` to view detailed coverage report.

---

## Development

### Running Locally (Dev Mode)

```bash
source .venv/bin/activate
./scripts/run.sh
```

Visit `http://localhost:8000/docs` for interactive API docs.

### Linting (optional)

```bash
# Install flake8/black if needed
pip install flake8 black
black app/
flake8 app/
```

---

## Production Checklist

- [ ] Set `APP_ENV=production`
- [ ] Set appropriate `LOG_LEVEL`
- [ ] Configure correct `DATABASE_URL` credentials
- [ ] Verify `GPS_PROVIDER` matches setup (`mock` or `serial`)
- [ ] Run `alembic upgrade head` before first start
- [ ] Enable systemd service on boot
- [ ] Monitor logs via `journalctl -u lte-scanner.service`
- [ ] Set up log rotation
- [ ] Configure firewall (allow 8000/tcp locally)

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `Permission denied for schema app` | `GRANT ALL ON SCHEMA app TO lte_scanner;` |
| `Connection refused` | Check PostgreSQL is running (`pg_isready`) |
| `CLI command not found` | Ensure `lte-discovery` is in PATH or adjust PATH |
| `Uvicorn fails to start` | Check port 8000 is free, verify `.env` exists |
| `WebSocket connection drops` | Check firewall, ensure app is running with systemd |

---

## Future Extensions

- Multiple modem support
- Scheduled/Automatic scans
- Authentication & user management
- Prometheus metrics endpoint
- CSV/JSON export
- Health check endpoint

# USB Modem LTE Network Discovery Web API Documentation

**API Version:** 0.1.0  
**Base URL:** `http://localhost:8000/api/v1`  
**Format:** JSON  

---

## Table of Contents

- [Authentication](#authentication)
- [Scan Service](#scan-service)
- [History Service](#history-service)
- [Settings Service](#settings-service)
- [WebSocket Service](#websocket-service)
- [Error Handling](#error-handling)

---

## Authentication

This API does not require authentication for now. All endpoints are publicly accessible within the Raspberry Pi LAN.

---

## Scan Service

### POST /scan

Trigger an LTE network scan on the specified USB modem port.

**Request Headers:**
```
Content-Type: application/json
```

**Request Body:**
```json
{
  "tty": "/dev/ttyUSB0"
}
```

**Response (200 OK):**
```json
{
  "id": 1,
  "scan_time": "2024-01-15T10:30:00+00:00",
  "tty_port": "/dev/ttyUSB0",
  "latitude": -6.150676643667096,
  "longitude": 106.89665223346297,
  "created_at": "2024-01-15T10:30:00+00:00",
  "results": [
    {
      "id": 1,
      "operator_name": "Telkomsel",
      "mcc": "510",
      "mnc": "10",
      "rat": "4G",
      "status": "active"
    },
    {
      "id": 2,
      "operator_name": "XL Axiata",
      "mcc": "510",
      "mnc": "11",
      "rat": "4G",
      "status": "active"
    }
  ]
}
```

**Error Responses:**
- `400 Bad Request` – Invalid TTY path
- `500 Internal Server Error` – CLI execution failed or timeout

---

## History Service

### GET /scans

List all scan sessions with pagination and filtering.

**Query Parameters:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `page` | int | 1 | Page number (>= 1) |
| `page_size` | int | 10 | Items per page (1-100) |
| `search` | string | null | Search by tty_port |
| `sort` | string | -scan_time | `-scan_time` or `scan_time` |

**Response (200 OK):**
```json
{
  "items": [...],
  "total": 100,
  "page": 1,
  "page_size": 10,
  "total_pages": 10
}
```

### GET /scans/{id}

Get a single scan session with all results.

**Path Parameter:**
- `scan_id` (int) – ID of the scan session

**Response (200 OK):** Same as POST /scan response format

**Response (404 Not Found):**
```json
{"detail": "Scan not found"}
```

### DELETE /scans/{id}

Delete a scan session permanently.

**Path Parameter:**
- `scan_id` (int) – ID of the scan to delete

**Response (200 OK):**
```json
{
  "message": "Scan deleted successfully",
  "id": 123
}
```

**Response (404 Not Found):**
```json
{"detail": "Scan not found"}
```

---

## Settings Service

### GET /settings

Get all application settings.

**Response (200 OK):**
```json
[
  {
    "key": "default_tty",
    "value": "/dev/ttyUSB0",
    "updated_at": "2024-01-15T10:00:00+00:00"
  },
  {
    "key": "gps_provider",
    "value": "mock",
    "updated_at": "2024-01-15T10:00:00+00:00"
  }
]
```

### PUT /settings

Create or update multiple settings in one request.

**Request Body:**
```json
[
  {
    "key": "default_tty",
    "value": "/dev/ttyUSB1"
  },
  {
    "key": "scan_timeout",
    "value": "60"
  }
]
```

**Response (200 OK):** List of updated settings with same structure as GET /settings

---

## WebSocket Service

### GET /ws/gps

Subscribe to real-time GPS location updates.

**Connection Type:** WebSocket (`ws://host/ws/gps`)

**Message Flow:**
```
Client connects → Server broadcasts every 10s → {"type":"gps_update","data":{"lat":...,"lon":...}}
```

Each connected client receives GPS updates every 10 seconds from the configured GPS provider.

---

### GET /ws/scan

Subscribe to scan result events.

**Connection Type:** WebSocket (`ws://host/ws/scan`)

**Message Flow:**
```
Client sends text message → Server processes/broadcasts
```

Future extension for real-time scan notification when new scans complete.

---

## Error Handling

All errors return standardized JSON responses:

```json
{
  "detail": "Error message description"
}
```

| HTTP Code | Error Type | Description |
|-----------|------------|-------------|
| `400` | BadRequestException | Invalid input data |
| `404` | NotFoundException | Resource not found |
| `500` | InternalServerErrorException | Server-side error |
| `500` | CLITimeoutError | CLI execution timed out |
| `500` | CLIParseError | Failed to parse CLI output |

---

## Environment Configuration

Copy `.env.example` to `.env` and configure:

```env
DATABASE_HOST=localhost
DATABASE_PORT=5432
DATABASE_NAME=lte_scanner
DATABASE_USER=lte_scanner
DATABASE_PASSWORD=engen1us
DATABASE_SCHEMA=app

GPS_PROVIDER=mock          # or "serial"
DEFAULT_TTY=/dev/ttyUSB0
SCAN_TIMEOUT=30

LOG_LEVEL=INFO

APP_ENV=production
APP_HOST=0.0.0.0
APP_PORT=8000

TIMEZONE=Asia/Jakarta
```

---

## Deployment

```bash
# Start virtual environment
source .venv/bin/activate

# Run development
./scripts/run.sh

# Production (systemd)
sudo systemctl enable lte-scanner.service
sudo systemctl start lte-scanner.service
```

---

## OpenAPI Specification

Interactive API documentation available at: `http://localhost:8000/docs`

Auto-generated OpenAPI spec at: `http://localhost:8000/openapi.json`

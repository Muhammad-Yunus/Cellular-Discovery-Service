# USB Modem LTE Network Discovery Web API Documentation

**API Version:** 0.1.0  
**Base URL:** `http://localhost:8000/api/v1`  
**Format:** JSON  

---

## Table of Contents

- [Authentication](#authentication)
- [Scan Service](#scan-service)
- [Device Service](#device-service)
- [History Service](#history-service)
  - [GET /scans](#get-scans)
  - [GET /scans/export](#get-scansexport)
  - [GET /scans/{id}](#get-scanssid)
  - [DELETE /scans/{id}](#deletescanssid)
- [Settings Service](#settings-service)
- [Mission Service](#mission-service)
  - [GET /missions/{mission_id}/logs](#get-missionsmission_idlogs)
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

## Device Service

### GET /device/location

Get current device GPS location independently (not tied to any mission).

**Query Parameters:** None (request directly)

**Response (200 OK):**
```json
{
  "latitude": -6.150601,
  "longitude": 106.896878,
  "altitude": null,
  "accuracy": null,
  "speed": 0.18,
  "status": "IDLE",
  "datetime": "2026-08-10T13:29:53.529629",
  "provider": "cli"
}
```

**Response Fields:**
| Field | Type | Description |
|-------|------|-------------|
| `latitude` | float | Current latitude coordinate |
| `longitude` | float | Current longitude coordinate |
| `altitude` | float\|null | Altitude in meters (if available) |
| `accuracy` | float\|null | GPS accuracy in meters (if available) |
| `speed` | float | Speed in m/s, calculated from position change |
| `status` | string | Device status: `MOVING` (speed > 0.5 m/s), `IDLE` (speed <= 0.5 m/s), `UNKNOWN` (error) |
| `datetime` | datetime | Timestamp when location was read (UTC+7) |
| `provider` | string | GPS provider used: `cli`, `mock`, `serial`, `moving_mock` |

**Error Responses:**
- `503 Service Unavailable` – GPS read error (provider unavailable)
- `500 Internal Server Error` – Unexpected error

**Example:**
```bash
curl http://localhost:8000/api/v1/device/location
```

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
| `rat` | string | null | Filter by RAT: GSM, LTE, UMTS, or ALL |
| `start_time` | datetime | null | ISO 8601 datetime filter (inclusive start) |
| `end_time` | datetime | null | ISO 8601 datetime filter (inclusive end) |

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

### GET /scans/export

Export all scan matching filters as a CSV file. Supports the same query parameters as GET /scans except `page` and `page_size` are ignored (all matching records are exported).

**Query Parameters:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `search` | string | null | Search by tty_port |
| `sort` | string | -scan_time | `-scan_time` or `scan_time` |
| `rat` | string | null | Filter by RAT: GSM, LTE, UMTS, or ALL |
| `start_time` | datetime | null | ISO 8601 datetime filter (inclusive start) |
| `end_time` | datetime | null | ISO 8601 datetime filter (inclusive end) |

**Response (200 OK):** CSV file downloadable with header:
```
id,session_id,scan_time,tty_port,latitude,longitude,created_at,operator_name,mcc,mnc,rat,status
```

Additional headers: `Content-Disposition: attachment; filename="scan_export.csv"`, `Content-Type: text/csv`

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

## Mission Service

### GET /missions/{mission_id}/scans

List all scan results for a mission with pagination and filtering.

**Query Parameters:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `page` | int | 1 | Page number (>= 1) |
| `page_size` | int | 10 | Items per page (1-100) |
| `search` | string | null | Search by tty_port, operator_name, mcc, mnc |
| `sort` | string | -scan_time | Sort field: `scan_time`, `operator_name`, `operator`, `mcc`, `mnc`, `rat`, `cellular_tower_id`, `cellular_tower_name` (prefix `-` for DESC) |
| `rat` | string | null | Filter by RAT: GSM, LTE, UMTS, or ALL |
| `start_time` | datetime | null | ISO 8601 datetime filter (inclusive start) |
| `end_time` | datetime | null | ISO 8601 datetime filter (inclusive end) |

**Response (200 OK):**
```json
{
  "items": [
    {
      "id": 413,
      "scan_session_id": 1395,
      "scan_time": "2026-08-10T12:59:32.661833+07:00",
      "tty_port": "/dev/ttyAMA0",
      "latitude": -6.177359541766261,
      "longitude": 106.82887655217871,
      "mission_location_id": 6118,
      "cellular_tower_id": "TWR-003",
      "cellular_tower_name": "Tower-3",
      "created_at": "2026-08-10T12:59:32.661833+07:00",
      "operator_name": "Indosat",
      "mcc": "510",
      "mnc": "01",
      "rat": "UMTS",
      "status": "AVAILABLE"
    }
  ],
  "total": 150,
  "page": 1,
  "page_size": 10,
  "total_pages": 15
}
```

**Example:**
```bash
# Default (sort by scan_time DESC)
curl http://localhost:8000/api/v1/missions/2156/scans

# Sort by cellular_tower_id ascending
curl "http://localhost:8000/api/v1/missions/2156/scans?sort=cellular_tower_id"

# Sort by cellular_tower_id descending
curl "http://localhost:8000/api/v1/missions/2156/scans?sort=-cellular_tower_id"

# Sort by cellular_tower_name
curl "http://localhost:8000/api/v1/missions/2156/scans?sort=cellular_tower_name"

# Custom pagination
curl "http://localhost:8000/api/v1/missions/2156/scans?page=1&page_size=5"
```

### GET /missions/{mission_id}/logs

Get paginated logs for a mission, sorted by timestamp DESC.

**Path Parameter:**
- `mission_id` (int) – ID of the mission

**Query Parameters:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `page` | int | 1 | Page number (>= 1) |
| `page_size` | int | 10 | Items per page (1-100) |

**Response (200 OK):**
```json
{
  "items": [
    {
      "timestamp": "2026-08-10T12:59:32.730548+07:00",
      "event_type": "COMPLETED",
      "message": "Mission completed successfully"
    },
    {
      "timestamp": "2026-08-10T12:59:30.123456+07:00",
      "event_type": "ARRIVED",
      "message": "Arrived at location 5/5"
    }
  ],
  "total": 25,
  "page": 1,
  "page_size": 10,
  "total_pages": 3
}
```

**Response Fields:**
| Field | Type | Description |
|-------|------|-------------|
| `items` | array | List of log entries (sorted by timestamp DESC) |
| `total` | int | Total number of logs for this mission |
| `page` | int | Current page number |
| `page_size` | int | Items per page |
| `total_pages` | int | Total number of pages |

**Log Entry Fields:**
| Field | Type | Description |
|-------|------|-------------|
| `timestamp` | string | ISO format timestamp (UTC) |
| `event_type` | string | Event type: `STARTED`, `GPS_FIX`, `SCANNING`, `ARRIVED`, `SKIPPED`, `FAILED`, `COMPLETED`, `STOPPED`, `PAUSED`, `RESUMED`, etc. |
| `message` | string | Descriptive message of the event |

**Error Responses:**
- `404 Not Found` – Mission not found
- `500 Internal Server Error` – Server error

**Example:**
```bash
# Default pagination (10 items per page)
curl http://localhost:8000/api/v1/missions/2156/logs

# Custom pagination
curl "http://localhost:8000/api/v1/missions/2156/logs?page=1&page_size=5"

# Second page
curl "http://localhost:8000/api/v1/missions/2156/logs?page=2"
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

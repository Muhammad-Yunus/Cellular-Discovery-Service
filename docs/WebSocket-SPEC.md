# WebSocket API Specification

Base URL: `ws://localhost:8001`

---

## Endpoints

| Endpoint | Channel | Purpose |
|----------|---------|---------|
| `/ws/scan` | `scan` | Real-time scan results |
| `/ws/mission` | `mission` | Mission lifecycle events |
| `/ws/device/location` | `device_location` | GPS location streaming |
| `/ws/gps` | `gps` | Raw GPS fix polling |

---

## 1. `/ws/scan` — Scan Result Streaming

Broadcast channel untuk setiap hasil scan yang selesai.

**Koneksi:**
```javascript
const ws = new WebSocket('ws://localhost:8001/ws/scan');
ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  console.log(msg.type, msg.data);
};
```

**Message Format (server → client):**
```json
{
  "type": "scan_result",
  "data": {
    "scan_id": 123,
    "mission_id": 456,
    "latitude": -6.1507,
    "longitude": 106.8968,
    "altitude_m": 44.9,
    "timestamp": "2024-01-01T10:00:00Z",
    "networks": [
      {
        "plmn": "51001",
        "lac": 1234,
        "ci": 5678,
        "signal_dbm": -85,
        "technology": "LTE"
      }
    ]
  }
}
```

**Client → Server:**
Client dapat mengirim teks (tidak ada perintah khusus, log only).

---

## 2. `/ws/mission` — Mission Lifecycle Events

Broadcast channel untuk event event mission (start, pause, resume, complete, failed).

**Koneksi:**
```javascript
const ws = new WebSocket('ws://localhost:8001/ws/mission');
ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  console.log(msg.type, msg.mission_id, msg.data);
};
```

**Event Types:**

### mission_started
```json
{
  "type": "mission_started",
  "mission_id": 456,
  "data": {
    "status": "RUNNING",
    "total_locations": 3,
    "visited_count": 0
  }
}
```

### mission_paused
```json
{
  "type": "mission_paused",
  "mission_id": 456,
  "data": {
    "status": "PAUSED",
    "visited_count": 2
  }
}
```

### mission_resumed
```json
{
  "type": "mission_resumed",
  "mission_id": 456,
  "data": {
    "status": "RUNNING",
    "visited_count": 2
  }
}
```

### mission_completed
```json
{
  "type": "mission_completed",
  "mission_id": 456,
  "data": {
    "status": "COMPLETED",
    "total_locations": 3,
    "visited_count": 3,
    "duration_seconds": 312.5
  }
}
```

### mission_failed
```json
{
  "type": "mission_failed",
  "mission_id": 456,
  "data": {
    "status": "FAILED",
    "reason": "GPS_ERROR",
    "message": "No GPS fix found"
  }
}
```

### INFO (progres visit)
```json
{
  "type": "INFO",
  "mission_id": 456,
  "data": {
    "target": "TWR-001",
    "distance_m": 45.2,
    "status": "APPROACHING"
  }
}
```

**Client → Server:**
Client dapat mengirim teks (tidak ada perintah khusus, log only).

---

## 3. `/ws/device/location` — GPS Location Streaming

Streaming lokasi GPS device secara real-time (setiap 5 detik).

**Koneksi:**
```javascript
const ws = new WebSocket('ws://localhost:8001/ws/device/location');
ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  console.log(msg.data.latitude, msg.data.longitude);
};
```

**Message Format (server → client):**

### Success
```json
{
  "type": "device_location",
  "data": {
    "latitude": -6.150681,
    "longitude": 106.896891,
    "altitude": 44.9,
    "accuracy": 5.2,
    "course_deg": 135.0,
    "speed": 0.0,
    "status": "IDLE",
    "datetime": "2024-01-01T10:00:00Z",
    "provider": "cli"
  }
}
```

### Error (no fix)
```json
{
  "type": "device_location",
  "data": {
    "latitude": 0.0,
    "longitude": 0.0,
    "altitude": null,
    "accuracy": null,
    "course_deg": null,
    "speed": 0.0,
    "status": "UNKNOWN",
    "datetime": "2024-01-01T10:00:00Z",
    "provider": "cli",
    "error": "No GPS fix found. GPS may need more time to acquire fix."
  }
}
```

**Status Values:**
- `IDLE` — speed ≤ 0.5 m/s
- `MOVING` — speed > 0.5 m/s
- `UNKNOWN` — no GPS fix

**Client → Server:**
Tidak ada client command.

---

## 4. `/ws/gps` — Raw GPS Fix Polling

Polling GPS fix setiap 10 detik (lebih simple dari device/location).

**Koneksi:**
```javascript
const ws = new WebSocket('ws://localhost:8001/ws/gps');
ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  console.log(msg.data.latitude, msg.data.longitude);
};
```

**Message Format (server → client):**
```json
{
  "type": "gps_update",
  "data": {
    "latitude": -6.150681,
    "longitude": 106.896891
  }
}
```

**Client → Server:**
Tidak ada client command.

---

## Error Handling

Semua endpoint menangani disconnect dengan auto-close. Client disarankan implementasi reconnect dengan exponential backoff:

```javascript
function connectWithReconnect(url) {
  const ws = new WebSocket(url);
  
  ws.onclose = () => {
    setTimeout(() => connectWithReconnect(url), 3000);
  };
  
  ws.onmessage = (event) => {
    // handle message
  };
}
```

---

## Security Note

WebSocket endpoint saat ini **tidak ada autentikasi**. Gunakan di environment trusted (local/network internal).

# API Documentation

## REST API

OpenAPI/Swagger: http://localhost:8001/docs
ReDoc: http://localhost:8001/redoc

## WebSocket Endpoints

OpenAPI spec tidak mendukung WebSocket. Berikut daftar endpoint WebSocket:

### `/ws/scan` — Scan Result Streaming

**Connection:**
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
    "mission_id": 123,
    "scan_id": 456,
    "latitude": -6.1507,
    "longitude": 106.8968,
    "timestamp": "2024-01-01T00:00:00Z"
  }
}
```

**Client → Server:**
Client dapat mengirim teks untuk monitoring status (opsional).

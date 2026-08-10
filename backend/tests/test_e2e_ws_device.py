"""
End-to-end tests untuk Device Location WebSocket endpoint.

Test menggunakan live backend dengan GPS provider.
Membutuhkan:
- Backend service berjalan (http://localhost:8001)
- GPS hardware tersedia di /dev/ttyAMA0

Test cases:
1. Connect dan terima update lokasi
2. Response format match dengan GET endpoint
3. Multiple clients menerima update yang sama
4. Broadcast berhenti setelah disconnect
5. Reconnect bekerja setelah timeout
"""

import asyncio
import json
import time
from datetime import datetime
import pytest
import httpx
import websockets


WS_URL = "ws://localhost:8001/ws/device/location"
API_URL = "http://localhost:8001/api/v1/device/location"
POLL_INTERVAL = 5  # detik


class TestDeviceLocationE2E:
    """End-to-end tests untuk ws/device/location."""

    @pytest.fixture(scope="module")
    def event_loop(self):
        """Create module-scoped event loop."""
        loop = asyncio.new_event_loop()
        yield loop
        loop.close()

    @pytest.fixture(scope="module")
    def ws_client(self):
        """Create a WebSocket client for the module."""
        async def connect():
            return await websockets.connect(WS_URL, ping_interval=20, ping_timeout=10)
        return connect

    @pytest.mark.asyncio
    async def test_e2e_websocket_connect_and_receive(self, event_loop):
        """Test 1: Connect dan terima update lokasi."""
        ws = await websockets.connect(WS_URL, ping_interval=30, ping_timeout=15)

        try:
            # Receive first message
            msg = await asyncio.wait_for(ws.recv(), timeout=20)
            data = json.loads(msg)

            # Verify structure
            assert "type" in data
            assert data["type"] == "device_location"
            assert "data" in data
            loc = data["data"]

            # Verify location fields
            assert "latitude" in loc
            assert "longitude" in loc
            assert loc["latitude"] != 0.0  # Not error value
            assert loc["longitude"] != 0.0

            # Verify location is in Jakarta area (roughly)
            assert -7.0 < loc["latitude"] < -5.0
            assert 106.0 < loc["longitude"] < 108.0

            # Verify other fields
            assert "altitude" in loc
            assert "speed" in loc
            assert "status" in loc
            assert loc["status"] in ["IDLE", "MOVING"]
            assert "datetime" in loc
            assert "provider" in loc

            # Verify datetime is parseable
            datetime.fromisoformat(loc["datetime"])

        finally:
            await ws.close()

    @pytest.mark.asyncio
    async def test_e2e_response_format_matches_get(self, event_loop):
        """Test 2: Response format match dengan GET endpoint."""
        # Get reference from GET endpoint
        async with httpx.AsyncClient() as client:
            get_resp = await client.get(API_URL)
            assert get_resp.status_code == 200
            get_data = get_resp.json()

        # Get from WebSocket
        ws = await websockets.connect(WS_URL, ping_interval=30, ping_timeout=15)
        try:
            msg = await asyncio.wait_for(ws.recv(), timeout=20)
            ws_data = json.loads(msg)["data"]
        finally:
            await ws.close()

        # Compare field names
        assert set(get_data.keys()) == set(ws_data.keys())

        # Compare values are close (allow small GPS drift)
        assert abs(get_data["latitude"] - ws_data["latitude"]) < 0.001
        assert abs(get_data["longitude"] - ws_data["longitude"]) < 0.001

        # Check types
        assert isinstance(ws_data["latitude"], float)
        assert isinstance(ws_data["longitude"], float)
        assert isinstance(ws_data["speed"], float)
        assert isinstance(ws_data["status"], str)
        assert isinstance(ws_data["provider"], str)
        assert isinstance(ws_data["datetime"], str)

    @pytest.mark.asyncio
    async def test_e2e_multiple_clients(self, event_loop):
        """Test 3: Multiple clients menerima update yang sama."""
        ws1 = await websockets.connect(WS_URL, ping_interval=30, ping_timeout=15)
        ws2 = await websockets.connect(WS_URL, ping_interval=30, ping_timeout=15)
        ws3 = await websockets.connect(WS_URL, ping_interval=30, ping_timeout=15)

        try:
            # Receive from all 3 clients
            msg1 = await asyncio.wait_for(ws1.recv(), timeout=20)
            msg2 = await asyncio.wait_for(ws2.recv(), timeout=20)
            msg3 = await asyncio.wait_for(ws3.recv(), timeout=20)

            data1 = json.loads(msg1)["data"]
            data2 = json.loads(msg2)["data"]
            data3 = json.loads(msg3)["data"]

            # All should have same location (within tolerance)
            assert abs(data1["latitude"] - data2["latitude"]) < 0.001
            assert abs(data1["latitude"] - data3["latitude"]) < 0.001
            assert abs(data1["longitude"] - data2["longitude"]) < 0.001
            assert abs(data1["longitude"] - data3["longitude"]) < 0.001

            # All should have same type
            assert json.loads(msg1)["type"] == "device_location"
            assert json.loads(msg2)["type"] == "device_location"
            assert json.loads(msg3)["type"] == "device_location"

        finally:
            await ws1.close()
            await ws2.close()
            await ws3.close()

    @pytest.mark.asyncio
    async def test_e2e_broadcast_continues_while_connected(self):
        """Test 4: Broadcast terus berjalan selama client connected."""
        ws = await websockets.connect(WS_URL, ping_interval=30, ping_timeout=15)

        try:
            # Receive at least 2 messages (POLL_INTERVAL=5s, so 12s should get 2)
            messages = []
            deadline = time.monotonic() + 15  # Give more time for 2 messages
            while time.monotonic() < deadline:
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=8)
                    messages.append(json.loads(msg))
                    if len(messages) >= 2:
                        break
                except asyncio.TimeoutError:
                    continue

            # Should have received at least 2 messages
            assert len(messages) >= 2, f"Expected >= 2 messages, got {len(messages)}"

            # All should be valid
            for msg in messages:
                assert msg["type"] == "device_location"
                assert "data" in msg
                loc = msg["data"]
                assert "latitude" in loc
                assert "longitude" in loc

        finally:
            await ws.close()

    @pytest.mark.asyncio
    async def test_e2e_disconnect_stops_broadcast(self, event_loop):
        """Test 5: Setelah disconnect, broadcast berhenti untuk client tersebut."""
        ws = await websockets.connect(WS_URL, ping_interval=30, ping_timeout=15)

        # Receive one message
        msg = await asyncio.wait_for(ws.recv(), timeout=10)
        data = json.loads(msg)
        assert data["type"] == "device_location"

        # Disconnect
        await ws.close()

        # Try to receive again - should timeout or get closed
        try:
            msg = await asyncio.wait_for(ws.recv(), timeout=3)
            # If we get here, connection is still open (unexpected)
            pytest.fail("Should have been disconnected")
        except (asyncio.TimeoutError, websockets.exceptions.ConnectionClosed):
            pass  # Expected

    @pytest.mark.asyncio
    async def test_e2e_multiple_iterations_format(self):
        """Test 6: Multiple iterasi format tetap konsisten."""
        ws = await websockets.connect(WS_URL, ping_interval=30, ping_timeout=15)

        try:
            for i in range(3):
                msg = await asyncio.wait_for(ws.recv(), timeout=10)
                data = json.loads(msg)

                # Every message should have same structure
                assert data["type"] == "device_location"
                loc = data["data"]
                assert "latitude" in loc
                assert "longitude" in loc
                assert "speed" in loc
                assert "status" in loc
                assert "datetime" in loc
                assert "provider" in loc

                # Verify speed is reasonable
                assert loc["speed"] >= 0.0

                # Verify status
                assert loc["status"] in ["IDLE", "MOVING"]

                # Verify datetime is recent
                dt = datetime.fromisoformat(loc["datetime"])
                age = time.monotonic() - dt.timestamp()
                assert age < 30, f"Message too old: {age}s"

        finally:
            await ws.close()

    @pytest.mark.asyncio
    async def test_e2e_health_check_before_test(self, event_loop):
        """Pre-check: Backend harus tersedia."""
        async with httpx.AsyncClient() as client:
            resp = await client.get("http://localhost:8001/health")
            assert resp.status_code == 200
            assert resp.json()["status"] == "ok"


class TestDeviceLocationIntegration:
    """Integration tests dengan GPS provider."""

    @pytest.mark.asyncio
    async def test_ws_with_different_providers(self, event_loop):
        """Test WebSocket dengan provider berbeda (jika tersedia)."""
        # Test default (CLI) provider
        ws = await websockets.connect(WS_URL, ping_interval=30, ping_timeout=15)

        try:
            msg = await asyncio.wait_for(ws.recv(), timeout=20)
            data = json.loads(msg)
            assert data["data"]["provider"] == "cli"
            assert data["data"]["latitude"] != 0.0
        finally:
            await ws.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

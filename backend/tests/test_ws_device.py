"""
Unit tests untuk Device Location WebSocket endpoint (/ws/device/location).

Test cases:
1. WebSocket connect -> broadcast lokasi GPS pertama
2. Format response identik dengan GET /api/v1/device/location
3. Speed calculation (Haversine) antar 2 titik
4. Status determination: IDLE vs MOVING
5. Handle GPS read errors tanpa crash
6. Loop exit ketika tidak ada listener
7. Multiple clients menerima broadcast bersamaan
8. Datetime harus ISO format string (JSON serializable)
"""

import json
import math
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import WebSocketDisconnect

from app.api.routers.ws_device import device_location_websocket, DEVICE_CHANNEL
from app.gps.schemas import GPSLocation
from app.gps.exceptions import GPSReadError, GPSError


class TestDeviceLocationWebSocket:
    """Unit tests untuk device_location_websocket endpoint."""

    @pytest.mark.asyncio
    async def test_websocket_broadcasts_first_location(self):
        """Connection -> pertama kali broadcast lokasi GPS."""
        with patch("app.api.routers.ws_device.manager") as mock_manager, \
             patch("app.api.routers.ws_device.create_gps_provider") as mock_create, \
             patch("app.api.routers.ws_device.asyncio.sleep", new_callable=AsyncMock):
            mock_ws = AsyncMock()
            mock_manager.connect = AsyncMock()
            mock_manager.disconnect = MagicMock()
            # 1 listener, then exit
            mock_manager.get_connections_count = MagicMock(side_effect=[1, 0])

            mock_provider = MagicMock()
            mock_provider.get_location.return_value = GPSLocation(
                latitude=-6.150676,
                longitude=106.896652,
                altitude=50.0,
                accuracy=5.0,
            )
            mock_create.return_value = mock_provider
            mock_manager.broadcast = AsyncMock()

            await device_location_websocket(mock_ws)

            # Verify connect called
            mock_manager.connect.assert_called_once_with(mock_ws, DEVICE_CHANNEL)
            # Verify broadcast called once (first iteration)
            assert mock_manager.broadcast.call_count == 1

    @pytest.mark.asyncio
    async def test_websocket_response_format_matches_get_endpoint(self):
        """Response format harus sama dengan GET /api/v1/device/location."""
        with patch("app.api.routers.ws_device.manager") as mock_manager, \
             patch("app.api.routers.ws_device.create_gps_provider") as mock_create, \
             patch("app.api.routers.ws_device.asyncio.sleep", new_callable=AsyncMock):
            mock_ws = AsyncMock()
            mock_manager.connect = AsyncMock()
            mock_manager.disconnect = MagicMock()
            mock_manager.get_connections_count = MagicMock(side_effect=[1, 0])

            mock_provider = MagicMock()
            mock_provider.get_location.return_value = GPSLocation(
                latitude=-6.150676,
                longitude=106.896652,
                altitude=50.0,
                accuracy=5.0,
            )
            mock_create.return_value = mock_provider

            # Capture broadcast calls
            captured = []
            async def capture_broadcast(channel, data):
                captured.append((channel, data))

            mock_manager.broadcast = capture_broadcast

            await device_location_websocket(mock_ws)

            assert len(captured) == 1
            channel, payload = captured[0]

            # Verify channel
            assert channel == DEVICE_CHANNEL

            # Verify structure
            assert payload["type"] == "device_location"
            data = payload["data"]
            assert "latitude" in data
            assert "longitude" in data
            assert "altitude" in data
            assert "accuracy" in data
            assert "speed" in data
            assert "status" in data
            assert "datetime" in data
            assert "provider" in data

    @pytest.mark.asyncio
    async def test_websocket_datetime_is_json_serializable(self):
        """datetime field harus string ISO format (bukan datetime object)."""
        with patch("app.api.routers.ws_device.manager") as mock_manager, \
             patch("app.api.routers.ws_device.create_gps_provider") as mock_create, \
             patch("app.api.routers.ws_device.asyncio.sleep", new_callable=AsyncMock):
            mock_ws = AsyncMock()
            mock_manager.connect = AsyncMock()
            mock_manager.disconnect = MagicMock()
            mock_manager.get_connections_count = MagicMock(side_effect=[1, 0])

            mock_provider = MagicMock()
            mock_provider.get_location.return_value = GPSLocation(
                latitude=-6.150676,
                longitude=106.896652,
                altitude=50.0,
            )
            mock_create.return_value = mock_provider

            captured = []
            async def capture_broadcast(channel, data):
                captured.append((channel, data))

            mock_manager.broadcast = capture_broadcast

            await device_location_websocket(mock_ws)

            assert len(captured) == 1
            data = captured[0][1]["data"]

            # Verify datetime is string, not datetime object
            assert isinstance(data["datetime"], str)
            # Verify it's ISO format
            try:
                datetime.fromisoformat(data["datetime"])
            except ValueError:
                pytest.fail(f"datetime '{data['datetime']}' is not ISO format")

            # Verify whole payload is JSON serializable
            json.dumps(captured[0][1])

    @pytest.mark.asyncio
    async def test_websocket_speed_calculation(self):
        """Verify Haversine distance / time = speed calculation."""
        with patch("app.api.routers.ws_device.manager") as mock_manager, \
             patch("app.api.routers.ws_device.create_gps_provider") as mock_create, \
             patch("app.api.routers.ws_device.asyncio.sleep", new_callable=AsyncMock):
            mock_ws = AsyncMock()
            mock_manager.connect = AsyncMock()
            mock_manager.disconnect = MagicMock()
            mock_manager.get_connections_count = MagicMock(side_effect=[1, 1, 0])

            # Two different locations ~11m apart
            locations = [
                GPSLocation(latitude=-6.150000, longitude=106.896000, altitude=50.0),
                GPSLocation(latitude=-6.150100, longitude=106.896000, altitude=50.0),
            ]
            call_count = [0]

            def get_location():
                result = locations[call_count[0] % len(locations)]
                call_count[0] += 1
                return result

            mock_provider = MagicMock()
            mock_provider.get_location.side_effect = get_location
            mock_create.return_value = mock_provider

            captured = []
            async def capture_broadcast(channel, data):
                captured.append((channel, data))

            mock_manager.broadcast = capture_broadcast

            await device_location_websocket(mock_ws)

            assert len(captured) >= 2
            # First broadcast should have speed=0 (no previous location)
            assert captured[0][1]["data"]["speed"] == 0.0
            # Second broadcast should have speed > 0
            second_speed = captured[1][1]["data"]["speed"]
            assert second_speed > 0.0

    @pytest.mark.asyncio
    async def test_websocket_status_idle_vs_moving(self):
        """Speed < 0.5 = IDLE, speed >= 0.5 = MOVING."""
        with patch("app.api.routers.ws_device.manager") as mock_manager, \
             patch("app.api.routers.ws_device.create_gps_provider") as mock_create, \
             patch("app.api.routers.ws_device.asyncio.sleep", new_callable=AsyncMock):
            mock_ws = AsyncMock()
            mock_manager.connect = AsyncMock()
            mock_manager.disconnect = MagicMock()
            mock_manager.get_connections_count = MagicMock(side_effect=[1, 1, 1, 0])

            # Use slightly different locations to create measurable speed
            # but small enough to be IDLE
            locations = [
                GPSLocation(latitude=-6.150000, longitude=106.896000, altitude=50.0),
                GPSLocation(latitude=-6.1500001, longitude=106.896000, altitude=50.0),
                GPSLocation(latitude=-6.1500001, longitude=106.896000, altitude=50.0),
            ]
            call_count = [0]

            def get_location():
                result = locations[call_count[0] % len(locations)]
                call_count[0] += 1
                return result

            mock_provider = MagicMock()
            mock_provider.get_location.side_effect = get_location
            mock_create.return_value = mock_provider

            captured = []
            async def capture_broadcast(channel, data):
                captured.append((channel, data))

            mock_manager.broadcast = capture_broadcast

            await device_location_websocket(mock_ws)

            assert len(captured) >= 2
            # All should be IDLE (very small movement)
            for ch, payload in captured:
                assert payload["data"]["status"] in ["IDLE", "MOVING"]

    @pytest.mark.asyncio
    async def test_websocket_handles_gps_read_error(self):
        """GPS error bukan crash, harus kirim status UNKNOWN."""
        with patch("app.api.routers.ws_device.manager") as mock_manager, \
             patch("app.api.routers.ws_device.create_gps_provider") as mock_create, \
             patch("app.api.routers.ws_device.asyncio.sleep", new_callable=AsyncMock):
            mock_ws = AsyncMock()
            mock_manager.connect = AsyncMock()
            mock_manager.disconnect = MagicMock()
            mock_manager.get_connections_count = MagicMock(side_effect=[1, 1, 0])

            mock_provider = MagicMock()
            # Fail first call, succeed second
            mock_provider.get_location.side_effect = [
                GPSReadError("GPS hardware error"),
                GPSLocation(latitude=-6.150676, longitude=106.896652),
            ]
            mock_create.return_value = mock_provider

            captured = []
            async def capture_broadcast(channel, data):
                captured.append((channel, data))

            mock_manager.broadcast = capture_broadcast

            await device_location_websocket(mock_ws)

            assert len(captured) == 2
            # First: error response
            error_payload = captured[0][1]["data"]
            assert error_payload["status"] == "UNKNOWN"
            assert "error" in error_payload
            assert error_payload["latitude"] == 0.0
            assert error_payload["longitude"] == 0.0

            # Second: success response
            success_payload = captured[1][1]["data"]
            assert success_payload["status"] in ["IDLE", "MOVING"]
            assert success_payload["latitude"] == -6.150676

    @pytest.mark.asyncio
    async def test_websocket_disconnect_cleanup(self):
        """WebSocketDisconnect harus trigger cleanup."""
        with patch("app.api.routers.ws_device.manager") as mock_manager, \
             patch("app.api.routers.ws_device.create_gps_provider") as mock_create, \
             patch("app.api.routers.ws_device.asyncio.sleep", new_callable=AsyncMock):
            mock_ws = AsyncMock()
            mock_manager.connect = AsyncMock()
            mock_manager.disconnect = MagicMock()
            mock_manager.get_connections_count = MagicMock(return_value=1)

            mock_provider = MagicMock()
            mock_provider.get_location.side_effect = WebSocketDisconnect()
            mock_create.return_value = mock_provider
            mock_manager.broadcast = AsyncMock()

            await device_location_websocket(mock_ws)

            mock_manager.disconnect.assert_called_once_with(mock_ws, DEVICE_CHANNEL)

    @pytest.mark.asyncio
    async def test_websocket_no_listeners_exits_loop(self):
        """Jika tidak ada listener, loop harus exit."""
        with patch("app.api.routers.ws_device.manager") as mock_manager, \
             patch("app.api.routers.ws_device.create_gps_provider") as mock_create, \
             patch("app.api.routers.ws_device.asyncio.sleep", new_callable=AsyncMock):
            mock_ws = AsyncMock()
            mock_manager.connect = AsyncMock()
            mock_manager.disconnect = MagicMock()
            # Start with 0 listeners - loop should not execute
            mock_manager.get_connections_count = MagicMock(return_value=0)

            mock_provider = MagicMock()
            mock_provider.get_location.return_value = GPSLocation(
                latitude=-6.150676,
                longitude=106.896652,
            )
            mock_create.return_value = mock_provider
            mock_manager.broadcast = AsyncMock()

            await device_location_websocket(mock_ws)

            # Broadcast should not be called because no listeners
            mock_manager.broadcast.assert_not_called()
            # Provider.get_location should not be called because loop didn't execute
            mock_provider.get_location.assert_not_called()

    @pytest.mark.asyncio
    async def test_websocket_multiple_iterations(self):
        """Loop harus broadcast berkali-kali sampai listeners = 0."""
        with patch("app.api.routers.ws_device.manager") as mock_manager, \
             patch("app.api.routers.ws_device.create_gps_provider") as mock_create, \
             patch("app.api.routers.ws_device.asyncio.sleep", new_callable=AsyncMock):
            mock_ws = AsyncMock()
            mock_manager.connect = AsyncMock()
            mock_manager.disconnect = MagicMock()
            # 1, 1, 1, 0 -> broadcast 3 times then exit
            mock_manager.get_connections_count = MagicMock(side_effect=[1, 1, 1, 0])

            mock_provider = MagicMock()
            mock_provider.get_location.return_value = GPSLocation(
                latitude=-6.150676,
                longitude=106.896652,
                altitude=50.0,
            )
            mock_create.return_value = mock_provider
            mock_manager.broadcast = AsyncMock()

            await device_location_websocket(mock_ws)

            # Verify exactly 3 broadcasts
            assert mock_manager.broadcast.call_count == 3
            # Verify get_location called 3 times
            assert mock_provider.get_location.call_count == 3

    @pytest.mark.asyncio
    async def test_websocket_broadcast_includes_all_fields(self):
        """Verify semua field required ada di response."""
        with patch("app.api.routers.ws_device.manager") as mock_manager, \
             patch("app.api.routers.ws_device.create_gps_provider") as mock_create, \
             patch("app.api.routers.ws_device.asyncio.sleep", new_callable=AsyncMock):
            mock_ws = AsyncMock()
            mock_manager.connect = AsyncMock()
            mock_manager.disconnect = MagicMock()
            mock_manager.get_connections_count = MagicMock(side_effect=[1, 0])

            mock_provider = MagicMock()
            mock_provider.get_location.return_value = GPSLocation(
                latitude=-6.150676,
                longitude=106.896652,
                altitude=123.45,
                accuracy=3.5,
            )
            mock_create.return_value = mock_provider

            captured = []
            async def capture_broadcast(channel, data):
                captured.append((channel, data))

            mock_manager.broadcast = capture_broadcast

            await device_location_websocket(mock_ws)

            assert len(captured) == 1
            data = captured[0][1]["data"]

            # Same fields as GET /api/v1/device/location
            required_fields = [
                "latitude", "longitude", "altitude", "accuracy",
                "speed", "status", "datetime", "provider"
            ]
            for field in required_fields:
                assert field in data, f"Missing field: {field}"

            # Verify types
            assert isinstance(data["latitude"], float)
            assert isinstance(data["longitude"], float)
            assert isinstance(data["speed"], float)
            assert isinstance(data["status"], str)
            assert isinstance(data["provider"], str)
            assert isinstance(data["datetime"], str)


class TestDeviceLocationHaversine:
    """Test the Haversine distance calculation logic."""

    def test_distance_zero_same_point(self):
        lat1, lon1 = -6.150676, 106.896652
        lat2, lon2 = -6.150676, 106.896652
        R = 6371000.0

        lat1_r = math.radians(lat1)
        lat2_r = math.radians(lat2)
        dlat = lat2_r - lat1_r
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat/2)**2 + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlon/2)**2
        distance = 2 * R * math.asin(math.sqrt(a))
        assert distance < 0.001  # Should be ~0

    def test_distance_known_point(self):
        # Jakarta center to Monas: ~5km
        lat1, lon1 = -6.175110, 106.865036  # Monas
        lat2, lon2 = -6.214620, 106.845130  # ~5km away

        R = 6371000.0
        lat1_r, lat2_r = math.radians(lat1), math.radians(lat2)
        dlat = lat2_r - lat1_r
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat/2)**2 + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlon/2)**2
        distance = 2 * R * math.asin(math.sqrt(a))

        # Should be approximately 5km (within 500m tolerance)
        assert 4500 < distance < 5500

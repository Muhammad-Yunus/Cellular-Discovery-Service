import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from app.api.routers.ws_gps import gps_websocket
from app.api.routers.ws_scan import scan_websocket, broadcast_scan_result
from app.gps import GPSLocation


class TestGPSWebSocket:
    @pytest.mark.asyncio
    async def test_gps_websocket_broadcasts_location(self):
        with patch("app.api.routers.ws_gps.manager") as mock_manager, \
             patch("app.api.routers.ws_gps.create_gps_provider") as mock_create, \
             patch("app.api.routers.ws_gps.asyncio.sleep", new_callable=AsyncMock):
            mock_ws = AsyncMock()
            mock_manager.connect = AsyncMock()
            mock_manager.disconnect = MagicMock()
            mock_manager.get_connections_count = MagicMock(side_effect=[1, 0])

            mock_provider = MagicMock()
            mock_provider.get_location.return_value = GPSLocation(
                latitude=-6.150676643667096,
                longitude=106.89665223346297,
            )
            mock_create.return_value = mock_provider

            mock_manager.broadcast = AsyncMock()

            await gps_websocket(mock_ws)

            mock_manager.connect.assert_called_once()
            mock_manager.broadcast.assert_called_once()

    @pytest.mark.asyncio
    async def test_gps_websocket_disconnect(self):
        with patch("app.api.routers.ws_gps.manager") as mock_manager, \
             patch("app.api.routers.ws_gps.create_gps_provider") as mock_create:
            from fastapi import WebSocketDisconnect

            mock_ws = AsyncMock()
            mock_manager.connect = AsyncMock()
            mock_manager.disconnect = MagicMock()
            mock_manager.get_connections_count = MagicMock(return_value=1)

            mock_ws.receive_text = AsyncMock(side_effect=WebSocketDisconnect)

            mock_provider = MagicMock()
            mock_provider.get_location.return_value = GPSLocation(
                latitude=-6.150676643667096,
                longitude=106.89665223346297,
            )
            mock_create.return_value = mock_provider

            await gps_websocket(mock_ws)

            mock_manager.disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_gps_websocket_error(self):
        with patch("app.api.routers.ws_gps.manager") as mock_manager, \
             patch("app.api.routers.ws_gps.create_gps_provider") as mock_create:
            mock_ws = AsyncMock()
            mock_manager.connect = AsyncMock()
            mock_manager.disconnect = MagicMock()
            mock_manager.get_connections_count = MagicMock(return_value=1)

            mock_provider = MagicMock()
            mock_provider.get_location.side_effect = Exception("GPS error")
            mock_create.return_value = mock_provider

            await gps_websocket(mock_ws)

            mock_manager.disconnect.assert_called_once()


class TestScanWebSocket:
    @pytest.mark.asyncio
    async def test_scan_websocket(self):
        with patch("app.api.routers.ws_scan.manager") as mock_manager:
            from fastapi import WebSocketDisconnect

            mock_ws = AsyncMock()
            mock_manager.connect = AsyncMock()
            mock_manager.disconnect = MagicMock()
            mock_manager.get_connections_count = MagicMock(return_value=1)

            mock_ws.receive_text = AsyncMock(side_effect=WebSocketDisconnect)

            await scan_websocket(mock_ws)

            mock_manager.connect.assert_called_once()
            mock_manager.disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_broadcast_scan_result(self):
        with patch("app.api.routers.ws_scan.manager") as mock_manager:
            mock_manager.broadcast = AsyncMock()

            await broadcast_scan_result({"operator": "Telkomsel"})

            mock_manager.broadcast.assert_called_once_with(
                "scan",
                {"type": "scan_result", "data": {"operator": "Telkomsel"}},
            )

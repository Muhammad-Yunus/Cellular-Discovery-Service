import pytest
from unittest.mock import AsyncMock
from app.core.websocket_manager import ConnectionManager


class TestConnectionManager:
    def setup_method(self):
        self.manager = ConnectionManager()

    @pytest.mark.asyncio
    async def test_connect(self):
        mock_websocket = AsyncMock()

        await self.manager.connect(mock_websocket, "test_channel")

        assert self.manager.get_connections_count("test_channel") == 1

    @pytest.mark.asyncio
    async def test_disconnect(self):
        mock_websocket = AsyncMock()

        await self.manager.connect(mock_websocket, "test_channel")
        assert self.manager.get_connections_count("test_channel") == 1

        self.manager.disconnect(mock_websocket, "test_channel")
        assert self.manager.get_connections_count("test_channel") == 0

    @pytest.mark.asyncio
    async def test_broadcast(self):
        mock_ws1 = AsyncMock()
        mock_ws2 = AsyncMock()

        await self.manager.connect(mock_ws1, "test_channel")
        await self.manager.connect(mock_ws2, "test_channel")

        await self.manager.broadcast("test_channel", {"type": "test", "data": "hello"})

        mock_ws1.send_json.assert_called_once_with({"type": "test", "data": "hello"})
        mock_ws2.send_json.assert_called_once_with({"type": "test", "data": "hello"})

    def test_get_connections_count_empty(self):
        assert self.manager.get_connections_count("nonexistent") == 0

    @pytest.mark.asyncio
    async def test_multiple_channels(self):
        mock_ws1 = AsyncMock()
        mock_ws2 = AsyncMock()

        await self.manager.connect(mock_ws1, "channel1")
        await self.manager.connect(mock_ws2, "channel2")

        assert self.manager.get_connections_count("channel1") == 1
        assert self.manager.get_connections_count("channel2") == 1

    @pytest.mark.asyncio
    async def test_broadcast_removes_failed_connections(self):
        mock_ws_good = AsyncMock()
        mock_ws_bad = AsyncMock()
        mock_ws_bad.send_json.side_effect = Exception("Connection closed")

        await self.manager.connect(mock_ws_good, "test_channel")
        await self.manager.connect(mock_ws_bad, "test_channel")

        await self.manager.broadcast("test_channel", {"type": "test"})

        assert self.manager.get_connections_count("test_channel") == 1

import asyncio
import time

import pytest

from app.api.routers.ws_mission import broadcast_mission_event
from app.core.websocket_manager import manager
from app.services.scan_service import ScanService

from tests.conftest import CSV_1, FakeCLI, FakeGPS, make_planned, stop_and_wait


def recv_until(ws, event_type):
    while True:
        msg = ws.receive_json()
        if msg["type"] == event_type:
            return msg


def collect_until(ws, terminal_types):
    msgs = []
    while True:
        msg = ws.receive_json()
        msgs.append(msg)
        if msg["type"] in terminal_types:
            return msgs


class TestPayload:
    @pytest.mark.parametrize(
        "event_type",
        [
            "mission_started",
            "mission_progress",
            "mission_visit",
            "mission_skipped",
            "mission_paused",
            "mission_resumed",
            "mission_stopped",
            "mission_completed",
            "mission_failed",
        ],
    )
    def test_u01_envelope(self, monkeypatch, event_type):
        captured = {}

        async def fake_broadcast(channel, payload):
            captured["channel"] = channel
            captured["payload"] = payload

        monkeypatch.setattr(manager, "broadcast", fake_broadcast)

        asyncio.run(broadcast_mission_event(event_type, 3, status="RUNNING"))

        payload = captured["payload"]
        assert payload["type"] == event_type
        assert payload["mission_id"] == 3
        assert "mission_id" not in payload["data"]
        assert captured["channel"] == "mission"

    def test_u02_progress_fields(self, monkeypatch):
        captured = {}

        async def fake_broadcast(channel, payload):
            captured["payload"] = payload

        monkeypatch.setattr(manager, "broadcast", fake_broadcast)

        asyncio.run(
            broadcast_mission_event(
                "mission_progress",
                3,
                current_location_id=45,
                visited_locations=3,
                total_locations=10,
                status="RUNNING",
                distance_to_target_meters=15.2,
            )
        )

        payload = captured["payload"]
        assert payload["mission_id"] == 3
        assert payload["data"] == {
            "current_location_id": 45,
            "visited_locations": 3,
            "total_locations": 10,
            "status": "RUNNING",
            "distance_to_target_meters": 15.2,
        }

    def test_u03_visit_fields(self, monkeypatch):
        captured = {}

        async def fake_broadcast(channel, payload):
            captured["payload"] = payload

        monkeypatch.setattr(manager, "broadcast", fake_broadcast)

        asyncio.run(
            broadcast_mission_event(
                "mission_visit",
                3,
                location_id=45,
                tower_id="TWR-005",
                tower_name="Jakarta Pusat",
                scan_session_id=456,
                distance_m=14.2,
            )
        )

        data = captured["payload"]["data"]
        assert data["tower_id"] == "TWR-005"
        assert data["tower_name"] == "Jakarta Pusat"
        assert data["scan_session_id"] == 456
        assert data["distance_m"] == 14.2

    def test_u04_failed_reason_passthrough(self, monkeypatch):
        captured = {}

        async def fake_broadcast(channel, payload):
            captured["payload"] = payload

        monkeypatch.setattr(manager, "broadcast", fake_broadcast)

        reason = "GPS unavailable after 10 consecutive failures"
        asyncio.run(
            broadcast_mission_event(
                "mission_failed", 3, status="FAILED", reason=reason
            )
        )

        assert captured["payload"]["data"]["reason"] == reason

    def test_u05_broadcast_targets_mission_channel(self, monkeypatch):
        channels = []

        async def fake_broadcast(channel, payload):
            channels.append(channel)

        monkeypatch.setattr(manager, "broadcast", fake_broadcast)

        asyncio.run(broadcast_mission_event("mission_paused", 3, status="PAUSED"))
        asyncio.run(broadcast_mission_event("mission_visit", 3, location_id=1))
        asyncio.run(
            broadcast_mission_event("mission_completed", 3, status="COMPLETED")
        )

        assert channels == ["mission", "mission", "mission"]

    def test_u06_broadcast_no_subscribers(self):
        asyncio.run(
            broadcast_mission_event("mission_completed", 3, status="COMPLETED")
        )


class TestChannels:
    def test_u07_connection_manager_multichannel(self, api):
        assert manager.get_connections_count("mission") == 0

        with api.websocket_connect("/ws/mission") as m1, api.websocket_connect(
            "/ws/scan"
        ) as s1:
            assert manager.get_connections_count("mission") == 1
            assert manager.get_connections_count("scan") == 1

            with api.websocket_connect("/ws/mission") as m2:
                assert manager.get_connections_count("mission") == 2

            assert manager.get_connections_count("mission") == 1

        assert manager.get_connections_count("mission") == 0
        assert manager.get_connections_count("scan") == 0

    def test_e04_scan_and_gps_channels_unchanged(self, api):
        with api.websocket_connect("/ws/scan"), api.websocket_connect("/ws/gps"):
            assert manager.get_connections_count("scan") == 1
            assert manager.get_connections_count("gps") == 1


class TestMissionEvents:
    def test_e01_mission_ws_connects(self, api):
        with api.websocket_connect("/ws/mission"):
            assert manager.get_connections_count("mission") == 1

    def test_e02_full_mission_event_sequence(self, api, executor, db_session):
        mission = make_planned(db_session)

        with api.websocket_connect("/ws/mission") as ws:
            api.post(f"/api/v1/missions/{mission.id}/start")
            msgs = collect_until(ws, {"mission_completed"})

        types = [m["type"] for m in msgs]
        expected = [
            "mission_started",
            "mission_progress",
            "mission_visit",
            "mission_completed",
        ]
        indexes = [types.index(t) for t in expected]
        assert indexes == sorted(indexes)
        assert types[-1] == "mission_completed"

        started = next(m for m in msgs if m["type"] == "mission_started")
        assert started["data"]["name"] == mission.name
        assert started["data"]["status"] == "RUNNING"
        assert started["data"]["total_locations"] == 1

        visit = next(m for m in msgs if m["type"] == "mission_visit")
        assert set(visit["data"]) >= {
            "location_id",
            "tower_id",
            "tower_name",
            "scan_session_id",
            "distance_m",
        }
        assert visit["data"]["tower_id"] == "T1"
        assert visit["data"]["scan_session_id"] is not None

    def test_u08_scan_failure_emits_skipped(self, api, executor, db_session):
        cli = FakeCLI(error=RuntimeError("scan exploded"))
        gps = FakeGPS()

        def scan_factory(db):
            return ScanService(db=db, cli_adapter=cli, gps_provider=gps)

        executor._scan_factory = scan_factory
        executor.gps_provider = gps
        mission = make_planned(db_session)

        with api.websocket_connect("/ws/mission") as ws:
            api.post(f"/api/v1/missions/{mission.id}/start")
            msgs = collect_until(ws, {"mission_completed"})

        skipped = next(m for m in msgs if m["type"] == "mission_skipped")
        assert skipped["data"]["reason"] == "SCAN_ERROR"
        assert skipped["data"]["tower_id"] == "T1"
        assert msgs[-1]["type"] == "mission_completed"

    def test_e03_pause_resume_stop_events(self, api, executor, db_session):
        mission = make_planned(db_session)
        executor.gps_provider = FakeGPS(lat=0, lon=0)

        with api.websocket_connect("/ws/mission") as ws:
            api.post(f"/api/v1/missions/{mission.id}/start")
            recv_until(ws, "mission_started")

            api.post(f"/api/v1/missions/{mission.id}/pause")
            assert recv_until(ws, "mission_paused")["data"]["status"] == "PAUSED"

            api.post(f"/api/v1/missions/{mission.id}/resume")
            assert recv_until(ws, "mission_resumed")["data"]["status"] == "RUNNING"

            api.post(f"/api/v1/missions/{mission.id}/stop")
            assert recv_until(ws, "mission_stopped")["data"]["status"] == "STOPPED"

    def test_e05_disconnect_mid_mission(self, api, executor, db_session):
        mission = make_planned(db_session)
        executor.gps_provider = FakeGPS(lat=0, lon=0)

        with api.websocket_connect("/ws/mission") as ws:
            api.post(f"/api/v1/missions/{mission.id}/start")
            recv_until(ws, "mission_started")

        time.sleep(0.3)

        status = api.get(f"/api/v1/missions/{mission.id}/status").json()
        assert status["status"] == "RUNNING"
        assert status["active"] is True
        stop_and_wait(api, mission.id)

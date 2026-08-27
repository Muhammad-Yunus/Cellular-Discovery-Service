import pytest
from unittest.mock import MagicMock, patch
from app.cli import CLIScanResponse, CLIScanResult
from app.gps import GPSLocation
from app.api.dependencies.providers import get_cli_adapter, get_gps_provider
from app.db.database import get_db


class TestHealthEndpoint:
    def test_health_check(self, client):
        response = client.get("/health")

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestScanEndpoints:
    def test_execute_scan_success(self, client):
        mock_gps = MagicMock()
        mock_gps.get_location.return_value = GPSLocation(
            latitude=-6.150676643667096,
            longitude=106.89665223346297,
        )

        mock_cli = MagicMock()
        mock_cli.execute.return_value = CLIScanResponse(
            results=[
                CLIScanResult(
                    operator_name="Telkomsel",
                    mcc="510",
                    mnc="10",
                    rat="4G",
                    status="active",
                )
            ],
            raw_output='{"results": []}',
        )

        client.app.dependency_overrides[get_gps_provider] = lambda: mock_gps
        client.app.dependency_overrides[get_cli_adapter] = lambda: mock_cli

        try:
            response = client.post(
                "/api/v1/scan",
                json={"band": 8},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["band"] == "8"
            assert len(data["results"]) == 1
        finally:
            client.app.dependency_overrides.pop(get_gps_provider, None)
            client.app.dependency_overrides.pop(get_cli_adapter, None)


class TestHistoryEndpoints:
    def test_list_scans_empty(self, client):
        response = client.get("/api/v1/scans")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert len(data["items"]) == 0

    def test_get_scan_not_found(self, client):
        response = client.get("/api/v1/scans/9999")

        assert response.status_code == 404

    def test_delete_scan_not_found(self, client):
        response = client.delete("/api/v1/scans/9999")

        assert response.status_code == 404


class TestSettingsEndpoints:
    def test_list_settings_empty(self, client):
        response = client.get("/api/v1/settings")

        assert response.status_code == 200
        assert response.json() == []

    def test_update_settings(self, client):
        response = client.put(
            "/api/v1/settings",
            json=[
                {"key": "test_key", "value": "test_value"},
            ],
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["key"] == "test_key"

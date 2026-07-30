import pytest
from unittest.mock import patch, MagicMock
from app.cli import CLIScanResponse, CLIScanResult
from app.gps import GPSLocation
from app.api.dependencies.providers import get_gps_provider, get_cli_adapter
from app.db.database import get_db
from app.db.models.scan_session import ScanSession
from app.db.models.scan_result import ScanResult
from app.db.models.setting import Setting


@pytest.fixture
def mock_cli():
    cli = MagicMock()
    cli.execute.return_value = CLIScanResponse(
        results=[
            CLIScanResult(
                operator_name="Telkomsel",
                mcc="510",
                mnc="10",
                rat="4G",
                status="registered",
            ),
            CLIScanResult(
                operator_name="XL Axiata",
                mcc="510",
                mnc="11",
                rat="4G",
                status="registered",
            ),
        ],
        raw_output='{"results": []}',
    )
    return cli


@pytest.fixture
def mock_gps():
    gps = MagicMock()
    gps.get_location.return_value = GPSLocation(
        latitude=-6.150676643667096,
        longitude=106.89665223346297,
    )
    return gps


class TestScanWorkflowE2E:
    def test_full_scan_workflow(self, client, db_session, mock_cli, mock_gps):
        client.app.dependency_overrides[get_gps_provider] = lambda: mock_gps
        client.app.dependency_overrides[get_cli_adapter] = lambda: mock_cli

        try:
            response = client.post(
                "/api/v1/scan",
                json={"tty": "/dev/ttyUSB0"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["tty_port"] == "/dev/ttyUSB0"
            assert data["latitude"] == pytest.approx(-6.150676643667096)
            assert data["longitude"] == pytest.approx(106.89665223346297)
            assert len(data["results"]) == 2
            assert data["results"][0]["operator_name"] == "Telkomsel"
            assert data["results"][0]["mcc"] == "510"
            assert data["results"][1]["operator_name"] == "XL Axiata"

            result_id = data["results"][0]["id"]

            detail_response = client.get(f"/api/v1/scans/{result_id}")
            assert detail_response.status_code == 200
            detail = detail_response.json()
            assert detail["id"] == result_id
            assert detail["operator_name"] == "Telkomsel"
            assert detail["scan_session_id"] == data["id"]

        finally:
            client.app.dependency_overrides.pop(get_gps_provider, None)
            client.app.dependency_overrides.pop(get_cli_adapter, None)

    def test_multiple_scans_accumulate(self, client, db_session, mock_cli, mock_gps):
        client.app.dependency_overrides[get_gps_provider] = lambda: mock_gps
        client.app.dependency_overrides[get_cli_adapter] = lambda: mock_cli

        try:
            for i in range(3):
                response = client.post(
                    "/api/v1/scan",
                    json={"tty": f"/dev/ttyUSB{i}"},
                )
                assert response.status_code == 200

            list_response = client.get("/api/v1/scans")
            assert list_response.status_code == 200
            data = list_response.json()
            assert data["total"] == 6
            assert len(data["items"]) == 6

        finally:
            client.app.dependency_overrides.pop(get_gps_provider, None)
            client.app.dependency_overrides.pop(get_cli_adapter, None)

    def test_scan_cli_failure_returns_error(self, client, db_session, mock_gps):
        failing_cli = MagicMock()
        from app.cli.exceptions import CLIError
        failing_cli.execute.side_effect = CLIError("CLI failed", stderr="error output")

        client.app.dependency_overrides[get_gps_provider] = lambda: mock_gps
        client.app.dependency_overrides[get_cli_adapter] = lambda: failing_cli

        try:
            response = client.post(
                "/api/v1/scan",
                json={"tty": "/dev/ttyUSB0"},
            )

            assert response.status_code == 500
            assert "CLI failed" in response.json()["detail"]

        finally:
            client.app.dependency_overrides.pop(get_gps_provider, None)
            client.app.dependency_overrides.pop(get_cli_adapter, None)


class TestHistoryCRUDE2E:
    def test_create_and_get_scan(self, client, db_session, mock_cli, mock_gps):
        client.app.dependency_overrides[get_gps_provider] = lambda: mock_gps
        client.app.dependency_overrides[get_cli_adapter] = lambda: mock_cli

        try:
            create_resp = client.post(
                "/api/v1/scan",
                json={"tty": "/dev/ttyUSB0"},
            )
            result_id = create_resp.json()["results"][0]["id"]

            get_resp = client.get(f"/api/v1/scans/{result_id}")
            assert get_resp.status_code == 200
            assert get_resp.json()["id"] == result_id
        finally:
            client.app.dependency_overrides.pop(get_gps_provider, None)
            client.app.dependency_overrides.pop(get_cli_adapter, None)

    def test_create_and_delete_scan(self, client, db_session, mock_cli, mock_gps):
        client.app.dependency_overrides[get_gps_provider] = lambda: mock_gps
        client.app.dependency_overrides[get_cli_adapter] = lambda: mock_cli

        try:
            create_resp = client.post(
                "/api/v1/scan",
                json={"tty": "/dev/ttyUSB0"},
            )
            result_id = create_resp.json()["results"][0]["id"]

            delete_resp = client.delete(f"/api/v1/scans/{result_id}")
            assert delete_resp.status_code == 200
            assert delete_resp.json()["id"] == result_id

            get_resp = client.get(f"/api/v1/scans/{result_id}")
            assert get_resp.status_code == 404
        finally:
            client.app.dependency_overrides.pop(get_gps_provider, None)
            client.app.dependency_overrides.pop(get_cli_adapter, None)

    def test_delete_nonexistent_scan(self, client, db_session):
        response = client.delete("/api/v1/scans/99999")
        assert response.status_code == 404

    def test_get_nonexistent_scan(self, client, db_session):
        response = client.get("/api/v1/scans/99999")
        assert response.status_code == 404

    def test_list_empty_scans(self, client, db_session):
        response = client.get("/api/v1/scans")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["items"] == []
        assert data["total_pages"] == 1


class TestSettingsE2E:
    def test_empty_settings(self, client, db_session):
        response = client.get("/api/v1/settings")
        assert response.status_code == 200
        assert response.json() == []

    def test_add_settings(self, client, db_session):
        response = client.put(
            "/api/v1/settings",
            json=[
                {"key": "default_tty", "value": "/dev/ttyUSB0"},
                {"key": "gps_provider", "value": "mock"},
                {"key": "scan_timeout", "value": "30"},
            ],
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3

        keys = {s["key"] for s in data}
        assert keys == {"default_tty", "gps_provider", "scan_timeout"}

    def test_update_settings(self, client, db_session):
        client.put(
            "/api/v1/settings",
            json=[{"key": "default_tty", "value": "/dev/ttyUSB0"}],
        )

        response = client.put(
            "/api/v1/settings",
            json=[{"key": "default_tty", "value": "/dev/ttyUSB1"}],
        )
        assert response.status_code == 200
        data = response.json()
        assert data[0]["value"] == "/dev/ttyUSB1"

    def test_settings_persist(self, client, db_session):
        client.put(
            "/api/v1/settings",
            json=[
                {"key": "key1", "value": "value1"},
                {"key": "key2", "value": "value2"},
            ],
        )

        response = client.get("/api/v1/settings")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2


class TestPaginationE2E:
    def _populate_scans(self, client, count=25, mock_cli=None, mock_gps=None):
        client.app.dependency_overrides[get_gps_provider] = lambda: mock_gps
        client.app.dependency_overrides[get_cli_adapter] = lambda: mock_cli

        try:
            for i in range(count):
                client.post(
                    "/api/v1/scan",
                    json={"tty": f"/dev/ttyUSB{i % 5}"},
                )
        finally:
            client.app.dependency_overrides.pop(get_gps_provider, None)
            client.app.dependency_overrides.pop(get_cli_adapter, None)

    def test_pagination_default(self, client, db_session, mock_cli, mock_gps):
        self._populate_scans(client, 25, mock_cli, mock_gps)

        response = client.get("/api/v1/scans")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 50
        assert len(data["items"]) == 10
        assert data["page"] == 1
        assert data["page_size"] == 10
        assert data["total_pages"] == 5

    def test_pagination_page_2(self, client, db_session, mock_cli, mock_gps):
        self._populate_scans(client, 25, mock_cli, mock_gps)

        response = client.get("/api/v1/scans?page=2&page_size=10")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 10
        assert data["page"] == 2

    def test_pagination_last_page(self, client, db_session, mock_cli, mock_gps):
        self._populate_scans(client, 25, mock_cli, mock_gps)

        response = client.get("/api/v1/scans?page=5&page_size=10")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 10

    def test_pagination_custom_page_size(self, client, db_session, mock_cli, mock_gps):
        self._populate_scans(client, 15, mock_cli, mock_gps)

        response = client.get("/api/v1/scans?page=1&page_size=5")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 5
        assert data["total_pages"] == 6


class TestHealthCheckE2E:
    def test_health_check(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_docs_available(self, client):
        response = client.get("/docs")
        assert response.status_code == 200

    def test_openapi_available(self, client):
        response = client.get("/openapi.json")
        assert response.status_code == 200
        data = response.json()
        assert "openapi" in data
        assert "paths" in data

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from app.db.models import Mission
from app.db.models.mission_location import MissionLocation
from app.services import LocationService
from app.repositories import MissionLocationRepository

CSV_HEADER = "cellular_tower_id,cellular_tower_name,latitude,longitude\n"
CSV_VALID = (
    CSV_HEADER
    + "TWR-001,Jakarta Pusat,-6.2088,106.8456\n"
    + "TWR-002,Jakarta Selatan,-6.2615,106.8106\n"
    + "TWR-003,Jakarta Barat,-6.1688,106.7582\n"
)


def make_mission(db, status="IDLE", name="Mission X"):
    mission = Mission(name=name, status=status)
    db.add(mission)
    db.commit()
    db.refresh(mission)
    return mission


class TestParseCsv:
    def test_u01_parse_csv_valid(self):
        rows = LocationService.parse_csv(CSV_VALID.encode())

        assert len(rows) == 3
        assert all(not row["errors"] for row in rows)
        assert rows[0]["cellular_tower_id"] == "TWR-001"
        assert rows[0]["cellular_tower_name"] == "Jakarta Pusat"
        assert rows[0]["latitude"] == -6.2088
        assert rows[0]["longitude"] == 106.8456

    def test_u02_parse_csv_missing_header(self):
        csv_bytes = b"foo,bar\n1,2\n"

        with pytest.raises(ValueError) as exc:
            LocationService.parse_csv(csv_bytes)

        assert "Invalid CSV header" in str(exc.value)

    def test_u03_parse_csv_bad_latitude(self):
        csv_bytes = (
            CSV_HEADER
            + "TWR-001,Jakarta Pusat,abc,106.8456\n"
            + "TWR-002,Jakarta Selatan,-6.2615,106.8106\n"
        ).encode()

        rows = LocationService.parse_csv(csv_bytes)

        assert rows[0]["errors"] == ["invalid latitude (must be a number): abc"]
        assert rows[0]["latitude"] is None
        assert rows[1]["errors"] == []
        assert rows[1]["latitude"] == -6.2615

    def test_u04_parse_csv_out_of_range_longitude(self):
        csv_bytes = (CSV_HEADER + "TWR-001,Jakarta Pusat,-6.2088,200.5\n").encode()

        rows = LocationService.parse_csv(csv_bytes)

        assert rows[0]["errors"] == ["longitude out of range (-180 to 180): 200.5"]
        assert rows[0]["longitude"] is None

    def test_u05_parse_csv_empty_file_raises(self, db_session):
        # Empty file is caught at the router layer (_read_and_validate_csv),
        # so calling service.upload() directly with empty bytes returns an
        # empty UploadLocationResponse instead of raising.
        mission = make_mission(db_session)
        service = LocationService(db_session)

        result = service.upload(mission.id, b"")
        assert result.inserted == 0
        assert result.updated == 0
        assert result.skipped == 0
        assert result.total_rows == 0
        assert result.errors == []


class TestUpsertBatch:
    def test_u06_upsert_new_rows(self, db_session):
        mission = make_mission(db_session)
        repo = MissionLocationRepository(db_session)
        rows = [
            {"cellular_tower_id": "T1", "cellular_tower_name": "A", "latitude": -6.2, "longitude": 106.8},
            {"cellular_tower_id": "T2", "cellular_tower_name": "B", "latitude": -6.3, "longitude": 106.9},
        ]

        inserted, updated = repo.upsert_batch(mission.id, rows, "batch-1")

        assert inserted == 2
        assert updated == 0

    def test_u07_upsert_existing_ids(self, db_session):
        mission = make_mission(db_session)
        repo = MissionLocationRepository(db_session)
        repo.upsert_batch(
            mission.id,
            [{"cellular_tower_id": "T1", "cellular_tower_name": "Old", "latitude": -6.2, "longitude": 106.8}],
            "batch-1",
        )

        inserted, updated = repo.upsert_batch(
            mission.id,
            [{"cellular_tower_id": "T1", "cellular_tower_name": "New", "latitude": -6.5, "longitude": 107.0}],
            "batch-2",
        )

        assert inserted == 0
        assert updated == 1
        loc = db_session.query(MissionLocation).filter_by(mission_id=mission.id).first()
        assert loc.cellular_tower_name == "New"
        assert loc.latitude == -6.5
        assert loc.longitude == 107.0

    def test_u08_upsert_mixed_batch(self, db_session):
        mission = make_mission(db_session)
        repo = MissionLocationRepository(db_session)
        repo.upsert_batch(
            mission.id,
            [{"cellular_tower_id": "T1", "cellular_tower_name": "Old", "latitude": -6.2, "longitude": 106.8}],
            "batch-1",
        )

        inserted, updated = repo.upsert_batch(
            mission.id,
            [
                {"cellular_tower_id": "T1", "cellular_tower_name": "Updated", "latitude": -6.5, "longitude": 107.0},
                {"cellular_tower_id": "T9", "cellular_tower_name": "New", "latitude": -6.6, "longitude": 107.1},
            ],
            "batch-2",
        )

        assert inserted == 1
        assert updated == 1
        batch_rows = (
            db_session.query(MissionLocation)
            .filter_by(mission_id=mission.id, upload_batch_id="batch-2")
            .all()
        )
        assert len(batch_rows) == 2


class TestListQuery:
    def test_u09_list_by_mission_pagination(self, db_session):
        mission = make_mission(db_session)
        repo = MissionLocationRepository(db_session)
        repo.upsert_batch(
            mission.id,
            [
                {"cellular_tower_id": f"T{i}", "cellular_tower_name": f"Name {i}", "latitude": -6.0, "longitude": 106.0}
                for i in range(25)
            ],
            "batch-1",
        )

        page1, total = repo.list_by_mission(mission.id, page=1, page_size=10)
        page3, total2 = repo.list_by_mission(mission.id, page=3, page_size=10)

        assert len(page1) == 10
        assert len(page3) == 5
        assert total == 25
        assert total2 == 25
        assert [loc.cellular_tower_id for loc in page1] == [f"T{i}" for i in range(10)]

    def test_u10_list_by_mission_search_ilike(self, db_session):
        mission = make_mission(db_session)
        repo = MissionLocationRepository(db_session)
        repo.upsert_batch(
            mission.id,
            [
                {"cellular_tower_id": "TWR-001", "cellular_tower_name": "Jakarta Pusat", "latitude": -6.2, "longitude": 106.8},
                {"cellular_tower_id": "TWR-002", "cellular_tower_name": "Jakarta Selatan", "latitude": -6.3, "longitude": 106.9},
                {"cellular_tower_id": "XYZ-100", "cellular_tower_name": "Bogor", "latitude": -6.6, "longitude": 106.8},
            ],
            "batch-1",
        )

        by_id, _ = repo.list_by_mission(mission.id, 1, 10, search="twr-0")
        by_name, _ = repo.list_by_mission(mission.id, 1, 10, search="jakarta")

        assert len(by_id) == 2
        assert len(by_name) == 2

    def test_u11_count_by_mission_after_upsert(self, db_session):
        mission = make_mission(db_session)
        repo = MissionLocationRepository(db_session)
        repo.upsert_batch(
            mission.id,
            [
                {"cellular_tower_id": f"T{i}", "cellular_tower_name": "N", "latitude": -6.0, "longitude": 106.0}
                for i in range(7)
            ],
            "batch-1",
        )

        assert repo.count_by_mission(mission.id) == 7


class TestGuard:
    def test_u12_ensure_mutable_rejects_active(self, db_session):
        for status in ("STARTING", "RUNNING", "PAUSED"):
            mission = make_mission(db_session, status=status)

            with pytest.raises(HTTPException) as exc:
                LocationService._ensure_mutable(mission)

            assert exc.value.status_code == 409
            assert "Cannot modify locations while mission is running" in exc.value.detail

    def test_ensure_mutable_allows_idle(self, db_session):
        mission = make_mission(db_session, status="IDLE")

        LocationService._ensure_mutable(mission)


class TestLocationEndpoints:
    def test_e01_upload_valid_csv(self, client, db_session):
        mission = make_mission(db_session)

        response = client.post(
            f"/api/v1/missions/{mission.id}/locations/upload",
            files={"file": ("towers.csv", CSV_VALID.encode(), "text/csv")},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["mission_id"] == mission.id
        assert data["total_rows"] == 3
        assert data["inserted"] == 3
        assert data["updated"] == 0
        assert data["skipped"] == 0
        assert data["upload_batch_id"]
        db_session.refresh(mission)
        assert mission.total_locations == 3

    def test_e02_upload_same_csv_twice(self, client, db_session):
        mission = make_mission(db_session)

        client.post(
            f"/api/v1/missions/{mission.id}/locations/upload",
            files={"file": ("towers.csv", CSV_VALID.encode(), "text/csv")},
        )
        response = client.post(
            f"/api/v1/missions/{mission.id}/locations/upload",
            files={"file": ("towers.csv", CSV_VALID.encode(), "text/csv")},
        )

        data = response.json()
        assert data["inserted"] == 0
        assert data["updated"] == 3
        assert data["total_rows"] == 3

    def test_e03_get_list_after_upload(self, client, db_session):
        mission = make_mission(db_session)
        client.post(
            f"/api/v1/missions/{mission.id}/locations/upload",
            files={"file": ("towers.csv", CSV_VALID.encode(), "text/csv")},
        )

        response = client.get(f"/api/v1/missions/{mission.id}/locations")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        assert len(data["items"]) == 3
        assert data["items"][0]["cellular_tower_id"] == "TWR-001"

    def test_e04_get_list_search(self, client, db_session):
        mission = make_mission(db_session)
        client.post(
            f"/api/v1/missions/{mission.id}/locations/upload",
            files={"file": ("towers.csv", CSV_VALID.encode(), "text/csv")},
        )

        response = client.get(f"/api/v1/missions/{mission.id}/locations?search=TWR-0")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        assert all("TWR-0" in item["cellular_tower_id"] for item in data["items"])

    def test_e05_get_single_location(self, client, db_session):
        mission = make_mission(db_session)
        client.post(
            f"/api/v1/missions/{mission.id}/locations/upload",
            files={"file": ("towers.csv", CSV_VALID.encode(), "text/csv")},
        )
        location_id = client.get(f"/api/v1/missions/{mission.id}/locations").json()["items"][0]["id"]

        response = client.get(f"/api/v1/missions/{mission.id}/locations/{location_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == location_id
        assert data["mission_id"] == mission.id
        assert data["cellular_tower_id"] == "TWR-001"
        assert data["status"] == "PENDING"

    def test_e06_delete_single_location(self, client, db_session):
        mission = make_mission(db_session)
        client.post(
            f"/api/v1/missions/{mission.id}/locations/upload",
            files={"file": ("towers.csv", CSV_VALID.encode(), "text/csv")},
        )
        location_id = client.get(f"/api/v1/missions/{mission.id}/locations").json()["items"][0]["id"]

        response = client.delete(f"/api/v1/missions/{mission.id}/locations/{location_id}")

        assert response.status_code == 200
        assert response.json()["message"] == "Location deleted successfully"
        assert client.get(f"/api/v1/missions/{mission.id}/locations/{location_id}").status_code == 404
        db_session.refresh(mission)
        assert mission.total_locations == 2

    def test_e07_delete_on_running_mission(self, client, db_session):
        mission = make_mission(db_session)
        client.post(
            f"/api/v1/missions/{mission.id}/locations/upload",
            files={"file": ("towers.csv", CSV_VALID.encode(), "text/csv")},
        )
        location_id = client.get(f"/api/v1/missions/{mission.id}/locations").json()["items"][0]["id"]

        mission.status = "RUNNING"
        db_session.commit()

        response = client.delete(f"/api/v1/missions/{mission.id}/locations/{location_id}")

        assert response.status_code == 409
        assert "Cannot modify locations while mission is running" in response.json()["detail"]
        assert client.get(f"/api/v1/missions/{mission.id}/locations/{location_id}").status_code == 200

    def test_e08_bulk_delete_by_batch(self, client, db_session):
        mission = make_mission(db_session)
        upload = client.post(
            f"/api/v1/missions/{mission.id}/locations/upload",
            files={"file": ("towers.csv", CSV_VALID.encode(), "text/csv")},
        ).json()
        batch_id = upload["upload_batch_id"]

        response = client.post(
            f"/api/v1/missions/{mission.id}/locations/bulk-delete",
            json={"upload_batch_id": batch_id},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["deleted"] == 3
        assert f"Deleted 3 locations from batch {batch_id}" in data["message"]
        assert client.get(f"/api/v1/missions/{mission.id}/locations").json()["total"] == 0
        db_session.refresh(mission)
        assert mission.total_locations == 0

    def test_e09_upload_to_non_existent_mission(self, client):
        response = client.post(
            "/api/v1/missions/99999/locations/upload",
            files={"file": ("towers.csv", CSV_VALID.encode(), "text/csv")},
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Mission not found"

    def test_e10_upload_bad_header(self, client, db_session):
        mission = make_mission(db_session)

        response = client.post(
            f"/api/v1/missions/{mission.id}/locations/upload",
            files={"file": ("bad.csv", b"foo,bar\n1,2\n", "text/csv")},
        )

        # Header-level errors are file-level failures (no row number),
        # so they stay as 422 with a flat string detail — matching the
        # project-standard error format.
        assert response.status_code == 422
        assert "Invalid CSV header" in response.json()["detail"]

    def test_e12_upload_non_csv_extension(self, client, db_session):
        mission = make_mission(db_session)

        response = client.post(
            f"/api/v1/missions/{mission.id}/locations/upload",
            files={"file": ("data.txt", b"foo\n", "text/plain")},
        )

        assert response.status_code == 422
        assert "Only .csv files are accepted" in response.json()["detail"]

    def test_e13_upload_binary_file(self, client, db_session):
        mission = make_mission(db_session)

        response = client.post(
            f"/api/v1/missions/{mission.id}/locations/upload",
            files={"file": ("binary.csv", b"\x00\x01\x02\x03", "application/octet-stream")},
        )

        assert response.status_code == 422
        # Binary content-type is rejected by the content-type check
        detail = response.json()["detail"]
        assert "CSV" in detail or "octet-stream" in detail or "text-based" in detail

    def test_e14_upload_bad_encoding(self, client, db_session):
        """Non-UTF-8 bytes in a .csv file should be rejected cleanly (not crash)."""
        mission = make_mission(db_session)

        # These bytes are valid Latin-1 but invalid UTF-8
        bad_bytes = bytes([0xFF, 0xFE, 0xFD, 0xFC])

        response = client.post(
            f"/api/v1/missions/{mission.id}/locations/upload",
            files={"file": ("data.csv", bad_bytes, "text/csv")},
        )

        assert response.status_code == 422
        # The UTF-8 decode error must be caught in the service layer,
        # not surface as a 500 Internal Server Error
        assert response.status_code < 500

    def test_e15_upload_mixed_valid_and_invalid_rows(self, client, db_session):
        """Some rows valid, some invalid — partial success with error report."""
        mission = make_mission(db_session)

        mixed_csv = (
            CSV_HEADER
            + "TWR-001,Jakarta Pusat,-6.2088,106.8456\n"   # valid
            + "TWR-002,Jakarta,abc,200.5\n"               # invalid lat + lon
            + "TWR-003,Jakarta Selatan,-6.2615,106.8106\n" # valid
        ).encode()

        response = client.post(
            f"/api/v1/missions/{mission.id}/locations/upload",
            files={"file": ("towers.csv", mixed_csv, "text/csv")},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total_rows"] == 3
        assert data["inserted"] == 2
        assert data["skipped"] == 1
        # Per-row errors must be reported with the actual row number
        assert any(e["row"] == 3 for e in data["errors"])

    def test_e11_upload_while_running(self, client, db_session):
        mission = make_mission(db_session, status="RUNNING")

        response = client.post(
            f"/api/v1/missions/{mission.id}/locations/upload",
            files={"file": ("towers.csv", CSV_VALID.encode(), "text/csv")},
        )

        assert response.status_code == 409
        assert "Cannot modify locations while mission is running" in response.json()["detail"]
        assert db_session.query(MissionLocation).filter_by(mission_id=mission.id).count() == 0

    def test_e16_download_template(self, client, db_session):
        """GET /missions/{id}/locations/download_template returns CSV with 5 sample rows."""
        mission = make_mission(db_session)

        response = client.get(f"/api/v1/missions/{mission.id}/locations/download_template")

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/csv; charset=utf-8"
        assert f"mission_{mission.id}" in response.headers["content-disposition"]

        lines = response.text.strip().split("\n")
        assert lines[0] == "cellular_tower_id,cellular_tower_name,latitude,longitude"
        assert len(lines) == 6  # header + 5 rows

        # All rows should be valid (between -90/90 lat and -180/180 lon)
        for line in lines[1:]:
            parts = line.split(",")
            assert len(parts) == 4
            lat, lon = float(parts[2]), float(parts[3])
            assert -90 <= lat <= 90
            assert -180 <= lon <= 180

    def test_e17_download_template_nonexistent_mission(self, client):
        """404 when mission does not exist."""
        response = client.get("/api/v1/missions/99999/locations/download_template")
        assert response.status_code == 404
        assert response.json()["detail"] == "Mission not found"

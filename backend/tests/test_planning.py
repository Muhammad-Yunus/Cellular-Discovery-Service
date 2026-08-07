import pytest
from fastapi import HTTPException

from app.db.models import Mission, MissionLocation
from app.schemas.route import ReorderItem
from app.services import LocationService, MissionPlannerService
from tests.conftest import FakeGPS

CSV_HEADER = "cellular_tower_id,cellular_tower_name,latitude,longitude\n"
CSV_5 = (
    CSV_HEADER
    + "T1,A,-6.200,106.800\n"
    + "T2,B,-6.260,106.820\n"
    + "T3,C,-6.150,106.780\n"
    + "T4,D,-6.220,106.860\n"
    + "T5,E,-6.280,106.830\n"
)


def make_mission(db, status="IDLE", name="Mission X"):
    mission = Mission(name=name, status=status)
    db.add(mission)
    db.commit()
    db.refresh(mission)
    return mission


def upload(db, mission_id):
    return LocationService(db).upload(mission_id, CSV_5.encode())


def locations_of(db, mission_id):
    return (
        db.query(MissionLocation)
        .filter(MissionLocation.mission_id == mission_id)
        .order_by(MissionLocation.id)
        .all()
    )


class TestPlan:
    def test_u07_plan_empty_mission(self, db_session):
        mission = make_mission(db_session)

        with pytest.raises(HTTPException) as exc:
            MissionPlannerService(db_session, gps_provider=FakeGPS()).plan(mission.id)

        assert exc.value.status_code == 422
        assert exc.value.detail == "Mission has no locations to plan"

    def test_u08_plan_single_location(self, db_session):
        service = MissionPlannerService(db_session, gps_provider=FakeGPS())
        mission = make_mission(db_session)
        LocationService(db_session).upload(
            mission.id, (CSV_HEADER + "T1,A,-6.2,106.8\n").encode()
        )

        route = service.plan(mission.id)

        assert len(route.items) == 1
        assert route.items[0].sequence_order == 1
        assert route.items[0].distance_from_previous_meters is None
        assert route.items[0].bearing_from_previous_degrees is None
        assert route.status == "READY"
        db_session.refresh(mission)
        assert mission.status == "READY"
        assert mission.total_locations == 1

    def test_u09_plan_writes_fields(self, db_session):
        service = MissionPlannerService(db_session, gps_provider=FakeGPS())
        mission = make_mission(db_session)
        upload(db_session, mission.id)

        route = service.plan(mission.id)

        seqs = [item.sequence_order for item in route.items]
        assert seqs == [1, 2, 3, 4, 5]
        assert all(item.distance_from_previous_meters is not None for item in route.items[1:])
        assert all(item.bearing_from_previous_degrees is not None for item in route.items[1:])
        assert route.items[0].distance_from_previous_meters is None

    def test_u10_plan_on_running(self, db_session):
        service = MissionPlannerService(db_session, gps_provider=FakeGPS())
        mission = make_mission(db_session, status="RUNNING")

        with pytest.raises(HTTPException) as exc:
            service.plan(mission.id)

        assert exc.value.status_code == 409
        assert exc.value.detail == "Cannot plan while mission is RUNNING"

    def test_u16_build_route_total_distance(self, db_session):
        service = MissionPlannerService(db_session, gps_provider=FakeGPS())
        mission = make_mission(db_session)
        upload(db_session, mission.id)
        service.plan(mission.id)

        route = service.build_route(mission.id)
        expected = sum(
            loc.distance_from_previous_meters
            for loc in locations_of(db_session, mission.id)
            if loc.distance_from_previous_meters is not None
        )

        assert route.total_distance_meters == round(expected, 2)


class TestReorder:
    def _plan_mission(self, db_session):
        service = MissionPlannerService(db_session, gps_provider=FakeGPS())
        mission = make_mission(db_session)
        upload(db_session, mission.id)
        service.plan(mission.id)
        return service, mission

    def test_u11_reorder_full_valid_list(self, db_session):
        service, mission = self._plan_mission(db_session)
        locs = locations_of(db_session, mission.id)
        locs[1].status = "IN_PROGRESS"
        locs[2].status = "SKIPPED"
        db_session.commit()

        payload = [
            ReorderItem(location_id=locs[2].id, sequence_order=1),
            ReorderItem(location_id=locs[0].id, sequence_order=2),
            ReorderItem(location_id=locs[1].id, sequence_order=3),
            ReorderItem(location_id=locs[4].id, sequence_order=4),
            ReorderItem(location_id=locs[3].id, sequence_order=5),
        ]
        route = service.reorder(mission.id, payload)

        ordered = [item.location_id for item in route.items]
        assert ordered == [locs[2].id, locs[0].id, locs[1].id, locs[4].id, locs[3].id]
        assert route.status == "READY"
        db_session.refresh(mission)
        assert mission.status == "READY"

        statuses = {loc.id: loc.status for loc in locations_of(db_session, mission.id)}
        assert statuses[locs[0].id] == "PENDING"
        assert statuses[locs[1].id] == "PENDING"
        assert statuses[locs[2].id] == "PENDING"

    def test_u12_reorder_incomplete_list(self, db_session):
        service, mission = self._plan_mission(db_session)
        locs = locations_of(db_session, mission.id)

        with pytest.raises(HTTPException) as exc:
            service.reorder(
                mission.id,
                [ReorderItem(location_id=locs[0].id, sequence_order=1)],
            )

        assert exc.value.status_code == 422
        assert "Reorder list must include all mission locations" in exc.value.detail

    def test_u13_reorder_duplicate_sequence_order(self, db_session):
        service, mission = self._plan_mission(db_session)
        locs = locations_of(db_session, mission.id)

        payload = [
            ReorderItem(location_id=locs[0].id, sequence_order=1),
            ReorderItem(location_id=locs[1].id, sequence_order=1),
            ReorderItem(location_id=locs[2].id, sequence_order=3),
            ReorderItem(location_id=locs[3].id, sequence_order=4),
            ReorderItem(location_id=locs[4].id, sequence_order=5),
        ]

        with pytest.raises(HTTPException) as exc:
            service.reorder(mission.id, payload)

        assert exc.value.status_code == 422
        assert exc.value.detail == "Duplicate sequence_order values are not allowed"

    def test_u14_reorder_foreign_location(self, db_session):
        service, mission = self._plan_mission(db_session)
        other = make_mission(db_session, name="Other")
        upload(db_session, other.id)
        foreign_loc = locations_of(db_session, other.id)[0]
        locs = locations_of(db_session, mission.id)

        payload = [
            ReorderItem(location_id=foreign_loc.id, sequence_order=1),
            ReorderItem(location_id=locs[0].id, sequence_order=2),
            ReorderItem(location_id=locs[1].id, sequence_order=3),
            ReorderItem(location_id=locs[2].id, sequence_order=4),
            ReorderItem(location_id=locs[3].id, sequence_order=5),
        ]

        with pytest.raises(HTTPException) as exc:
            service.reorder(mission.id, payload)

        assert exc.value.status_code == 422
        assert exc.value.detail == f"location_id {foreign_loc.id} does not belong to this mission"


class TestSkip:
    def test_u15_skip_location(self, db_session):
        service = MissionPlannerService(db_session, gps_provider=FakeGPS())
        mission = make_mission(db_session)
        upload(db_session, mission.id)
        service.plan(mission.id)
        locs = locations_of(db_session, mission.id)
        mid = locs[2]

        result = service.skip(mission.id, mid.id)

        assert result.message == "Location skipped successfully"
        assert result.location_id == mid.id

        db_session.refresh(mid)
        assert mid.status == "SKIPPED"
        assert mid.sequence_order is None

        remaining = sorted(
            [loc for loc in locations_of(db_session, mission.id) if loc.sequence_order is not None],
            key=lambda loc: loc.sequence_order,
        )
        assert [loc.sequence_order for loc in remaining] == [1, 2, 3, 4]

    def test_u15_skip_recomputes_distances(self, db_session):
        service = MissionPlannerService(db_session, gps_provider=FakeGPS())
        mission = make_mission(db_session)
        upload(db_session, mission.id)
        service.plan(mission.id)
        locs = locations_of(db_session, mission.id)

        service.skip(mission.id, locs[2].id)

        remaining = sorted(
            [loc for loc in locations_of(db_session, mission.id) if loc.sequence_order is not None],
            key=lambda loc: loc.sequence_order,
        )
        assert remaining[1].distance_from_previous_meters is not None


class TestPlanningEndpoints:
    def _create_with_locations(self, client, db_session):
        mission = make_mission(db_session)
        upload(db_session, mission.id)
        return mission

    def test_e01_create_upload_plan_route(self, client, db_session):
        mission = self._create_with_locations(client, db_session)

        plan_resp = client.post(f"/api/v1/missions/{mission.id}/plan")
        route_resp = client.get(f"/api/v1/missions/{mission.id}/route")

        assert plan_resp.status_code == 200
        assert route_resp.status_code == 200
        plan_data = plan_resp.json()
        route_data = route_resp.json()
        assert len(plan_data["items"]) == 5
        assert [item["sequence_order"] for item in plan_data["items"]] == [1, 2, 3, 4, 5]
        assert route_data["items"] == plan_data["items"]

    def test_e02_route_before_planning(self, client, db_session):
        mission = self._create_with_locations(client, db_session)

        route = client.get(f"/api/v1/missions/{mission.id}/route")

        assert route.status_code == 200
        data = route.json()
        assert all(item["sequence_order"] is None for item in data["items"])
        assert data["total_distance_meters"] == 0.0

    def test_e03_plan_twice_deterministic(self, client, db_session):
        mission = self._create_with_locations(client, db_session)

        first = client.post(f"/api/v1/missions/{mission.id}/plan").json()
        second = client.post(f"/api/v1/missions/{mission.id}/plan").json()

        first_order = [item["location_id"] for item in first["items"]]
        second_order = [item["location_id"] for item in second["items"]]
        assert first_order == second_order

    def test_e04_reorder_then_route(self, client, db_session):
        mission = self._create_with_locations(client, db_session)
        client.post(f"/api/v1/missions/{mission.id}/plan")
        locs = locations_of(db_session, mission.id)

        reversed_payload = [
            {"location_id": locs[4].id, "sequence_order": 1},
            {"location_id": locs[3].id, "sequence_order": 2},
            {"location_id": locs[2].id, "sequence_order": 3},
            {"location_id": locs[1].id, "sequence_order": 4},
            {"location_id": locs[0].id, "sequence_order": 5},
        ]
        reorder = client.post(
            f"/api/v1/missions/{mission.id}/route/reorder", json=reversed_payload
        )
        route = client.get(f"/api/v1/missions/{mission.id}/route")

        assert reorder.status_code == 200
        manual_order = [item["location_id"] for item in route.json()["items"]]
        assert manual_order == [locs[4].id, locs[3].id, locs[2].id, locs[1].id, locs[0].id]

    def test_e05_reorder_then_plan(self, client, db_session):
        mission = self._create_with_locations(client, db_session)
        client.post(f"/api/v1/missions/{mission.id}/plan")
        locs = locations_of(db_session, mission.id)

        reversed_payload = [
            {"location_id": locs[4].id, "sequence_order": 1},
            {"location_id": locs[3].id, "sequence_order": 2},
            {"location_id": locs[2].id, "sequence_order": 3},
            {"location_id": locs[1].id, "sequence_order": 4},
            {"location_id": locs[0].id, "sequence_order": 5},
        ]
        client.post(f"/api/v1/missions/{mission.id}/route/reorder", json=reversed_payload)
        planned = client.post(f"/api/v1/missions/{mission.id}/plan").json()

        planned_order = [item["location_id"] for item in planned["items"]]
        assert planned_order != [locs[4].id, locs[3].id, locs[2].id, locs[1].id, locs[0].id]
        assert sorted(planned_order) == sorted(locs[i].id for i in range(5))

    def test_e06_skip_mid_route(self, client, db_session):
        mission = self._create_with_locations(client, db_session)
        client.post(f"/api/v1/missions/{mission.id}/plan")
        locs = locations_of(db_session, mission.id)
        mid = locs[2]

        skip = client.post(
            f"/api/v1/missions/{mission.id}/route/skip", json={"location_id": mid.id}
        )
        route = client.get(f"/api/v1/missions/{mission.id}/route")

        assert skip.status_code == 200
        assert skip.json() == {
            "message": "Location skipped successfully",
            "location_id": mid.id,
        }
        items = route.json()["items"]
        planned = [item for item in items if item["sequence_order"] is not None]
        assert [item["sequence_order"] for item in planned] == [1, 2, 3, 4]
        skipped_item = next(item for item in items if item["location_id"] == mid.id)
        assert skipped_item["sequence_order"] is None
        assert skipped_item["status"] == "SKIPPED"

        replan = client.post(f"/api/v1/missions/{mission.id}/plan")
        assert replan.status_code == 200

    def test_e07_plan_on_running(self, client, db_session):
        mission = make_mission(db_session, status="RUNNING")

        response = client.post(f"/api/v1/missions/{mission.id}/plan")

        assert response.status_code == 409
        assert response.json()["detail"] == "Cannot plan while mission is RUNNING"

    def test_e08_plan_without_locations(self, client, db_session):
        mission = make_mission(db_session)

        response = client.post(f"/api/v1/missions/{mission.id}/plan")

        assert response.status_code == 422
        assert response.json()["detail"] == "Mission has no locations to plan"

    def test_e09_route_of_deleted_mission(self, client, db_session):
        response = client.get("/api/v1/missions/99999/route")

        assert response.status_code == 404
        assert response.json()["detail"] == "Mission not found"

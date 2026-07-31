import math

import pytest

from app.services.mission_planner_service import nearest_neighbor, two_opt
from app.utils.geo import bearing, haversine


class TestGeo:
    def test_u01_haversine_known_pair(self):
        dist = haversine(-6.1754, 106.8272, -6.1646, 106.8272)
        assert 0.99 * 1200 <= dist <= 1.01 * 1200

    def test_u01_haversine_same_point(self):
        assert haversine(-6.2088, 106.8456, -6.2088, 106.8456) == 0.0

    def test_u02_bearing_directions(self):
        lat, lon = 0.0, 0.0
        north = bearing(lat, lon, lat + 0.01, lon)
        east = bearing(lat, lon, lat, lon + 0.01)
        south = bearing(lat, lon, lat - 0.01, lon)
        west = bearing(lat, lon, lat, lon - 0.01)

        assert abs(north - 0) < 1
        assert abs(east - 90) < 1
        assert abs(south - 180) < 1
        assert abs(west - 270) < 1


class TestNearestNeighbor:
    def test_u03_nearest_neighbor_three_points(self):
        points = [(0.0, 0.0, 1), (0.0, 0.01, 2), (0.0, 0.03, 3)]
        order = nearest_neighbor(points, start_idx=0)

        assert [p[2] for p in order] == [1, 2, 3]

    def test_u04_nearest_neighbor_single_point(self):
        points = [(-6.2, 106.8, 42)]
        order = nearest_neighbor(points, start_idx=0)

        assert [p[2] for p in order] == [42]


class TestTwoOpt:
    def test_u05_two_opt_on_crossed_path(self):
        d = math.sqrt(2)
        dist_matrix = [
            [0.0, 1.0, d, 1.0],
            [1.0, 0.0, 1.0, d],
            [d, 1.0, 0.0, 1.0],
            [1.0, d, 1.0, 0.0],
        ]
        index_by_id = {0: 0, 1: 1, 2: 2, 3: 3}
        crossed = [(0.0, 0.0, 0), (1.0, 1.0, 2), (1.0, 0.0, 1), (0.0, 1.0, 3)]

        def path_length(order):
            return sum(
                dist_matrix[index_by_id[order[i][2]]][index_by_id[order[i + 1][2]]]
                for i in range(len(order) - 1)
            )

        improved = two_opt(crossed.copy(), dist_matrix, index_by_id)

        assert path_length(improved) <= path_length(crossed)
        assert [p[2] for p in improved] == [0, 1, 2, 3]

    def test_u06_two_opt_noop_on_optimal(self):
        d = math.sqrt(2)
        dist_matrix = [
            [0.0, 1.0, d, 1.0],
            [1.0, 0.0, 1.0, d],
            [d, 1.0, 0.0, 1.0],
            [1.0, d, 1.0, 0.0],
        ]
        index_by_id = {0: 0, 1: 1, 2: 2, 3: 3}
        optimal = [(0.0, 0.0, 0), (1.0, 0.0, 1), (1.0, 1.0, 2), (0.0, 1.0, 3)]

        result = two_opt(optimal.copy(), dist_matrix, index_by_id)

        assert [p[2] for p in result] == [0, 1, 2, 3]

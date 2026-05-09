import math
import random
import pytest
from backend.services.interpolator import RouteInterpolator

RI = RouteInterpolator


class TestHaversine:
    def test_same_point_is_zero(self):
        assert RI.haversine(25.0, 121.0, 25.0, 121.0) == pytest.approx(0.0)

    def test_taipei_to_tokyo(self):
        dist = RI.haversine(25.0330, 121.5654, 35.6762, 139.6503)
        assert dist == pytest.approx(2_100_000, rel=0.05)

    def test_symmetric(self):
        a = RI.haversine(10.0, 20.0, 30.0, 40.0)
        b = RI.haversine(30.0, 40.0, 10.0, 20.0)
        assert a == pytest.approx(b)

    def test_one_degree_latitude_approx_111km(self):
        dist = RI.haversine(0.0, 0.0, 1.0, 0.0)
        assert dist == pytest.approx(111_194, rel=0.005)


class TestBearing:
    def test_north(self):
        b = RI.bearing(0.0, 0.0, 1.0, 0.0)
        assert b == pytest.approx(0.0, abs=0.01)

    def test_south(self):
        b = RI.bearing(1.0, 0.0, 0.0, 0.0)
        assert b == pytest.approx(180.0, abs=0.01)

    def test_east(self):
        b = RI.bearing(0.0, 0.0, 0.0, 1.0)
        assert b == pytest.approx(90.0, abs=0.01)

    def test_west(self):
        b = RI.bearing(0.0, 1.0, 0.0, 0.0)
        assert b == pytest.approx(270.0, abs=0.01)

    def test_result_in_range(self):
        b = RI.bearing(25.0, 121.0, 35.0, 139.0)
        assert 0.0 <= b < 360.0


class TestMovePoint:
    def test_zero_distance_returns_origin(self):
        lat, lon = RI.move_point(10.0, 20.0, 45.0, 0.0)
        assert lat == pytest.approx(10.0)
        assert lon == pytest.approx(20.0)

    def test_north_1000m_increases_latitude(self):
        lat, lon = RI.move_point(0.0, 0.0, 0.0, 1000.0)
        assert lat == pytest.approx(0.008993, rel=0.01)
        assert lon == pytest.approx(0.0, abs=1e-6)

    def test_roundtrip(self):
        lat1, lon1 = 25.0330, 121.5654
        b = RI.bearing(lat1, lon1, 35.0, 139.0)
        dist = RI.haversine(lat1, lon1, 35.0, 139.0)
        lat2, lon2 = RI.move_point(lat1, lon1, b, dist)
        assert lat2 == pytest.approx(35.0, abs=0.01)
        assert lon2 == pytest.approx(139.0, abs=0.01)


class TestInterpolate:
    def test_short_segment_returns_endpoint(self):
        # ~1m segment with step_m=5 → should return just the endpoint
        pts = RI.interpolate(0.0, 0.0, 0.000009, 0.0, step_m=5.0)
        assert len(pts) == 1
        assert pts[0][0] == pytest.approx(0.000009, rel=1e-3)

    def test_normal_segment_ends_at_destination(self):
        pts = RI.interpolate(0.0, 0.0, 0.1, 0.0, step_m=1000.0)
        assert len(pts) >= 10
        last = pts[-1]
        assert last[0] == pytest.approx(0.1, rel=0.01)

    def test_step_spacing(self):
        pts = RI.interpolate(0.0, 0.0, 0.0, 0.1, step_m=1000.0)
        # Inner segments are exactly step_m; last segment may be shorter.
        for i in range(len(pts) - 2):
            d = RI.haversine(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1])
            assert d == pytest.approx(1000.0, rel=0.05)
        last_d = RI.haversine(pts[-2][0], pts[-2][1], pts[-1][0], pts[-1][1])
        assert 0.0 < last_d <= 1000.0 + 1.0


class TestAddJitter:
    def test_output_within_max_distance(self):
        random.seed(0)
        origin_lat, origin_lon = 25.0, 121.0
        max_m = 3.0
        for _ in range(100):
            jlat, jlon = RI.add_jitter(origin_lat, origin_lon, max_m)
            dist = RI.haversine(origin_lat, origin_lon, jlat, jlon)
            assert dist <= max_m + 1e-6


class TestRandomPointInRadius:
    def test_all_points_within_radius(self):
        rng = random.Random(42)
        center_lat, center_lon = 25.0, 121.0
        radius_m = 500.0
        for _ in range(1000):
            lat, lon = RI.random_point_in_radius(center_lat, center_lon, radius_m, rng)
            dist = RI.haversine(center_lat, center_lon, lat, lon)
            assert dist <= radius_m + 1e-6

    def test_deterministic_with_seeded_rng(self):
        rng1 = random.Random(99)
        rng2 = random.Random(99)
        p1 = RI.random_point_in_radius(0.0, 0.0, 1000.0, rng1)
        p2 = RI.random_point_in_radius(0.0, 0.0, 1000.0, rng2)
        assert p1 == p2

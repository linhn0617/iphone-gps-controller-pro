import math
import pytest
from backend.core.goldditto import _offset_to_bearing_dist, _DITTO_OFFSETS


class TestOffsetToBearingDist:
    def _single(self, north, east):
        return _offset_to_bearing_dist([(north, east)])[0]

    def test_zero_offset(self):
        bearing, dist = self._single(0, 0)
        assert bearing == pytest.approx(0.0)
        assert dist == pytest.approx(0.0)

    def test_north(self):
        bearing, dist = self._single(100, 0)
        assert bearing == pytest.approx(0.0, abs=1e-6)
        assert dist == pytest.approx(100.0)

    def test_east(self):
        bearing, dist = self._single(0, 100)
        assert bearing == pytest.approx(90.0, abs=1e-6)
        assert dist == pytest.approx(100.0)

    def test_south(self):
        bearing, dist = self._single(-100, 0)
        assert bearing == pytest.approx(180.0, abs=1e-6)
        assert dist == pytest.approx(100.0)

    def test_west(self):
        bearing, dist = self._single(0, -100)
        assert bearing == pytest.approx(270.0, abs=1e-6)
        assert dist == pytest.approx(100.0)

    def test_northeast_diagonal(self):
        bearing, dist = self._single(70, 70)
        assert bearing == pytest.approx(45.0, abs=0.01)
        assert dist == pytest.approx(math.sqrt(70**2 + 70**2), rel=1e-6)

    def test_bearing_in_range(self):
        for north, east in _DITTO_OFFSETS:
            bearing, _ = self._single(north, east)
            assert 0.0 <= bearing < 360.0

    def test_output_length_matches_input(self):
        result = _offset_to_bearing_dist(_DITTO_OFFSETS)
        assert len(result) == len(_DITTO_OFFSETS)

    def test_actual_ditto_offsets_round_trip(self):
        """Distances in the ditto pattern match sqrt(n²+e²)."""
        from backend.services.interpolator import RouteInterpolator
        results = _offset_to_bearing_dist(_DITTO_OFFSETS)
        for (north, east), (bearing, dist) in zip(_DITTO_OFFSETS, results):
            expected_dist = math.sqrt(north**2 + east**2)
            assert dist == pytest.approx(expected_dist, rel=1e-6)
            # move_point with that bearing+dist should yield a point ~dist metres away
            if dist > 0:
                lat, lon = RouteInterpolator.move_point(0.0, 0.0, bearing, dist)
                back = RouteInterpolator.haversine(0.0, 0.0, lat, lon)
                assert back == pytest.approx(dist, rel=0.01)

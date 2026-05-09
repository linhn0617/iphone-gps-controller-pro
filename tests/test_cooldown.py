import time
import pytest
from backend.services.cooldown import CooldownTimer


class TestLookup:
    """Boundary tests for the COOLDOWN_TABLE lookup."""

    def test_0_5_km(self):
        assert CooldownTimer._lookup(0.5) == 0.0

    def test_1_0_km_boundary(self):
        assert CooldownTimer._lookup(1.0) == 0.0

    def test_1_01_km_triggers_30s(self):
        assert CooldownTimer._lookup(1.01) == 30.0

    def test_5_0_km_boundary(self):
        assert CooldownTimer._lookup(5.0) == 30.0

    def test_5_01_km_triggers_120s(self):
        assert CooldownTimer._lookup(5.01) == 120.0

    def test_10_km_boundary(self):
        assert CooldownTimer._lookup(10.0) == 120.0

    def test_25_km_boundary(self):
        assert CooldownTimer._lookup(25.0) == 300.0

    def test_100_km_boundary(self):
        assert CooldownTimer._lookup(100.0) == 900.0

    def test_250_km_boundary(self):
        assert CooldownTimer._lookup(250.0) == 1500.0

    def test_500_km_boundary(self):
        assert CooldownTimer._lookup(500.0) == 2700.0

    def test_750_km_boundary(self):
        assert CooldownTimer._lookup(750.0) == 3600.0

    def test_1000_km_boundary(self):
        assert CooldownTimer._lookup(1000.0) == 5400.0

    def test_9999_km_falls_through(self):
        assert CooldownTimer._lookup(9999.0) == 7200.0


class TestStart:
    def test_short_jump_no_cooldown(self):
        ct = CooldownTimer()
        secs = ct.start(0.0, 0.0, 0.0, 0.0)  # same point → 0 km → 0s
        assert secs == 0.0
        assert ct.is_active is False

    def test_medium_jump_activates(self):
        # 0.01° lat ≈ 1.11 km → _lookup(1.11) = 30s
        ct = CooldownTimer()
        secs = ct.start(0.0, 0.0, 0.01, 0.0)
        assert secs == 30.0
        assert ct.is_active is True

    def test_large_jump_max_cooldown(self):
        # Taipei to Tokyo ~2100 km → 7200s
        ct = CooldownTimer()
        secs = ct.start(25.0330, 121.5654, 35.6762, 139.6503)
        assert secs == 7200.0
        assert ct.is_active is True


class TestGetStatus:
    def test_inactive_returns_zeroes(self):
        ct = CooldownTimer()
        s = ct.get_status()
        assert s["active"] is False
        assert s["remaining_sec"] == 0
        assert s["total_sec"] == 0

    def test_active_reports_remaining(self):
        ct = CooldownTimer()
        ct.start(0.0, 0.0, 0.01, 0.0)  # 30s
        s = ct.get_status()
        assert s["active"] is True
        assert 0.0 < s["remaining_sec"] <= 30.0
        assert s["total_sec"] == 30.0


class TestTick:
    def test_inactive_returns_false(self):
        ct = CooldownTimer()
        assert ct.tick() is False

    def test_unexpired_returns_false(self):
        ct = CooldownTimer()
        ct.start(0.0, 0.0, 0.01, 0.0)  # 30s
        assert ct.tick() is False

    def test_expired_returns_true_and_deactivates(self):
        ct = CooldownTimer()
        ct.start(0.0, 0.0, 0.01, 0.0)  # 30s
        ct._start_time -= 31             # wind clock forward past expiry
        assert ct.tick() is True
        assert ct.is_active is False

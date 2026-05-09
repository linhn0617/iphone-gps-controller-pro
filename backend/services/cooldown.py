from __future__ import annotations

import time
from backend.config import COOLDOWN_TABLE
from backend.services.interpolator import RouteInterpolator


class CooldownTimer:
    def __init__(self):
        self.enabled: bool = True
        self.is_active: bool = False
        self._start_time: float = 0.0
        self._total_sec: float = 0.0
        self._distance_km: float = 0.0

    def start(self, from_lat: float, from_lng: float, to_lat: float, to_lng: float) -> float:
        dist_km = RouteInterpolator.haversine(from_lat, from_lng, to_lat, to_lng) / 1000.0
        secs = self._lookup(dist_km)
        if secs <= 0:
            return 0.0
        self.is_active = True
        self._start_time = time.monotonic()
        self._total_sec = secs
        self._distance_km = dist_km
        return secs

    def get_status(self) -> dict:
        if not self.is_active:
            return {"active": False, "remaining_sec": 0, "total_sec": 0, "distance_km": 0}
        remaining = max(self._total_sec - (time.monotonic() - self._start_time), 0.0)
        if remaining <= 0:
            self.is_active = False
        return {
            "active": self.is_active,
            "remaining_sec": remaining,
            "total_sec": self._total_sec,
            "distance_km": self._distance_km,
        }

    def tick(self) -> bool:
        """Returns True if cooldown just ended."""
        if not self.is_active:
            return False
        elapsed = time.monotonic() - self._start_time
        if elapsed >= self._total_sec:
            self.is_active = False
            return True
        return False

    @staticmethod
    def _lookup(dist_km: float) -> float:
        for threshold_km, secs in COOLDOWN_TABLE:
            if dist_km <= threshold_km:
                return float(secs)
        return float(COOLDOWN_TABLE[-1][1])

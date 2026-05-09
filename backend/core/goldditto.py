"""Pokemon GO GoldDitto cycle — teleport a sequence of coordinates to
trigger Ditto encounters. The pattern uses offsets from a center point
that land in adjacent S2 cells (L14/L17 boundaries)."""
from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from backend.services.interpolator import RouteInterpolator

if TYPE_CHECKING:
    from backend.core.simulation_engine import SimulationEngine

_log = logging.getLogger(__name__)

# Approximate offsets (metres) that cross S2 L17 cell boundaries.
# These are empirical offsets used by the PoGo community.
_DITTO_OFFSETS: list[tuple[float, float]] = [
    (0, 0),
    (100, 0),
    (-100, 0),
    (0, 100),
    (0, -100),
    (70, 70),
    (-70, 70),
    (70, -70),
    (-70, -70),
    (0, 0),   # return to center
]

_DWELL_SEC = 2.0   # seconds to stay at each offset


class GoldDittoCycle:
    def __init__(self, engine: "SimulationEngine"):
        self._eng = engine

    async def run(
        self,
        center_lat: float,
        center_lng: float,
        *,
        dwell_sec: float = _DWELL_SEC,
        repeat: int = 1,
    ) -> None:
        eng = self._eng
        await eng.stop()

        async def _run():
            try:
                for _rep in range(repeat):
                    for bearing, distance in _offset_to_bearing_dist(_DITTO_OFFSETS):
                        if eng._stop_event.is_set():
                            return
                        lat, lng = RouteInterpolator.move_point(center_lat, center_lng, bearing, distance)
                        await eng.teleport(lat, lng)
                        try:
                            await asyncio.wait_for(eng._stop_event.wait(), timeout=dwell_sec)
                        except asyncio.TimeoutError:
                            pass
                await eng._emit("goldditto_complete", {"udid": eng.udid})
            except asyncio.CancelledError:
                pass

        eng._stop_event.clear()
        eng._task = asyncio.create_task(_run())


def _offset_to_bearing_dist(offsets: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Convert (north_m, east_m) offsets to (bearing_deg, distance_m)."""
    import math
    result = []
    for north, east in offsets:
        dist = math.sqrt(north ** 2 + east ** 2)
        if dist == 0:
            result.append((0.0, 0.0))
        else:
            bearing = (math.degrees(math.atan2(east, north)) + 360) % 360
            result.append((bearing, dist))
    return result

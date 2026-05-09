from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from backend.config import resolve_speed_profile
from backend.models.schemas import ResumableSnapshot, SimulationState
from backend.services.route_service import RouteService

if TYPE_CHECKING:
    from backend.core.simulation_engine import SimulationEngine

_log = logging.getLogger(__name__)

_route_service = RouteService()


class RouteLooper:
    def __init__(self, engine: "SimulationEngine"):
        self._eng = engine

    async def start_loop(
        self,
        waypoints: list[dict],
        *,
        mode: str = "walking",
        speed_kmh: float | None = None,
        lap_count: int | None = None,
    ) -> None:
        if len(waypoints) < 2:
            raise ValueError("At least 2 waypoints required for loop")
        eng = self._eng
        await eng.stop()
        eng.state = SimulationState.LOOPING

        wp_coords = [(float(w["lat"]), float(w["lng"])) for w in waypoints]
        # Close the loop: append first point at end
        closed = wp_coords + [wp_coords[0]]

        snap = ResumableSnapshot(
            kind="route_loop",
            args={"waypoints": waypoints, "mode": mode, "speed_kmh": speed_kmh, "lap_count": lap_count},
        )
        eng._resume_snapshot = snap

        async def _run():
            laps_done = snap.lap_count
            try:
                while True:
                    if lap_count is not None and laps_done >= lap_count:
                        await eng._emit("loop_complete", {"udid": eng.udid, "laps": laps_done})
                        break

                    # Each lap fetches fresh OSRM routes for each segment
                    for leg_idx in range(len(closed) - 1):
                        if eng._stop_event.is_set():
                            return
                        A, B = closed[leg_idx], closed[leg_idx + 1]
                        profile = resolve_speed_profile(mode=mode, speed_kmh=speed_kmh)
                        coords = await _route_service.get_route(A[0], A[1], B[0], B[1], mode=mode)
                        await eng._emit("route_path", {"udid": eng.udid, "coords": coords})
                        await eng._move_along_route(coords, profile)
                        if eng._stop_event.is_set():
                            return

                    laps_done += 1
                    snap.lap_count = laps_done
                    await eng._emit("lap_complete", {"udid": eng.udid, "lap": laps_done})

            except asyncio.CancelledError:
                pass
            except Exception as exc:
                _log.error("[%s] route_loop error: %s", eng.udid, exc)
            finally:
                if eng.state == SimulationState.LOOPING:
                    eng.state = SimulationState.IDLE

        eng._stop_event.clear()
        eng._task = asyncio.create_task(_run())

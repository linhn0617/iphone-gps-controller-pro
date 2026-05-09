from __future__ import annotations

import asyncio
import logging
import random
from typing import TYPE_CHECKING

from backend.config import resolve_speed_profile
from backend.models.schemas import ResumableSnapshot, SimulationState
from backend.services.interpolator import RouteInterpolator
if TYPE_CHECKING:
    from backend.core.simulation_engine import SimulationEngine

_log = logging.getLogger(__name__)

_NEAR_THRESHOLD_M = 50.0


class MultiStopNavigator:
    def __init__(self, engine: "SimulationEngine"):
        self._eng = engine

    async def start(
        self,
        waypoints: list[dict],      # [{"lat": ..., "lng": ...}, ...]
        *,
        mode: str = "walking",
        speed_kmh: float | None = None,
        speed_min_kmh: float | None = None,
        speed_max_kmh: float | None = None,
        stop_duration: float = 0.0,
        pause_min: float = 1.0,
        pause_max: float = 3.0,
        loop: bool = False,
        jump_mode: bool = False,
        jump_interval: float = 2.0,
    ) -> None:
        if len(waypoints) < 2:
            raise ValueError("At least 2 waypoints required")
        eng = self._eng
        await eng.stop()
        eng.state = SimulationState.MULTI_STOP

        wp_coords = [(float(w["lat"]), float(w["lng"])) for w in waypoints]

        snap = ResumableSnapshot(
            kind="multi_stop",
            args={
                "waypoints": waypoints, "mode": mode, "speed_kmh": speed_kmh,
                "stop_duration": stop_duration, "loop": loop,
                "jump_mode": jump_mode, "jump_interval": jump_interval,
            },
        )
        eng._resume_snapshot = snap

        async def _run():
            try:
                while True:
                    start_leg = snap.user_waypoint_next

                    # Pre-navigate to first stop if far away
                    if start_leg == 0 and eng.position:
                        dist = RouteInterpolator.haversine(
                            eng.position.lat, eng.position.lng,
                            wp_coords[0][0], wp_coords[0][1],
                        )
                        if dist > _NEAR_THRESHOLD_M:
                            coords = await eng._route_service.get_route(
                                eng.position.lat, eng.position.lng,
                                wp_coords[0][0], wp_coords[0][1],
                                mode=mode,
                            )
                            profile = resolve_speed_profile(mode=mode, speed_kmh=speed_kmh)
                            await eng._emit("route_path", {"udid": eng.udid, "coords": coords})
                            await eng._move_along_route(coords, profile)

                    for leg_idx in range(start_leg, len(wp_coords) - 1):
                        if eng._stop_event.is_set():
                            return
                        snap.user_waypoint_next = leg_idx + 1

                        A, B = wp_coords[leg_idx], wp_coords[leg_idx + 1]
                        profile = resolve_speed_profile(
                            mode=mode, speed_kmh=speed_kmh,
                            speed_min_kmh=speed_min_kmh, speed_max_kmh=speed_max_kmh,
                        )

                        if jump_mode:
                            await eng.teleport(B[0], B[1])
                            try:
                                await asyncio.wait_for(eng._stop_event.wait(), timeout=jump_interval)
                            except asyncio.TimeoutError:
                                pass
                        else:
                            coords = await eng._route_service.get_route(A[0], A[1], B[0], B[1], mode=mode)
                            await eng._emit("route_path", {"udid": eng.udid, "coords": coords})
                            await eng._move_along_route(coords, profile)

                        if eng._stop_event.is_set():
                            return

                        await eng._emit("stop_reached", {
                            "udid": eng.udid,
                            "stop_idx": leg_idx + 1,
                            "lat": B[0], "lng": B[1],
                        })

                        pause = stop_duration if stop_duration > 0 else random.uniform(pause_min, pause_max)
                        try:
                            await asyncio.wait_for(eng._stop_event.wait(), timeout=pause)
                        except asyncio.TimeoutError:
                            pass

                    if loop:
                        snap.user_waypoint_next = 0
                        snap.lap_count += 1
                        await eng._emit("lap_complete", {"udid": eng.udid, "lap": snap.lap_count})
                    else:
                        break

            except asyncio.CancelledError:
                pass
            except Exception as exc:
                _log.error("[%s] multi_stop error: %s", eng.udid, exc)
            finally:
                if eng.state == SimulationState.MULTI_STOP:
                    eng.state = SimulationState.IDLE
                await eng._emit("multi_stop_complete", {"udid": eng.udid})

        eng._stop_event.clear()
        eng._task = asyncio.create_task(_run())

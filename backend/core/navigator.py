from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from backend.config import resolve_speed_profile
from backend.models.schemas import MovementMode, ResumableSnapshot, SimulationState
from backend.services.route_service import RouteService

if TYPE_CHECKING:
    from backend.core.simulation_engine import SimulationEngine

_log = logging.getLogger(__name__)

_route_service = RouteService()


class Navigator:
    def __init__(self, engine: "SimulationEngine"):
        self._eng = engine

    async def navigate(
        self,
        lat: float,
        lng: float,
        *,
        mode: str = "walking",
        speed_kmh: float | None = None,
        force_straight: bool = False,
    ) -> None:
        eng = self._eng
        await eng.stop()

        from backend.models.schemas import Coordinate
        eng.destination = Coordinate(lat, lng)
        eng.mode = MovementMode(mode) if mode in MovementMode._value2member_map_ else MovementMode.WALKING
        eng.state = SimulationState.NAVIGATING

        speed_profile = resolve_speed_profile(mode=mode, speed_kmh=speed_kmh)

        if not eng.position:
            _log.warning("[%s] navigate called with no current position — teleporting first", eng.udid)
            await eng.teleport(lat, lng)
            return

        cur = eng.position

        async def _run():
            try:
                coords = await _route_service.get_route(
                    cur.lat, cur.lng, lat, lng,
                    mode=mode, force_straight=force_straight,
                )
                await eng._emit("route_path", {"udid": eng.udid, "coords": coords})

                eng._resume_snapshot = ResumableSnapshot(
                    kind="navigate",
                    args={"lat": lat, "lng": lng, "mode": mode, "speed_kmh": speed_kmh},
                    current_pos=(cur.lat, cur.lng),
                )

                await eng._move_along_route(coords, speed_profile)

                eng.state = SimulationState.IDLE
                eng.destination = None
                await eng._emit("navigation_complete", {"udid": eng.udid, "lat": lat, "lng": lng})
            except asyncio.CancelledError:
                pass
            except Exception as exc:
                _log.error("[%s] navigate error: %s", eng.udid, exc)
                eng.state = SimulationState.IDLE

        eng._stop_event.clear()
        eng._task = asyncio.create_task(_run())

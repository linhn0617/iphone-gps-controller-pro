from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING

from backend.config import resolve_speed_profile
from backend.models.schemas import SimulationState
from backend.services.interpolator import RouteInterpolator

if TYPE_CHECKING:
    from backend.core.simulation_engine import SimulationEngine

_log = logging.getLogger(__name__)

_TICK_INTERVAL = 0.2  # 5 Hz


class JoystickHandler:
    def __init__(self, engine: "SimulationEngine", mode: str = "walking"):
        self._eng = engine
        self._mode = mode
        self._direction: float = 0.0
        self._intensity: float = 0.0
        self._active = False
        self._task: asyncio.Task | None = None
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        eng = self._eng
        if not eng.position:
            raise ValueError("No current position — teleport first")
        eng.state = SimulationState.JOYSTICK
        self._active = True
        self._task = asyncio.create_task(self._tick_loop())

    async def update_input(self, data: dict) -> None:
        async with self._lock:
            self._direction = float(data.get("direction", self._direction))
            self._intensity = float(data.get("intensity", self._intensity))
            self._active = True

    async def stop(self) -> None:
        self._active = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
        self._task = None

    async def _tick_loop(self) -> None:
        eng = self._eng
        profile = resolve_speed_profile(mode=self._mode)
        try:
            while self._active and not eng._stop_event.is_set():
                tick_start = time.monotonic()
                async with self._lock:
                    direction = self._direction
                    intensity = self._intensity

                if intensity > 0 and eng.position:
                    speed_mps = profile["speed_mps"] * intensity
                    distance_m = speed_mps * _TICK_INTERVAL
                    lat, lng = RouteInterpolator.move_point(
                        eng.position.lat, eng.position.lng, direction, distance_m
                    )
                    lat, lng = RouteInterpolator.add_jitter(lat, lng, profile["jitter"] * 0.3)
                    await eng._set_position(lat, lng)
                    await eng._emit("position_update", eng._status_dict())

                elapsed = time.monotonic() - tick_start
                await asyncio.sleep(max(_TICK_INTERVAL - elapsed, 0))
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            _log.error("[%s] joystick error: %s", eng.udid, exc)
        finally:
            if eng.state == SimulationState.JOYSTICK:
                eng.state = SimulationState.IDLE

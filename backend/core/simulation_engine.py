from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING, Any

from backend.api.websocket import broadcast
from backend.models.schemas import (
    Coordinate, MovementMode, ResumableSnapshot, SimulationState, SimulationStatus,
)
from backend.services.interpolator import RouteInterpolator

if TYPE_CHECKING:
    pass

_log = logging.getLogger(__name__)


class SimulationEngine:
    def __init__(self, udid: str, set_pos_fn, clear_pos_fn):
        self.udid = udid
        self._set_pos_fn = set_pos_fn    # async fn(lat, lng) — calls GPS worker
        self._clear_pos_fn = clear_pos_fn  # async fn()

        self.state = SimulationState.IDLE
        self.position: Coordinate | None = None
        self.mode = MovementMode.WALKING
        self.speed_kmh: float | None = None
        self.destination: Coordinate | None = None
        self.is_primary = False
        self.connected = False

        self._task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()
        self._resume_snapshot: ResumableSnapshot | None = None

        # Set by device_manager when joystick mode active
        self.joystick_handler = None

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    async def teleport(self, lat: float, lng: float) -> None:
        await self.stop()
        self.state = SimulationState.TELEPORTING
        await self._set_position(lat, lng)
        self.state = SimulationState.IDLE
        await self._emit("position_update", self._status_dict())

    async def navigate(
        self, lat: float, lng: float, *, mode: str = "walking",
        speed_kmh: float | None = None, force_straight: bool = False,
    ) -> None:
        from backend.core.navigator import Navigator
        await Navigator(self).navigate(lat, lng, mode=mode, speed_kmh=speed_kmh, force_straight=force_straight)

    async def stop(self) -> None:
        if self._task and not self._task.done():
            self._stop_event.set()
            try:
                await asyncio.wait_for(self._task, timeout=3.0)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                self._task.cancel()
        self._stop_event.clear()
        self._task = None
        if self.joystick_handler:
            await self.joystick_handler.stop()
            self.joystick_handler = None
        self.state = SimulationState.IDLE
        await self._emit("state_change", {"state": self.state.value, "udid": self.udid})

    async def clear(self) -> None:
        await self.stop()
        await self._clear_pos_fn()
        self.position = None
        await self._emit("position_update", self._status_dict())

    # ------------------------------------------------------------------ #
    # Core movement loop                                                   #
    # ------------------------------------------------------------------ #

    async def _move_along_route(
        self,
        coords: list[tuple[float, float]],
        speed_profile: dict[str, Any],
        *,
        start_segment: int = 0,
    ) -> None:
        """Tick-budgeted movement loop. coords is list of (lat, lng) points."""
        update_interval: float = speed_profile["update_interval"]
        jitter: float = speed_profile.get("jitter", 0.5)
        speed_mps: float = speed_profile["speed_mps"]
        step_m: float = speed_mps * update_interval

        # Pre-expand coords into dense points
        dense: list[tuple[float, float]] = []
        for i in range(len(coords) - 1):
            seg = RouteInterpolator.interpolate(
                coords[i][0], coords[i][1],
                coords[i + 1][0], coords[i + 1][1],
                step_m=step_m,
            )
            dense.extend(seg)
        if not dense:
            return

        for idx in range(start_segment, len(dense)):
            if self._stop_event.is_set():
                return
            tick_start = time.monotonic()
            lat, lng = dense[idx]
            if jitter > 0:
                lat, lng = RouteInterpolator.add_jitter(lat, lng, jitter * 0.3)
            await self._set_position(lat, lng)
            await self._emit("position_update", self._status_dict())
            elapsed = time.monotonic() - tick_start
            await asyncio.sleep(max(update_interval - elapsed, 0))

    # ------------------------------------------------------------------ #
    # Leadership / snapshot                                               #
    # ------------------------------------------------------------------ #

    def capture_resumable_snapshot(self) -> ResumableSnapshot | None:
        return self._resume_snapshot

    async def resume_from_snapshot(self, snap: ResumableSnapshot) -> None:
        if snap.current_pos:
            await self.teleport(snap.current_pos[0], snap.current_pos[1])
        _log.info("Engine %s resuming from snapshot kind=%s", self.udid, snap.kind)

    # ------------------------------------------------------------------ #
    # Internals                                                            #
    # ------------------------------------------------------------------ #

    async def _set_position(self, lat: float, lng: float) -> None:
        for attempt in range(3):
            try:
                await self._set_pos_fn(lat, lng)
                self.position = Coordinate(lat, lng)
                return
            except (ConnectionError, OSError) as exc:
                if attempt == 2:
                    raise
                await asyncio.sleep(0.5 * (attempt + 1))

    async def _emit(self, event_type: str, data: Any) -> None:
        await broadcast(event_type, data)

    def _status_dict(self) -> dict[str, Any]:
        return SimulationStatus(
            udid=self.udid,
            state=self.state,
            position=self.position,
            mode=self.mode,
            speed_kmh=self.speed_kmh,
            destination=self.destination,
            is_primary=self.is_primary,
            connected=self.connected,
        ).to_dict()

    def get_status(self) -> SimulationStatus:
        return SimulationStatus(
            udid=self.udid,
            state=self.state,
            position=self.position,
            mode=self.mode,
            speed_kmh=self.speed_kmh,
            destination=self.destination,
            is_primary=self.is_primary,
            connected=self.connected,
        )

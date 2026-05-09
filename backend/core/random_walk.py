from __future__ import annotations

import asyncio
import logging
import random
import time
from typing import TYPE_CHECKING

from backend.config import resolve_speed_profile
from backend.models.schemas import ResumableSnapshot, SimulationState
from backend.services.interpolator import RouteInterpolator
from backend.services.route_service import RouteService

if TYPE_CHECKING:
    from backend.core.simulation_engine import SimulationEngine

_log = logging.getLogger(__name__)

_route_service = RouteService()

_MAX_GENERAL_ERRORS = 5
_MAX_CONN_ERRORS    = 60
_CONN_RETRY_BASE    = 5.0
_CONN_RETRY_MAX     = 30.0


class RandomWalkHandler:
    def __init__(self, engine: "SimulationEngine"):
        self._eng = engine

    async def start(
        self,
        center_lat: float,
        center_lng: float,
        radius_m: float,
        *,
        mode: str = "walking",
        speed_kmh: float | None = None,
        speed_min_kmh: float | None = None,
        speed_max_kmh: float | None = None,
        pause_min: float = 1.0,
        pause_max: float = 3.0,
        seed: int | None = None,
        straight_line: bool = False,
    ) -> None:
        eng = self._eng
        await eng.stop()
        eng.state = SimulationState.RANDOM_WALK

        rng = random.Random(seed)
        walk_count = 0

        snap = ResumableSnapshot(
            kind="random_walk",
            args={
                "center_lat": center_lat, "center_lng": center_lng,
                "radius_m": radius_m, "mode": mode, "speed_kmh": speed_kmh,
                "seed": seed, "straight_line": straight_line,
                "pause_min": pause_min, "pause_max": pause_max,
            },
        )
        eng._resume_snapshot = snap

        if eng._resume_snapshot and eng._resume_snapshot.random_walk_count > 0:
            for _ in range(eng._resume_snapshot.random_walk_count):
                RouteInterpolator.random_point_in_radius(center_lat, center_lng, radius_m, rng)

        async def _run():
            nonlocal walk_count
            gen_errors = 0
            conn_errors = 0
            conn_backoff = _CONN_RETRY_BASE
            try:
                while not eng._stop_event.is_set():
                    dest_lat, dest_lng = RouteInterpolator.random_point_in_radius(
                        center_lat, center_lng, radius_m, rng
                    )
                    walk_count += 1
                    snap.random_walk_count = walk_count

                    profile = resolve_speed_profile(
                        mode=mode, speed_kmh=speed_kmh,
                        speed_min_kmh=speed_min_kmh, speed_max_kmh=speed_max_kmh,
                    )
                    cur = eng.position
                    if not cur:
                        cur_lat, cur_lng = center_lat, center_lng
                    else:
                        cur_lat, cur_lng = cur.lat, cur.lng

                    try:
                        coords = await _route_service.get_route(
                            cur_lat, cur_lng, dest_lat, dest_lng,
                            mode=mode, force_straight=straight_line,
                        )
                        await eng._emit("route_path", {"udid": eng.udid, "coords": coords})
                        await eng._move_along_route(coords, profile)
                        conn_errors = 0
                        conn_backoff = _CONN_RETRY_BASE
                        gen_errors = 0
                    except (ConnectionError, OSError) as exc:
                        conn_errors += 1
                        if conn_errors >= _MAX_CONN_ERRORS:
                            _log.error("[%s] random_walk: too many connection errors", eng.udid)
                            break
                        _log.warning("[%s] random_walk connection error (%d/%d): %s", eng.udid, conn_errors, _MAX_CONN_ERRORS, exc)
                        await asyncio.sleep(conn_backoff)
                        conn_backoff = min(conn_backoff * 2, _CONN_RETRY_MAX)
                        continue
                    except Exception as exc:
                        gen_errors += 1
                        if gen_errors >= _MAX_GENERAL_ERRORS:
                            _log.error("[%s] random_walk: too many errors: %s", eng.udid, exc)
                            break
                        _log.warning("[%s] random_walk error: %s", eng.udid, exc)
                        continue

                    if eng._stop_event.is_set():
                        break
                    pause = rng.uniform(pause_min, pause_max)
                    try:
                        await asyncio.wait_for(eng._stop_event.wait(), timeout=pause)
                    except asyncio.TimeoutError:
                        pass
            except asyncio.CancelledError:
                pass
            finally:
                if eng.state == SimulationState.RANDOM_WALK:
                    eng.state = SimulationState.IDLE

        eng._stop_event.clear()
        eng._task = asyncio.create_task(_run())

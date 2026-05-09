#!/usr/bin/env python3
import asyncio, logging, sys
from pathlib import Path
from aiohttp import web
from aiohttp.web_middlewares import middleware

from backend.config import API_HOST, API_PORT
from backend.core.device_manager import (
    device_scanner, get_devices,
    register_device_ready_callback, register_device_removed_callback,
    _SetCmd, _ClearCmd,
)
from backend.core.simulation_engine import SimulationEngine
from backend.services.cooldown import CooldownTimer
from backend.api.location import (
    route_devices, route_set, route_clear, route_device_status,
    route_navigate, route_stop,
    route_joystick_start, route_random_walk_start,
    route_multi_stop_start, route_route_loop_start,
    route_cooldown_status,
)
from backend.api.websocket import route_ws_status, broadcast
from backend.api.device import route_wifi_toggle

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s  %(levelname)-7s  %(message)s',
    datefmt='%H:%M:%S',
)
logging.getLogger('aiohttp.access').setLevel(logging.WARNING)
logging.getLogger('aiohttp.server').setLevel(logging.WARNING)

FRONTEND_DIR = Path(__file__).parent.parent / 'frontend'
_log = logging.getLogger('launcher')

_FOLLOWER_POLL_INTERVAL = 0.5   # seconds


class AppState:
    """Central holder for per-device SimulationEngines and cooldown."""
    def __init__(self):
        self.engines: dict[str, SimulationEngine] = {}
        self.primary_udid: str | None = None
        self.cooldown = CooldownTimer()
        self._follower_tasks: dict[str, asyncio.Task] = {}

    # ── Engine creation ──────────────────────────────────────────────── #

    async def create_engine_for_device(self, ctx) -> None:
        udid = ctx.udid

        async def _set_pos(lat: float, lng: float) -> None:
            ctx._mailbox.post(_SetCmd(lat, lng))

        async def _clear_pos() -> None:
            ctx._mailbox.post(_ClearCmd())

        eng = SimulationEngine(udid, _set_pos, _clear_pos)
        eng.connected = True

        if not self.primary_udid:
            self.primary_udid = udid
            eng.is_primary = True
        else:
            # New follower — sync to leader position
            asyncio.create_task(self._auto_sync_new_device(udid))

        self.engines[udid] = eng
        _log.info("Engine created for %s  primary=%s", ctx.name, eng.is_primary)
        await broadcast("device_connected", {
            "udid": udid, "name": ctx.name, "ios": ctx.ios, "is_primary": eng.is_primary,
        })

    # ── Device removal + leadership handoff ──────────────────────────── #

    async def on_device_removed(self, udid: str) -> None:
        eng = self.engines.get(udid)
        if not eng:
            return

        snap = eng.capture_resumable_snapshot()
        was_primary = eng.is_primary

        # Cancel follower task for this device
        ft = self._follower_tasks.pop(udid, None)
        if ft:
            ft.cancel()

        await eng.stop()
        del self.engines[udid]
        await broadcast("device_disconnected", {"udid": udid})

        if was_primary:
            self.primary_udid = None
            # Promote the next available engine to leader
            for new_udid, new_eng in self.engines.items():
                new_eng.is_primary = True
                self.primary_udid = new_udid
                _log.info("Leadership handed to %s", new_udid)
                await broadcast("leadership_change", {"udid": new_udid})
                if snap:
                    asyncio.create_task(new_eng.resume_from_snapshot(snap))
                break

    # ── Follower sync ─────────────────────────────────────────────────── #

    async def _auto_sync_new_device(self, follower_udid: str) -> None:
        if not self.primary_udid or self.primary_udid not in self.engines:
            return
        leader = self.engines[self.primary_udid]
        if not leader.position:
            return
        follower = self.engines.get(follower_udid)
        if not follower:
            return
        # Teleport follower to leader's current position
        await follower.teleport(leader.position.lat, leader.position.lng)
        # Start following leader's real-time position
        task = asyncio.create_task(self._follow_primary_positions(follower_udid))
        self._follower_tasks[follower_udid] = task

    async def _follow_primary_positions(self, follower_udid: str) -> None:
        while True:
            await asyncio.sleep(_FOLLOWER_POLL_INTERVAL)
            if follower_udid not in self.engines:
                return
            follower = self.engines[follower_udid]
            if follower.is_primary:
                return
            if not self.primary_udid or self.primary_udid not in self.engines:
                return
            leader = self.engines[self.primary_udid]
            if leader.position:
                try:
                    await follower._set_position(leader.position.lat, leader.position.lng)
                except Exception:
                    pass

    # ── Cooldown guard ────────────────────────────────────────────────── #

    def check_cooldown(self) -> dict | None:
        if not self.cooldown.enabled:
            return None
        status = self.cooldown.get_status()
        if status["active"]:
            return status
        return None

    async def start_cooldown(self, from_lat: float, from_lng: float, to_lat: float, to_lng: float) -> float:
        secs = self.cooldown.start(from_lat, from_lng, to_lat, to_lng)
        if secs > 0:
            await broadcast("cooldown_active", self.cooldown.get_status())
            asyncio.create_task(self._cooldown_tick())
        return secs

    async def _cooldown_tick(self) -> None:
        while True:
            await asyncio.sleep(1.0)
            ended = self.cooldown.tick()
            if ended:
                await broadcast("cooldown_ended", {})
                return


_app_state = AppState()


@middleware
async def cors_middleware(request, handler):
    if request.method == 'OPTIONS':
        return web.Response(headers={
            'Access-Control-Allow-Origin':  '*',
            'Access-Control-Allow-Methods': 'GET,POST,OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type',
        })
    resp = await handler(request)
    resp.headers['Access-Control-Allow-Origin'] = '*'
    return resp


async def main():
    register_device_ready_callback(_app_state.create_engine_for_device)
    register_device_removed_callback(_app_state.on_device_removed)
    asyncio.create_task(device_scanner())

    app = web.Application(middlewares=[cors_middleware])
    app["_app_state"] = _app_state

    # API routes
    app.router.add_get ('/api/devices',              route_devices)
    app.router.add_get ('/devices',                  route_devices)
    app.router.add_post('/api/device/{idx}/set',     route_set)
    app.router.add_post('/api/device/{idx}/clear',   route_clear)
    app.router.add_get ('/api/device/{idx}/status',  route_device_status)
    app.router.add_post('/device/{idx}/set',         route_set)
    app.router.add_post('/device/{idx}/clear',       route_clear)
    app.router.add_get ('/device/{idx}/status',      route_device_status)

    app.router.add_post('/api/device/{idx}/navigate',         route_navigate)
    app.router.add_post('/api/device/{idx}/stop',             route_stop)
    app.router.add_post('/api/device/{idx}/joystick/start',   route_joystick_start)
    app.router.add_post('/api/device/{idx}/random-walk/start',route_random_walk_start)
    app.router.add_post('/api/device/{idx}/multi-stop/start', route_multi_stop_start)
    app.router.add_post('/api/device/{idx}/route-loop/start', route_route_loop_start)
    app.router.add_get ('/api/cooldown',                             route_cooldown_status)
    app.router.add_post('/api/device/{idx}/wifi-tunnel',             route_wifi_toggle)

    # WebSocket
    app.router.add_get('/ws/status', route_ws_status)

    for path in ['/api/device/{idx}/set', '/api/device/{idx}/clear',
                 '/device/{idx}/set', '/device/{idx}/clear']:
        app.router.add_route('OPTIONS', path, lambda r: web.Response())

    # Frontend static files
    if FRONTEND_DIR.exists():
        app.router.add_static('/static', FRONTEND_DIR)
        async def serve_index(request):
            return web.FileResponse(FRONTEND_DIR / 'index.html')
        app.router.add_get('/', serve_index)

    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, API_HOST, API_PORT).start()

    _log.info(f'GPS Controller Pro  port={API_PORT}')
    _log.info(f'   http://localhost:{API_PORT}/')
    _log.info('Scanning USB devices...')

    await asyncio.Event().wait()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        _log.info('Stopped')

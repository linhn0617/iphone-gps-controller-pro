#!/usr/bin/env python3
import asyncio, logging, sys
from pathlib import Path
from aiohttp import web
from aiohttp.web_middlewares import middleware

from backend.config import API_HOST, API_PORT
from backend.core.device_manager import (
    device_scanner, get_devices, register_device_ready_callback,
    _SetCmd, _ClearCmd,
)
from backend.core.simulation_engine import SimulationEngine
from backend.api.location import (
    route_devices, route_set, route_clear, route_device_status,
)
from backend.api.websocket import route_ws_status, broadcast

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s  %(levelname)-7s  %(message)s',
    datefmt='%H:%M:%S',
)
logging.getLogger('aiohttp.access').setLevel(logging.WARNING)
logging.getLogger('aiohttp.server').setLevel(logging.WARNING)

FRONTEND_DIR = Path(__file__).parent.parent / 'frontend'
_log = logging.getLogger('launcher')


class AppState:
    """Central holder for per-device SimulationEngines."""
    def __init__(self):
        self.engines: dict[str, SimulationEngine] = {}
        self.primary_udid: str | None = None

    def get_engine(self, udid: str) -> SimulationEngine | None:
        return self.engines.get(udid)

    def get_or_first_engine(self, idx: int) -> SimulationEngine | None:
        devices = get_devices()
        udids = list(devices.keys())
        if idx < 0 or idx >= len(udids):
            return None
        return self.engines.get(udids[idx])

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

        self.engines[udid] = eng
        _log.info("Engine created for %s  primary=%s", ctx.name, eng.is_primary)
        await broadcast("device_connected", {
            "udid": udid,
            "name": ctx.name,
            "ios": ctx.ios,
            "is_primary": eng.is_primary,
        })

    def remove_engine(self, udid: str) -> None:
        eng = self.engines.pop(udid, None)
        if eng and eng.is_primary:
            self.primary_udid = None
            # Promote next available device
            for u, e in self.engines.items():
                e.is_primary = True
                self.primary_udid = u
                break


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

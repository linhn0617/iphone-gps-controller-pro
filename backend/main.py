#!/usr/bin/env python3
import asyncio, logging, sys
from pathlib import Path
from aiohttp import web
from aiohttp.web_middlewares import middleware

from backend.config import API_HOST, API_PORT
from backend.core.device_manager import device_scanner
from backend.api.location import (
    route_devices, route_set, route_clear, route_device_status,
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s  %(levelname)-7s  %(message)s',
    datefmt='%H:%M:%S',
)
logging.getLogger('aiohttp.access').setLevel(logging.WARNING)
logging.getLogger('aiohttp.server').setLevel(logging.WARNING)

FRONTEND_DIR = Path(__file__).parent.parent / 'frontend'


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
    asyncio.create_task(device_scanner())

    app = web.Application(middlewares=[cors_middleware])

    # API routes
    app.router.add_get ('/api/devices',              route_devices)
    app.router.add_get ('/devices',                  route_devices)         # legacy compat
    app.router.add_post('/api/device/{idx}/set',     route_set)
    app.router.add_post('/api/device/{idx}/clear',   route_clear)
    app.router.add_get ('/api/device/{idx}/status',  route_device_status)
    app.router.add_post('/device/{idx}/set',         route_set)             # legacy compat
    app.router.add_post('/device/{idx}/clear',       route_clear)           # legacy compat
    app.router.add_get ('/device/{idx}/status',      route_device_status)   # legacy compat

    for path in ['/api/device/{idx}/set', '/api/device/{idx}/clear',
                 '/device/{idx}/set', '/device/{idx}/clear']:
        app.router.add_route('OPTIONS', path, lambda r: web.Response())

    # Serve frontend static files
    if FRONTEND_DIR.exists():
        app.router.add_static('/static', FRONTEND_DIR)
        async def serve_index(request):
            return web.FileResponse(FRONTEND_DIR / 'index.html')
        app.router.add_get('/', serve_index)

    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, API_HOST, API_PORT).start()

    _log = logging.getLogger('launcher')
    _log.info(f'GPS Controller Pro  port={API_PORT}')
    _log.info(f'   http://localhost:{API_PORT}/')
    _log.info('Scanning USB devices...')

    await asyncio.Event().wait()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.getLogger('launcher').info('Stopped')

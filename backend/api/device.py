"""Device management API — WiFi tunnel toggle, device rename, etc."""
import asyncio
from aiohttp import web
from backend.core.device_manager import get_devices


async def route_wifi_toggle(request: web.Request) -> web.Response:
    """POST /api/device/{idx}/wifi-tunnel — attempt WiFi tunnel switch."""
    idx = int(request.match_info.get('idx', -1))
    devices = get_devices()
    udids = list(devices.keys())
    if idx < 0 or idx >= len(udids):
        return web.json_response({'ok': False, 'error': 'device not found'}, status=404)
    udid = udids[idx]
    ctx = devices[udid]

    from backend.services.wifi_tunnel import start_wifi_tunnel
    from backend.core.device_manager import terminate_tunnel

    # Kill existing tunnel first
    await terminate_tunnel(ctx)
    ctx.rsd_host = None
    ctx.rsd_port = None

    result = await start_wifi_tunnel(udid)
    if result:
        ctx.rsd_host, ctx.rsd_port = result
        return web.json_response({'ok': True, 'rsd_host': ctx.rsd_host, 'rsd_port': ctx.rsd_port})
    else:
        return web.json_response({'ok': False, 'error': 'WiFi tunnel failed — keep USB connected'}, status=503)

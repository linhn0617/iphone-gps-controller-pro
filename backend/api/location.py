from aiohttp import web
from backend.core.device_manager import _devices, _SetCmd, _ClearCmd


def _get_ctx(request):
    idx = int(request.match_info.get('idx', -1))
    for ctx in _devices.values():
        if ctx.idx == idx:
            return ctx
    return None


async def route_devices(request):
    return web.json_response([c.to_dict() for c in _devices.values()])


async def route_set(request):
    ctx = _get_ctx(request)
    if not ctx:
        return web.json_response({'ok': False, 'error': 'device not found'}, status=404)
    if not ctx.state['connected']:
        return web.json_response({'ok': False, 'error': 'GPS not connected'}, status=503)
    try:
        data = await request.json()
        lat, lon = float(data['lat']), float(data['lon'])
    except Exception as e:
        return web.json_response({'ok': False, 'error': str(e)}, status=400)
    ctx._mailbox.post(_SetCmd(lat, lon))
    return web.json_response({'ok': True, 'lat': lat, 'lon': lon})


async def route_clear(request):
    ctx = _get_ctx(request)
    if not ctx:
        return web.json_response({'ok': False, 'error': 'device not found'}, status=404)
    if not ctx.state['connected']:
        return web.json_response({'ok': False, 'error': 'GPS not connected'}, status=503)
    ctx._mailbox.post(_ClearCmd())
    return web.json_response({'ok': True})


async def route_device_status(request):
    ctx = _get_ctx(request)
    if not ctx:
        return web.json_response({'ok': False, 'error': 'device not found'}, status=404)
    return web.json_response(ctx.to_dict())

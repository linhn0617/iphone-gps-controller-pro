from aiohttp import web
from backend.core.device_manager import get_devices


def _get_engine(request):
    idx = int(request.match_info.get('idx', -1))
    devices = get_devices()
    udids = list(devices.keys())
    if idx < 0 or idx >= len(udids):
        return None, None
    udid = udids[idx]
    ctx = devices[udid]
    state = request.app.get("_app_state")
    eng = state.engines.get(udid) if state else None
    return ctx, eng


async def route_devices(request):
    devices = get_devices()
    state = request.app.get("_app_state")
    result = []
    for ctx in devices.values():
        d = ctx.to_dict()
        if state:
            eng = state.engines.get(ctx.udid)
            if eng:
                d["is_primary"] = eng.is_primary
                d["state"] = eng.state.value
                pos = eng.position
                d["last_lat"] = pos.lat if pos else ctx.state.get("last_lat")
                d["last_lon"] = pos.lng if pos else ctx.state.get("last_lon")
        result.append(d)
    return web.json_response(result)


async def route_set(request):
    ctx, eng = _get_engine(request)
    if not ctx:
        return web.json_response({'ok': False, 'error': 'device not found'}, status=404)
    if not ctx.state['connected']:
        return web.json_response({'ok': False, 'error': 'GPS not connected'}, status=503)
    try:
        data = await request.json()
        lat, lon = float(data['lat']), float(data['lon'])
    except Exception as e:
        return web.json_response({'ok': False, 'error': str(e)}, status=400)

    if eng:
        await eng.teleport(lat, lon)
    else:
        from backend.core.device_manager import _SetCmd
        ctx._mailbox.post(_SetCmd(lat, lon))
    return web.json_response({'ok': True, 'lat': lat, 'lon': lon})


async def route_clear(request):
    ctx, eng = _get_engine(request)
    if not ctx:
        return web.json_response({'ok': False, 'error': 'device not found'}, status=404)
    if not ctx.state['connected']:
        return web.json_response({'ok': False, 'error': 'GPS not connected'}, status=503)

    if eng:
        await eng.clear()
    else:
        from backend.core.device_manager import _ClearCmd
        ctx._mailbox.post(_ClearCmd())
    return web.json_response({'ok': True})


async def route_device_status(request):
    ctx, eng = _get_engine(request)
    if not ctx:
        return web.json_response({'ok': False, 'error': 'device not found'}, status=404)
    d = ctx.to_dict()
    if eng:
        d["state"] = eng.state.value
        d["is_primary"] = eng.is_primary
        pos = eng.position
        if pos:
            d["last_lat"] = pos.lat
            d["last_lon"] = pos.lng
    return web.json_response(d)

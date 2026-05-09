import asyncio
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


async def route_navigate(request):
    ctx, eng = _get_engine(request)
    if not ctx:
        return web.json_response({'ok': False, 'error': 'device not found'}, status=404)
    if not ctx.state['connected']:
        return web.json_response({'ok': False, 'error': 'GPS not connected'}, status=503)
    try:
        data = await request.json()
        lat, lng = float(data['lat']), float(data['lng'])
    except Exception as e:
        return web.json_response({'ok': False, 'error': str(e)}, status=400)

    mode = data.get('mode', 'walking')
    speed_kmh = float(data['speed_kmh']) if 'speed_kmh' in data else None
    force_straight = bool(data.get('force_straight', False))

    if eng:
        asyncio.create_task(eng.navigate(lat, lng, mode=mode, speed_kmh=speed_kmh, force_straight=force_straight))
    return web.json_response({'ok': True})


async def route_stop(request):
    ctx, eng = _get_engine(request)
    if not ctx:
        return web.json_response({'ok': False, 'error': 'device not found'}, status=404)
    if eng:
        await eng.stop()
    return web.json_response({'ok': True})


async def route_joystick_start(request):
    ctx, eng = _get_engine(request)
    if not ctx:
        return web.json_response({'ok': False, 'error': 'device not found'}, status=404)
    if not ctx.state['connected']:
        return web.json_response({'ok': False, 'error': 'GPS not connected'}, status=503)
    if not eng:
        return web.json_response({'ok': False, 'error': 'engine not ready'}, status=503)
    try:
        data = await request.json()
    except Exception:
        data = {}
    mode = data.get('mode', 'walking')
    await eng.start_joystick(mode=mode)
    return web.json_response({'ok': True})


async def route_random_walk_start(request):
    ctx, eng = _get_engine(request)
    if not ctx:
        return web.json_response({'ok': False, 'error': 'device not found'}, status=404)
    if not ctx.state['connected']:
        return web.json_response({'ok': False, 'error': 'GPS not connected'}, status=503)
    if not eng:
        return web.json_response({'ok': False, 'error': 'engine not ready'}, status=503)
    try:
        data = await request.json()
        center_lat = float(data['center_lat'])
        center_lng = float(data['center_lng'])
        radius_m   = float(data['radius_m'])
    except Exception as e:
        return web.json_response({'ok': False, 'error': str(e)}, status=400)

    asyncio.create_task(eng.start_random_walk(
        center_lat, center_lng, radius_m,
        mode=data.get('mode', 'walking'),
        speed_kmh=float(data['speed_kmh']) if 'speed_kmh' in data else None,
        speed_min_kmh=float(data['speed_min_kmh']) if 'speed_min_kmh' in data else None,
        speed_max_kmh=float(data['speed_max_kmh']) if 'speed_max_kmh' in data else None,
        pause_min=float(data.get('pause_min', 1.0)),
        pause_max=float(data.get('pause_max', 3.0)),
        seed=int(data['seed']) if 'seed' in data else None,
        straight_line=bool(data.get('straight_line', False)),
    ))
    return web.json_response({'ok': True})


async def route_multi_stop_start(request):
    ctx, eng = _get_engine(request)
    if not ctx:
        return web.json_response({'ok': False, 'error': 'device not found'}, status=404)
    if not ctx.state['connected']:
        return web.json_response({'ok': False, 'error': 'GPS not connected'}, status=503)
    if not eng:
        return web.json_response({'ok': False, 'error': 'engine not ready'}, status=503)
    try:
        data = await request.json()
        waypoints = data['waypoints']
    except Exception as e:
        return web.json_response({'ok': False, 'error': str(e)}, status=400)

    asyncio.create_task(eng.start_multi_stop(
        waypoints,
        mode=data.get('mode', 'walking'),
        speed_kmh=float(data['speed_kmh']) if 'speed_kmh' in data else None,
        stop_duration=float(data.get('stop_duration', 0.0)),
        pause_min=float(data.get('pause_min', 1.0)),
        pause_max=float(data.get('pause_max', 3.0)),
        loop=bool(data.get('loop', False)),
        jump_mode=bool(data.get('jump_mode', False)),
        jump_interval=float(data.get('jump_interval', 2.0)),
    ))
    return web.json_response({'ok': True})


async def route_route_loop_start(request):
    ctx, eng = _get_engine(request)
    if not ctx:
        return web.json_response({'ok': False, 'error': 'device not found'}, status=404)
    if not ctx.state['connected']:
        return web.json_response({'ok': False, 'error': 'GPS not connected'}, status=503)
    if not eng:
        return web.json_response({'ok': False, 'error': 'engine not ready'}, status=503)
    try:
        data = await request.json()
        waypoints = data['waypoints']
    except Exception as e:
        return web.json_response({'ok': False, 'error': str(e)}, status=400)

    lap_count = int(data['lap_count']) if 'lap_count' in data else None
    asyncio.create_task(eng.start_route_loop(
        waypoints,
        mode=data.get('mode', 'walking'),
        speed_kmh=float(data['speed_kmh']) if 'speed_kmh' in data else None,
        lap_count=lap_count,
    ))
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

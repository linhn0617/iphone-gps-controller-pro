from aiohttp import web
from backend.services import bookmark_service


async def route_list(request: web.Request) -> web.Response:
    data = await bookmark_service.list_bookmarks()
    return web.json_response(data)


async def route_add(request: web.Request) -> web.Response:
    try:
        body = await request.json()
        name = body["name"]
        lat  = float(body["lat"])
        lng  = float(body.get("lng") or body.get("lon"))
    except Exception as e:
        return web.json_response({"ok": False, "error": str(e)}, status=400)
    entry = await bookmark_service.add_bookmark(name, lat, lng)
    return web.json_response({"ok": True, "bookmark": entry})


async def route_delete(request: web.Request) -> web.Response:
    try:
        bk_id = int(request.match_info["id"])
    except (ValueError, KeyError):
        return web.json_response({"ok": False, "error": "invalid id"}, status=400)
    ok = await bookmark_service.delete_bookmark(bk_id)
    return web.json_response({"ok": ok})


async def route_rename(request: web.Request) -> web.Response:
    try:
        bk_id = int(request.match_info["id"])
    except (ValueError, KeyError):
        return web.json_response({"ok": False, "error": "invalid id"}, status=400)
    try:
        body = await request.json()
        name = body["name"]
    except Exception as e:
        return web.json_response({"ok": False, "error": str(e)}, status=400)
    ok = await bookmark_service.rename_bookmark(bk_id, name)
    return web.json_response({"ok": ok})


async def route_migrate(request: web.Request) -> web.Response:
    try:
        body = await request.json()
        bookmarks = body if isinstance(body, list) else body.get("bookmarks", [])
    except Exception as e:
        return web.json_response({"ok": False, "error": str(e)}, status=400)
    added = await bookmark_service.migrate_from_client(bookmarks)
    return web.json_response({"ok": True, "added": added})


async def route_goldditto_start(request: web.Request) -> web.Response:
    idx = int(request.match_info.get('idx', -1))
    devices = request.app['device_manager'].devices
    udids = list(devices.keys())
    if idx < 0 or idx >= len(udids):
        return web.json_response({'ok': False, 'error': 'device not found'}, status=404)
    udid = udids[idx]
    ctx = devices[udid]
    if not ctx.state['connected']:
        return web.json_response({'ok': False, 'error': 'GPS not connected'}, status=503)
    state = request.app.get("_app_state")
    eng = state.engines.get(udid) if state else None
    if not eng:
        return web.json_response({'ok': False, 'error': 'engine not ready'}, status=503)
    try:
        body = await request.json()
        center_lat = float(body['center_lat'])
        center_lng = float(body['center_lng'])
    except Exception as e:
        return web.json_response({'ok': False, 'error': str(e)}, status=400)

    dwell = float(body.get('dwell_sec', 2.0))
    repeat = int(body.get('repeat', 1))

    from backend.core.goldditto import GoldDittoCycle
    import asyncio
    asyncio.create_task(GoldDittoCycle(eng).run(center_lat, center_lng, dwell_sec=dwell, repeat=repeat))
    return web.json_response({'ok': True})

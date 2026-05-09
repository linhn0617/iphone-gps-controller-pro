import asyncio
import json
import logging
from typing import Any

from aiohttp import web, WSMsgType

_log = logging.getLogger(__name__)
_connections: list[web.WebSocketResponse] = []


async def broadcast(event_type: str, data: Any) -> None:
    """Push a JSON event to every connected WebSocket client."""
    if not _connections:
        return
    msg = json.dumps({"type": event_type, "data": data})
    dead = []
    for ws in _connections:
        try:
            await ws.send_str(msg)
        except Exception:
            dead.append(ws)
    for ws in dead:
        if ws in _connections:
            _connections.remove(ws)


async def route_ws_status(request: web.Request) -> web.WebSocketResponse:
    ws = web.WebSocketResponse(heartbeat=30)
    await ws.prepare(request)
    _connections.append(ws)
    _log.info("WS client connected  total=%d", len(_connections))
    try:
        async for msg in ws:
            if msg.type == WSMsgType.TEXT:
                await _handle_ws_message(request, msg.data)
            elif msg.type in (WSMsgType.ERROR, WSMsgType.CLOSE):
                break
    finally:
        if ws in _connections:
            _connections.remove(ws)
        _log.info("WS client disconnected  total=%d", len(_connections))
    return ws


async def _handle_ws_message(request: web.Request, raw: str) -> None:
    try:
        msg = json.loads(raw)
    except Exception:
        return
    msg_type = msg.get("type")
    data = msg.get("data", {})

    app = request.app
    if not hasattr(app, "_app_state"):
        return
    state = app["_app_state"]

    if msg_type == "joystick_input":
        udid = data.get("udid") or state.primary_udid
        if udid and udid in state.engines:
            eng = state.engines[udid]
            if hasattr(eng, "joystick_handler") and eng.joystick_handler:
                await eng.joystick_handler.update_input(data)

    elif msg_type == "joystick_stop":
        udid = data.get("udid") or state.primary_udid
        if udid and udid in state.engines:
            eng = state.engines[udid]
            if hasattr(eng, "joystick_handler") and eng.joystick_handler:
                await eng.joystick_handler.stop()

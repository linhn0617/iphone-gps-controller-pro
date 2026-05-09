import asyncio, inspect, json, logging, re, sys, time
from typing import Callable, Awaitable

from backend.config import (
    SCAN_SEC, TUNNEL_TIMEOUT, TUNNEL_RETRIES, TUNNEL_RETRY_SEC, DEVICE_BOOT_WAIT,
)

log = logging.getLogger("device_manager")

# Callback invoked when a device is fully connected (tunnel up).
# Signature: async (ctx: DeviceCtx) -> None
_on_device_ready: Callable[["DeviceCtx"], Awaitable[None]] | None = None


def register_device_ready_callback(fn: Callable[["DeviceCtx"], Awaitable[None]]) -> None:
    global _on_device_ready
    _on_device_ready = fn


def get_devices() -> dict[str, "DeviceCtx"]:
    return _devices

_ANSI = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')

def strip_ansi(s: str) -> str:
    return _ANSI.sub('', s)


# ── Command types ─────────────────────────────────────────────────────
class _SetCmd:
    __slots__ = ('lat', 'lon')
    def __init__(self, lat, lon): self.lat = lat; self.lon = lon

class _ClearCmd: pass


# ── Single-slot mailbox for latest command ────────────────────────────
class _Mailbox:
    def __init__(self):
        self._cmd   = None
        self._event = asyncio.Event()

    def post(self, cmd):
        self._cmd = cmd
        self._event.set()

    async def wait(self):
        await self._event.wait()
        self._event.clear()
        cmd, self._cmd = self._cmd, None
        return cmd


# ── Per-device context ────────────────────────────────────────────────
class DeviceCtx:
    def __init__(self, idx, udid, name, ios):
        self.idx         = idx
        self.udid        = udid
        self.name        = name
        self.ios         = ios
        self.rsd_host    = None
        self.rsd_port    = None
        self.tunnel_proc = None
        self._mailbox    = _Mailbox()
        self._start_t    = time.time()
        self.state = {
            'connected': False, 'simulating': False,
            'last_lat': None,   'last_lon': None,
            'set_count': 0,     'error': None,
        }

    def to_dict(self):
        return {
            'idx': self.idx, 'udid': self.udid,
            'name': self.name, 'ios': self.ios,
            **self.state,
            'uptime_sec': int(time.time() - self._start_t),
            'tunnel_ok':  self.rsd_host is not None,
        }


# ── Global device registry ────────────────────────────────────────────
_devices: dict[str, DeviceCtx] = {}


# ── USB device scan (3 fallback methods) ─────────────────────────────
async def scan_usb_devices() -> list[dict]:
    try:
        from pymobiledevice3.usbmux import list_devices
        raw = list_devices()
        if inspect.isawaitable(raw):
            raw = await raw
        result = []
        for d in raw:
            udid = getattr(d, 'serial', None) or getattr(d, 'udid', None) or str(d)
            name, ios = f'iPhone ({udid[-4:]})', '?'
            try:
                from pymobiledevice3.lockdown import create_using_usbmux
                ld = create_using_usbmux(serial=udid)
                if inspect.isawaitable(ld): ld = await ld
                vals = ld.all_values
                name = vals.get('DeviceName', name)
                ios  = vals.get('ProductVersion', '?')
            except Exception:
                pass
            result.append({'udid': udid, 'name': name, 'ios': ios})
        if result: return result
    except Exception as e:
        log.debug(f'API scan: {e}')

    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable, '-m', 'pymobiledevice3', 'usbmux', 'list',
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
        )
        out, _ = await asyncio.wait_for(proc.communicate(), timeout=10)
        text = strip_ansi(out.decode()).strip()
        if text:
            data = json.loads(text)
            if isinstance(data, dict): data = [data]
            result = []
            for d in data:
                udid = d.get('SerialNumber') or d.get('udid', '')
                if udid:
                    result.append({
                        'udid': udid,
                        'name': d.get('DeviceName', f'iPhone ({udid[-4:]})'),
                        'ios':  d.get('ProductVersion', '?'),
                    })
            if result: return result
    except Exception as e:
        log.debug(f'CLI scan: {e}')

    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable, '-m', 'pymobiledevice3', 'usbmux', 'list',
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
        )
        out, _ = await asyncio.wait_for(proc.communicate(), timeout=10)
        udids = re.findall(r'[0-9a-f]{40}', out.decode(), re.I)
        if udids:
            return [{'udid': u, 'name': f'iPhone ({u[-4:]})', 'ios': '?'} for u in udids]
    except Exception as e:
        log.debug(f'Regex scan: {e}')

    return []


# ── Tunnel lifecycle ───────────────────────────────────────────────────
async def terminate_tunnel(ctx: DeviceCtx):
    proc = ctx.tunnel_proc
    if proc is None or proc.returncode is not None:
        ctx.tunnel_proc = None
        return
    try:
        proc.terminate()
        await asyncio.wait_for(proc.wait(), timeout=4.0)
    except asyncio.TimeoutError:
        try:
            proc.kill()
        except (ProcessLookupError, OSError):
            pass
        try:
            await asyncio.wait_for(proc.wait(), timeout=2.0)
        except asyncio.TimeoutError:
            pass
    except (ProcessLookupError, OSError):
        pass
    ctx.tunnel_proc = None


async def _try_start_tunnel(ctx: DeviceCtx) -> bool:
    try:
        proc = await asyncio.create_subprocess_exec(
            'sudo', sys.executable, '-m', 'pymobiledevice3',
            'remote', 'start-tunnel', '--udid', ctx.udid,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
    except Exception as e:
        log.error(f'[{ctx.name}] Failed to start tunnel process: {e}')
        return False

    ctx.tunnel_proc = proc
    rsd_host = rsd_port = None
    deadline = asyncio.get_event_loop().time() + TUNNEL_TIMEOUT

    while asyncio.get_event_loop().time() < deadline:
        try:
            raw = await asyncio.wait_for(proc.stdout.readline(), timeout=3.0)
        except asyncio.TimeoutError:
            if proc.returncode is not None:
                log.warning(f'[{ctx.name}] Tunnel process exited early (rc={proc.returncode})')
                break
            continue
        if not raw:
            break

        line = strip_ansi(raw.decode(errors='replace')).strip()
        log.debug(f'[tunnel/{ctx.name}] {line}')

        m = re.search(r'RSD\s*Address\s*[:\s]\s*([0-9a-f][0-9a-f:]+)', line, re.I)
        if m: rsd_host = m.group(1).strip().rstrip(':')
        m = re.search(r'RSD\s*Port\s*[:\s]\s*(\d+)', line, re.I)
        if m: rsd_port = int(m.group(1))

        if rsd_host and rsd_port:
            ctx.rsd_host = rsd_host
            ctx.rsd_port = rsd_port
            log.info(f'[{ctx.name}] Tunnel OK  {rsd_host}:{rsd_port}')
            asyncio.create_task(_drain(proc.stdout))
            return True

    try:
        proc.kill()
    except (ProcessLookupError, OSError):
        pass
    ctx.tunnel_proc = None
    return False


async def start_tunnel_with_retry(ctx: DeviceCtx) -> bool:
    for attempt in range(1, TUNNEL_RETRIES + 1):
        suffix = '' if attempt == 1 else f' (attempt {attempt})'
        log.info(f'[{ctx.name}] Starting tunnel...{suffix}')
        ok = await _try_start_tunnel(ctx)
        if ok: return True
        if attempt < TUNNEL_RETRIES:
            log.warning(f'[{ctx.name}] Tunnel failed, retrying in {TUNNEL_RETRY_SEC}s...')
            await terminate_tunnel(ctx)
            await asyncio.sleep(TUNNEL_RETRY_SEC)
    log.error(f'[{ctx.name}] Tunnel failed after {TUNNEL_RETRIES} attempts')
    return False


async def _drain(stream):
    try:
        async for _ in stream: pass
    except Exception:
        pass


# ── GPS worker ────────────────────────────────────────────────────────
async def gps_worker(ctx: DeviceCtx):
    from pymobiledevice3.remote.remote_service_discovery import RemoteServiceDiscoveryService
    from pymobiledevice3.services.dvt.instruments.dvt_provider import DvtProvider
    from pymobiledevice3.services.dvt.instruments.location_simulation import LocationSimulation

    last_target = None

    while True:
        if not ctx.rsd_host:
            await asyncio.sleep(2)
            continue
        try:
            log.info(f'[{ctx.name}] Connecting GPS...')
            async with RemoteServiceDiscoveryService((ctx.rsd_host, ctx.rsd_port)) as rsd:
                async with DvtProvider(rsd) as dvt:
                    async with LocationSimulation(dvt) as loc:
                        ctx.state['connected'] = True
                        ctx.state['error']     = None
                        log.info(f'[{ctx.name}] GPS connected')

                        if last_target:
                            await loc.set(last_target.lat, last_target.lon)
                            log.info(f'[{ctx.name}] Restored last position')

                        while True:
                            cmd = await ctx._mailbox.wait()
                            if isinstance(cmd, _ClearCmd):
                                await loc.clear()
                                last_target = None
                                ctx.state.update(simulating=False, last_lat=None, last_lon=None)
                                log.info(f'[{ctx.name}] GPS cleared')
                            elif isinstance(cmd, _SetCmd):
                                await loc.set(cmd.lat, cmd.lon)
                                last_target = cmd
                                ctx.state['simulating'] = True
                                ctx.state['last_lat']   = cmd.lat
                                ctx.state['last_lon']   = cmd.lon
                                ctx.state['set_count'] += 1
                                log.debug(f'[{ctx.name}] {cmd.lat:.5f},{cmd.lon:.5f}')
        except Exception as e:
            ctx.state['connected']  = False
            ctx.state['simulating'] = False
            ctx.state['error']      = str(e)
            log.error(f'[{ctx.name}] GPS disconnected: {e}, retrying in 5s...')
            await asyncio.sleep(5)


# ── Device scanner ────────────────────────────────────────────────────
async def device_scanner():
    idx_counter = 0
    while True:
        found       = await scan_usb_devices()
        found_udids = {d['udid'] for d in found}

        for udid in list(_devices.keys()):
            if udid not in found_udids:
                ctx = _devices.pop(udid)
                log.info(f'Device removed: {ctx.name}')
                asyncio.create_task(terminate_tunnel(ctx))

        for info in found:
            udid = info['udid']
            if udid not in _devices:
                ctx = DeviceCtx(idx_counter, udid, info['name'], info['ios'])
                idx_counter += 1
                _devices[udid] = ctx
                log.info(f'Device found: {ctx.name}  ({udid[-8:]})')
                asyncio.create_task(setup_device(ctx))

        await asyncio.sleep(SCAN_SEC)


async def setup_device(ctx: DeviceCtx):
    await asyncio.sleep(DEVICE_BOOT_WAIT)
    ok = await start_tunnel_with_retry(ctx)
    if ok:
        asyncio.create_task(gps_worker(ctx))
        if _on_device_ready:
            await _on_device_ready(ctx)
    else:
        ctx.state['error'] = 'Tunnel failed'

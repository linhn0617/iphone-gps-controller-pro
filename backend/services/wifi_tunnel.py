"""WiFi tunnel support for pymobiledevice3.

After a device is paired over USB, pymobiledevice3 saves the pairing record
to ~/.pymobiledevice3/. On macOS we can attempt a WiFi (remote) tunnel using
the same pair record. This is best-effort — if it fails the caller falls back
to USB.
"""
from __future__ import annotations

import asyncio
import logging
import sys

_log = logging.getLogger(__name__)


async def start_wifi_tunnel(udid: str) -> tuple[str, int] | None:
    """Try to start a WiFi tunnel for the given UDID.

    Returns (rsd_host, rsd_port) on success, None on failure.
    """
    try:
        proc = await asyncio.create_subprocess_exec(
            'sudo', sys.executable, '-m', 'pymobiledevice3',
            'remote', 'start-tunnel', '--udid', udid, '--wifi',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
    except Exception as exc:
        _log.warning("WiFi tunnel process failed to start: %s", exc)
        return None

    import re
    from backend.core.device_manager import strip_ansi, TUNNEL_TIMEOUT

    deadline = asyncio.get_running_loop().time() + TUNNEL_TIMEOUT
    rsd_host = rsd_port = None

    while asyncio.get_running_loop().time() < deadline:
        try:
            raw = await asyncio.wait_for(proc.stdout.readline(), timeout=3.0)
        except asyncio.TimeoutError:
            if proc.returncode is not None:
                break
            continue
        if not raw:
            break
        line = strip_ansi(raw.decode(errors='replace')).strip()
        m = re.search(r'RSD\s*Address\s*[:\s]\s*([0-9a-f][0-9a-f:]+)', line, re.I)
        if m:
            rsd_host = m.group(1).strip().rstrip(':')
        m = re.search(r'RSD\s*Port\s*[:\s]\s*(\d+)', line, re.I)
        if m:
            rsd_port = int(m.group(1))
        if rsd_host and rsd_port:
            _log.info("WiFi tunnel OK  %s:%s", rsd_host, rsd_port)
            return rsd_host, rsd_port

    try:
        proc.kill()
    except Exception:
        pass
    return None

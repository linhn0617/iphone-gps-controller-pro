[English](README.md) | [繁體中文](README.zh-TW.md)

# 📍 iPhone GPS Controller Pro

A full-featured macOS tool for real-time iPhone GPS location simulation via USB/WiFi.  
Ported from [LocWarp](https://github.com/keezxc1223/locwarp)'s complete feature set into a lightweight **aiohttp + Vanilla JS** stack — no Electron, no React, just `./start.sh`.

> **Author:** Aroha Lin · **License:** MIT · **Copyright (c) 2026 Aroha Lin**  
> **Repo:** https://github.com/ArohaLin/iphone-gps-controller-pro

---

## Table of Contents

1. [Features](#features)
2. [Requirements](#requirements)
3. [Installation & Quick Start](#installation--quick-start)
4. [Architecture](#architecture)
5. [Mode Reference](#mode-reference)
6. [HTTP API Reference](#http-api-reference)
7. [WebSocket Events](#websocket-events)
8. [Keyboard Shortcuts](#keyboard-shortcuts)
9. [Troubleshooting](#troubleshooting)
10. [Third-Party Licenses](#third-party-licenses)

---

## Features

### Core

| Feature | Description |
|---------|-------------|
| 📍 Click-to-teleport | Click map or enter coordinates to instantly push GPS to iPhone |
| 🧭 Directional Move | 8-direction pad with configurable step distance |
| 🔄 Auto-Reconnect | Exponential back-off retry on tunnel/GPS disconnect |
| 📱 Multi-Device | Manage multiple iPhones; leader 👑 badge + follower sync |
| 🌐 WebSocket push | Real-time position/state updates — no polling lag |
| 📲 iOS 16 & 17+ | DVT (iOS 17+) and DtSimulateLocation (iOS 16) dual path |

### Movement Modes

| Mode | Description |
|------|-------------|
| 🗺 Navigate | Real road routing via OSRM — click right-click → "Navigate here" |
| 🛳 Cruise | Multi-waypoint route (frontend interpolation, legacy) |
| 🕹 Joystick | WASD / arrow-key continuous movement at 5 Hz |
| 🚶 Random Walk | Seed-based area-uniform random walk within a radius |
| 📌 Multi-Stop | Leg-by-leg OSRM routing between N waypoints, with dwell + loop |
| 🔁 Route Loop | Closed-loop route with configurable lap count |

### Advanced

| Feature | Description |
|---------|-------------|
| ⏱ Pokemon Cooldown | Distance-based soft-ban timer (LocWarp-compatible table) |
| 👑 Leadership Handoff | Primary device disconnect → snapshot → resume on next device |
| 📶 WiFi Tunnel | Switch from USB to WiFi tunnel after initial USB pairing |
| 🎮 GoldDitto Cycle | S2-boundary teleport sequence to trigger Ditto encounters |
| 🗺 S2 Grid Overlay | L14 (yellow) / L17 (red) cell boundaries drawn on map |
| ⭐ Cloud Bookmarks | Backend-persisted favorites (JSON file), survives incognito |
| 📤 GPX Export | Export waypoint routes as standard `.gpx` files |
| 🔍 Place Search | Global geocoding via Nominatim |

---

## Requirements

| Item | Requirement |
|------|-------------|
| **OS** | macOS (requires `sudo` for USB tunnel / utun interface) |
| **Python** | 3.11 or higher |
| **iPhone iOS** | iOS 16 or higher |
| **Developer Mode** | **Must be enabled** on iPhone (Settings → Privacy & Security → Developer Mode) |
| **Connection** | USB (Lightning or USB-C); WiFi after initial pairing |
| **Browser** | Chrome / Firefox / Safari |
| **Network** | Backend is local-only; OSRM routing and geocoding require internet |

---

## Installation & Quick Start

### 1. Trust the iPhone & Enable Developer Mode

Connect iPhone via USB, tap **Trust This Computer**, then enable Developer Mode:

```bash
# Option A — command line (iPhone must be unlocked and trusted)
python3 -m pymobiledevice3 amfi enable-developer-mode

# Option B — manual
# iPhone: Settings → Privacy & Security → Developer Mode → Enable → Restart
```

### 2. Clone & Start

```bash
git clone https://github.com/ArohaLin/iphone-gps-controller-pro.git
cd iphone-gps-controller-pro
./start.sh          # creates venv, installs deps, starts backend, opens browser
```

The script auto-creates a Python venv and installs all dependencies on first run. macOS will prompt for `sudo` (required for the USB tunnel utun interface).

### 3. Set a GPS Location

1. Confirm the iPhone shows a **green dot (Connected)** in the device list
2. Click anywhere on the map → iPhone GPS updates within ~1 second
3. Right-click the map for more options: Navigate, Add Waypoint

### Stop

```bash
./stop.sh           # kills the process on port 8090
# or Ctrl+C in the terminal where ./start.sh is running
```

Custom port:

```bash
./start.sh 9000
./stop.sh  9000
```

---

## Architecture

```
iphone-gps-controller-pro/
├── backend/
│   ├── main.py                    # aiohttp app entry, AppState, route registration
│   ├── config.py                  # constants, speed profiles, cooldown table
│   ├── core/
│   │   ├── device_manager.py      # USB scan (3-tier fallback), tunnel lifecycle
│   │   ├── simulation_engine.py   # central FSM, tick-budgeted _move_along_route
│   │   ├── navigator.py           # single-destination OSRM route
│   │   ├── joystick.py            # 5 Hz tick handler (WASD WebSocket input)
│   │   ├── random_walk.py         # seed-based, area-uniform, conn-error backoff
│   │   ├── multi_stop.py          # leg-by-leg routing, jump mode, loop
│   │   ├── route_loop.py          # closed loop, per-lap OSRM re-fetch, lap_count
│   │   └── goldditto.py           # Pokemon GO S2-boundary teleport cycle
│   ├── api/
│   │   ├── location.py            # REST endpoints for all movement modes
│   │   ├── device.py              # WiFi tunnel toggle
│   │   ├── bookmark.py            # bookmark CRUD + localStorage migration
│   │   └── websocket.py           # /ws/status WebSocket broadcast
│   ├── services/
│   │   ├── interpolator.py        # haversine, move_point, add_jitter, random_point_in_radius
│   │   ├── route_service.py       # OSRM client + straight-line fallback
│   │   ├── cooldown.py            # Pokemon-style distance-based cooldown timer
│   │   ├── bookmark_service.py    # JSON persistence with asyncio lock
│   │   └── wifi_tunnel.py         # WiFi tunnel helper
│   └── models/
│       └── schemas.py             # @dataclass Coordinate/SimulationStatus, Enum State/Mode
├── frontend/
│   ├── index.html                 # single-page app, all JS inline
│   └── css/base.css               # extracted palette + component styles
├── start.sh                       # one-click start
├── stop.sh                        # kill port process
└── requirements.txt
```

### How it works

```
./start.sh
 └─ backend/main.py (aiohttp)
      ├─ AppState  ──── engines: {udid → SimulationEngine}
      │                 cooldown: CooldownTimer
      │                 leadership handoff on USB disconnect
      │
      ├─ device_scanner  (every 6 s)
      │    ├─ new device → setup_device → tunnel → gps_worker → SimulationEngine
      │    └─ removed    → snapshot → promote next engine → resume_from_snapshot
      │
      ├─ SimulationEngine (per device)
      │    ├─ teleport / navigate / start_joystick / start_random_walk / …
      │    └─ _move_along_route  ← tick-budgeted (anchors tick_start before push)
      │
      └─ /ws/status  ← WebSocket broadcast (position_update, state_change, …)

Browser (frontend/index.html)
 ├─ WebSocket client  → position_update → marker update (no polling lag)
 ├─ 6 s poll          → /api/devices    → device list sync only
 └─ Right-click menu  → /api/device/{idx}/navigate, /joystick/start, …
```

---

## Mode Reference

### 📍 Normal Mode

- **Click map** → teleport GPS instantly  
- **Manual input** → enter Lat/Lon in sidebar → Go  
- **D-Pad** → 8-direction movement, configurable step (meters)  
- **Right-click** → context menu: Set GPS / Navigate here / Add waypoint  
- **Speed selector** → Walking / Running / Driving (used for Navigate)  
- **Clear GPS** → remove simulated location; iPhone reverts to real GPS  

---

### 🗺 Navigate (right-click menu)

1. Right-click any map location → **Navigate here**
2. Backend fetches real road route from OSRM public demo API
3. iPhone walks along the road; map draws dashed polyline
4. Navigation complete → toast notification + line removed

Force straight-line fallback: available via API `force_straight: true`

---

### 🛳 Cruise Mode

Legacy frontend-interpolated mode.  
Add waypoints by clicking map in Cruise tab → Play / Stop / Loop / Export GPX.  
For production use, prefer **Multi-Stop** (backend OSRM routing).

---

### 🕹 Joystick Mode

1. First teleport to a starting position (Normal mode click)
2. Switch to **Joystick** tab → select mode → **Start Joystick**
3. Hold **WASD** or **arrow keys** to move continuously at 5 Hz
4. Release key → movement stops; WS `joystick_stop` sent

Input also accepted via WebSocket message:
```json
{ "type": "joystick_input", "data": { "direction": 0, "intensity": 1.0 } }
{ "type": "joystick_stop",  "data": {} }
```

---

### 🚶 Random Walk Mode

1. Click **Use current position** to set center
2. Set radius (meters) and optional seed
3. **Start Walk** → iPhone wanders within the radius using real roads

Seed-based: two devices with the same seed follow identical paths.  
Handles connection errors with exponential back-off (up to 60 retries).

---

### 📌 Multi-Stop Mode

Uses waypoints added in **Cruise tab**.

| Option | Description |
|--------|-------------|
| Dwell seconds | Time to pause at each stop (0 = random 1–3 s) |
| Mode | Walking / Running / Driving |
| Jump mode | Teleport to each stop instead of walking |
| Loop | Repeat route indefinitely |

WS events: `stop_reached`, `multi_stop_complete`, `lap_complete`

---

### 🔁 Route Loop Mode

Uses waypoints from **Cruise tab**. Last point auto-connects back to first.

| Option | Description |
|--------|-------------|
| Laps | 0 = infinite; >0 = stop after N laps |
| Mode | Walking / Running / Driving |

Each lap re-fetches OSRM routes. WS: `lap_complete`, `loop_complete`

---

### ⏱ Pokemon Cooldown

Triggered automatically on teleport. Distance-based table (km → seconds):

| Distance | Cooldown |
|----------|----------|
| ≤ 1 km   | 0 s      |
| ≤ 5 km   | 30 s     |
| ≤ 10 km  | 2 min    |
| ≤ 25 km  | 5 min    |
| ≤ 100 km | 15 min   |
| ≤ 250 km | 25 min   |
| ≤ 500 km | 45 min   |
| ≤ 750 km | 1 hr     |
| ≤ 1000 km| 1.5 hr   |
| > 1000 km| 2 hr     |

While active: teleport requests return HTTP 429, and a live countdown banner appears on the map.

---

### 🎮 Pokemon GO Suite (Pogo tab)

**GoldDitto Cycle**

Teleports to 10 points around the center that cross S2 L17 cell boundaries, triggering Ditto encounter logic. Configure dwell seconds and repeat count.

**S2 Grid Overlay**

| Level | Color | Visible at zoom |
|-------|-------|-----------------|
| L17   | Red   | ≥ 15            |
| L14   | Yellow| ≥ 13            |

---

### 👑 Leadership Handoff (multi-device)

When the primary device disconnects:
1. Current simulation state is captured (position, route segment, seed counter)
2. The next connected device is promoted to primary (👑 badge)
3. New primary resumes from the snapshot position and continues the route

New devices joining automatically sync to the leader's current position.

---

## HTTP API Reference

Base URL: `http://127.0.0.1:8090` (CORS fully open)

### Device

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/devices` | List all detected devices |
| GET | `/api/device/{idx}/status` | Single device status |
| POST | `/api/device/{idx}/set` | Teleport GPS (`{lat, lon}`) |
| POST | `/api/device/{idx}/clear` | Clear GPS simulation |
| POST | `/api/device/{idx}/wifi-tunnel` | Switch to WiFi tunnel |

### Movement

| Method | Path | Body |
|--------|------|------|
| POST | `/api/device/{idx}/navigate` | `{lat, lng, mode, speed_kmh?}` |
| POST | `/api/device/{idx}/stop` | — |
| POST | `/api/device/{idx}/joystick/start` | `{mode}` |
| POST | `/api/device/{idx}/random-walk/start` | `{center_lat, center_lng, radius_m, mode, seed?}` |
| POST | `/api/device/{idx}/multi-stop/start` | `{waypoints, mode, stop_duration, loop, jump_mode}` |
| POST | `/api/device/{idx}/route-loop/start` | `{waypoints, mode, lap_count?}` |
| POST | `/api/device/{idx}/goldditto/start` | `{center_lat, center_lng, dwell_sec, repeat}` |

### Bookmarks

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/bookmarks` | List all bookmarks |
| POST | `/api/bookmarks` | Add bookmark (`{name, lat, lng}`) |
| DELETE | `/api/bookmarks/{id}` | Delete bookmark |
| POST | `/api/bookmarks/{id}/rename` | Rename (`{name}`) |
| POST | `/api/bookmarks/migrate` | Migrate from localStorage (`[{name,lat,lng}]`) |

### Other

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/cooldown` | Cooldown status |
| GET | `/ws/status` | WebSocket (upgrade) |

---

## WebSocket Events

Connect to `ws://localhost:8090/ws/status`. All messages are JSON:

```json
{ "type": "<event>", "data": { ... } }
```

| Event | Data fields | Description |
|-------|-------------|-------------|
| `position_update` | `udid, state, position{lat,lng}` | Emitted every GPS tick |
| `state_change` | `udid, state` | Mode FSM transition |
| `device_connected` | `udid, name, ios, is_primary` | New device ready |
| `device_disconnected` | `udid` | Device removed |
| `leadership_change` | `udid` | New primary elected |
| `route_path` | `udid, coords[[lat,lng],…]` | Draw road polyline |
| `navigation_complete` | `udid, lat, lng` | Navigate finished |
| `stop_reached` | `udid, stop_idx, lat, lng` | Multi-stop waypoint arrived |
| `lap_complete` | `udid, lap` | Loop lap finished |
| `loop_complete` | `udid, laps` | All laps done |
| `multi_stop_complete` | `udid` | Route finished |
| `goldditto_complete` | `udid` | Ditto cycle finished |
| `cooldown_active` | `active, remaining_sec, total_sec, distance_km` | Cooldown started |
| `cooldown_ended` | — | Cooldown expired |

---

## Keyboard Shortcuts

> Disabled when an input field is focused.  
> In **Joystick mode**, WASD and arrow keys send `joystick_input` instead.

| Key | Action |
|-----|--------|
| `↑` / `W` | Move North |
| `↓` / `S` | Move South |
| `←` / `A` | Move West |
| `→` / `D` | Move East |
| `Q` | Move Northwest |
| `E` | Move Northeast |
| `Z` | Move Southwest |
| `C` | Move Southeast |
| `+` / `=` | Zoom in |
| `-` | Zoom out |
| `F` | Re-center map |

---

## Troubleshooting

**Q1: No devices detected after startup?**
- Make sure iPhone is unlocked and has tapped **Trust This Computer**
- Try unplugging and re-plugging the USB cable
- Run `python3 -m pymobiledevice3 usbmux list` to verify detection

**Q2: Tunnel keeps failing?**
- Confirm Developer Mode is enabled on iPhone (Settings → Privacy & Security → Developer Mode)
- Ensure Xcode Command Line Tools are up to date: `xcode-select --install`
- Try restarting the iPhone before reconnecting

**Q3: GPS set but iPhone location doesn't change?**
- Confirm the device card shows a **green dot (Connected)**
- Confirm the device state is not `disconnected` or `reconnecting`
- Some apps need to be relaunched to pick up the new location

**Q4: Backend not reachable / "Launcher not running"?**
- Ensure `./start.sh` is running — check the terminal for the port number
- If the port changed, restart with `./stop.sh && ./start.sh`
- Browser console → Network tab: check if requests to `localhost:8090` succeed

**Q5: Cooldown banner won't go away?**
- The banner reflects actual cooldown remaining — wait for it to expire
- Or restart the backend (`./stop.sh && ./start.sh`) to reset the cooldown state

**Q6: OSRM navigate takes a long time / fallback to straight line?**
- The public OSRM demo server (`router.project-osrm.org`) may be rate-limited
- Fallback behavior: iPhone walks in a straight line between points
- Consider self-hosting OSRM and updating `OSRM_BASE_URL` in `backend/config.py`

**Q7: S2 grid not showing?**
- Zoom in to level ≥ 15 for L17, ≥ 13 for L14
- Ensure the CDN for `s2-geometry` loaded (check browser console)

---

## Third-Party Licenses

| Package | License |
|---------|---------|
| [Leaflet.js](https://leafletjs.com/) | BSD 2-Clause |
| [OpenStreetMap / Nominatim](https://www.openstreetmap.org/) | ODbL |
| [Open-Meteo API](https://open-meteo.com/) | CC BY 4.0 |
| [OSRM](https://project-osrm.org/) | BSD 2-Clause |
| [s2-geometry](https://github.com/nicktacular/node-s2) | Apache 2.0 |
| [pymobiledevice3](https://github.com/doronz88/pymobiledevice3) | GPL-3.0 |
| [aiohttp](https://docs.aiohttp.org/) | Apache 2.0 |
| [httpx](https://www.python-httpx.org/) | BSD 3-Clause |

---

*Copyright (c) 2026 Aroha Lin — MIT License*

import sys
from pathlib import Path

META_PORT        = int(sys.argv[1]) if len(sys.argv) > 1 else 8090
SCAN_SEC         = 6
TUNNEL_TIMEOUT   = 40
TUNNEL_RETRIES   = 3
TUNNEL_RETRY_SEC = 5
DEVICE_BOOT_WAIT = 8

DATA_DIR         = Path.home() / ".iphone-gps-controller-pro"
BOOKMARKS_FILE   = DATA_DIR / "bookmarks.json"
ROUTES_FILE      = DATA_DIR / "routes.json"
DEVICE_NAMES_FILE = DATA_DIR / "device_names.json"

OSRM_BASE_URL    = "https://router.project-osrm.org"
VALHALLA_BASE_URL = "https://valhalla1.openstreetmap.de"
BROUTER_BASE_URL = "https://brouter.de"
DEFAULT_ROUTE_ENGINE = "osrm"
ROUTE_ENGINES_ALLOWED = ("osrm", "valhalla", "brouter")

NOMINATIM_BASE_URL = "https://nominatim.openstreetmap.org"
NOMINATIM_USER_AGENT = "iphone-gps-controller-pro/1.0"

SPEED_PROFILES = {
    "walking": {"speed_mps": 3.0,  "jitter": 0.5, "update_interval": 1.0},
    "running": {"speed_mps": 5.5,  "jitter": 0.7, "update_interval": 0.5},
    "driving": {"speed_mps": 16.7, "jitter": 1.2, "update_interval": 0.5},
}

COOLDOWN_TABLE = [
    (1,           0),
    (5,           30),
    (10,          120),
    (25,          300),
    (100,         900),
    (250,         1500),
    (500,         2700),
    (750,         3600),
    (1000,        5400),
    (float("inf"), 7200),
]

DEFAULT_LOCATION = {"lat": 25.0330, "lng": 121.5654}

API_HOST = "127.0.0.1"
API_PORT = META_PORT

RECONNECT_BASE_DELAY = 2.0
RECONNECT_MAX_DELAY  = 60.0
RECONNECT_MAX_RETRIES = 30

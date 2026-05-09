from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class SimulationState(str, Enum):
    IDLE          = "idle"
    TELEPORTING   = "teleporting"
    NAVIGATING    = "navigating"
    LOOPING       = "looping"
    JOYSTICK      = "joystick"
    RANDOM_WALK   = "random_walk"
    MULTI_STOP    = "multi_stop"
    PAUSED        = "paused"
    RECONNECTING  = "reconnecting"
    DISCONNECTED  = "disconnected"


class MovementMode(str, Enum):
    WALKING = "walking"
    RUNNING = "running"
    DRIVING = "driving"


@dataclass
class Coordinate:
    lat: float
    lng: float

    def to_dict(self) -> dict[str, float]:
        return {"lat": self.lat, "lng": self.lng}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Coordinate":
        return cls(lat=float(d["lat"]), lng=float(d["lng"]))


@dataclass
class JoystickInput:
    direction: float   # degrees, 0=N, 90=E
    intensity: float   # 0.0–1.0
    udid: str = ""


@dataclass
class SimulationStatus:
    udid: str
    state: SimulationState
    position: Coordinate | None = None
    mode: MovementMode = MovementMode.WALKING
    speed_kmh: float | None = None
    destination: Coordinate | None = None
    is_primary: bool = False
    connected: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "udid": self.udid,
            "state": self.state.value,
            "position": self.position.to_dict() if self.position else None,
            "mode": self.mode.value,
            "speed_kmh": self.speed_kmh,
            "destination": self.destination.to_dict() if self.destination else None,
            "is_primary": self.is_primary,
            "connected": self.connected,
        }


@dataclass
class ResumableSnapshot:
    kind: str                                  # "navigate" | "multi_stop" | "random_walk" | "route_loop"
    args: dict[str, Any] = field(default_factory=dict)
    current_pos: tuple[float, float] | None = None
    segment_index: int = 0
    lap_count: int = 0
    user_waypoint_next: int = 0
    distance_traveled: float = 0.0
    speed_was_applied: bool = False
    random_walk_count: int = 0

import math
import random


class RouteInterpolator:

    EARTH_RADIUS_M = 6_371_000.0

    @staticmethod
    def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Return distance in metres between two lat/lon points."""
        R = RouteInterpolator.EARTH_RADIUS_M
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlam = math.radians(lon2 - lon1)
        a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
        return 2 * R * math.asin(math.sqrt(a))

    @staticmethod
    def bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Return initial bearing in degrees (0=N, 90=E)."""
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dlam = math.radians(lon2 - lon1)
        x = math.sin(dlam) * math.cos(phi2)
        y = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(dlam)
        return (math.degrees(math.atan2(x, y)) + 360) % 360

    @staticmethod
    def move_point(lat: float, lon: float, bearing_deg: float, distance_m: float) -> tuple[float, float]:
        """Move from (lat, lon) by distance_m in direction bearing_deg. Returns (lat, lon)."""
        R = RouteInterpolator.EARTH_RADIUS_M
        d = distance_m / R
        b = math.radians(bearing_deg)
        phi1 = math.radians(lat)
        lam1 = math.radians(lon)
        phi2 = math.asin(math.sin(phi1) * math.cos(d) + math.cos(phi1) * math.sin(d) * math.cos(b))
        lam2 = lam1 + math.atan2(
            math.sin(b) * math.sin(d) * math.cos(phi1),
            math.cos(d) - math.sin(phi1) * math.sin(phi2),
        )
        return math.degrees(phi2), math.degrees(lam2)

    @staticmethod
    def interpolate(lat1: float, lon1: float, lat2: float, lon2: float, step_m: float = 5.0) -> list[tuple[float, float]]:
        """Return list of (lat, lon) points densified every step_m metres."""
        total = RouteInterpolator.haversine(lat1, lon1, lat2, lon2)
        if total < step_m:
            return [(lat2, lon2)]
        b = RouteInterpolator.bearing(lat1, lon1, lat2, lon2)
        points = []
        dist = 0.0
        while dist < total:
            dist = min(dist + step_m, total)
            points.append(RouteInterpolator.move_point(lat1, lon1, b, dist))
        return points

    @staticmethod
    def add_jitter(lat: float, lon: float, max_m: float = 2.0) -> tuple[float, float]:
        """Add random positional noise up to max_m metres."""
        bearing = random.uniform(0, 360)
        distance = random.uniform(0, max_m)
        return RouteInterpolator.move_point(lat, lon, bearing, distance)

    @staticmethod
    def random_point_in_radius(
        center_lat: float,
        center_lon: float,
        radius_m: float,
        rng: random.Random | None = None,
    ) -> tuple[float, float]:
        """Return a uniformly-distributed random point within radius_m of center."""
        _rng = rng or random
        bearing = _rng.uniform(0, 360)
        # sqrt ensures area-uniform distribution
        distance = math.sqrt(_rng.random()) * radius_m
        return RouteInterpolator.move_point(center_lat, center_lon, bearing, distance)

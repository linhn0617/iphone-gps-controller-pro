from __future__ import annotations

import asyncio
import logging
from typing import Literal

import httpx

from backend.config import (
    OSRM_BASE_URL, DEFAULT_ROUTE_ENGINE, SPEED_PROFILES,
)
from backend.services.interpolator import RouteInterpolator

_log = logging.getLogger(__name__)

Profile = Literal["foot", "car", "bike"]


def _osrm_profile(mode: str) -> str:
    return {"walking": "foot", "running": "foot", "driving": "car"}.get(mode, "foot")


class RouteService:
    def __init__(self, engine: str = DEFAULT_ROUTE_ENGINE):
        self.engine = engine
        self._client = httpx.AsyncClient(timeout=10.0)

    async def get_route(
        self,
        lat1: float, lon1: float,
        lat2: float, lon2: float,
        *,
        mode: str = "walking",
        force_straight: bool = False,
    ) -> list[tuple[float, float]]:
        if force_straight or self.engine == "straight":
            return self._straight_fallback([(lat1, lon1), (lat2, lon2)])

        try:
            return await self._osrm_route(lat1, lon1, lat2, lon2, mode=mode)
        except Exception as exc:
            _log.warning("OSRM failed (%s), using straight-line fallback", exc)
            return self._straight_fallback([(lat1, lon1), (lat2, lon2)])

    async def get_multi_route(
        self,
        waypoints: list[tuple[float, float]],
        *,
        mode: str = "walking",
        force_straight: bool = False,
    ) -> list[tuple[float, float]]:
        if len(waypoints) < 2:
            return waypoints
        all_coords: list[tuple[float, float]] = []
        for i in range(len(waypoints) - 1):
            seg = await self.get_route(
                waypoints[i][0], waypoints[i][1],
                waypoints[i + 1][0], waypoints[i + 1][1],
                mode=mode, force_straight=force_straight,
            )
            if i > 0 and all_coords and seg and all_coords[-1] == seg[0]:
                seg = seg[1:]
            all_coords.extend(seg)
        return all_coords

    async def _osrm_route(
        self, lat1: float, lon1: float, lat2: float, lon2: float, *, mode: str
    ) -> list[tuple[float, float]]:
        profile = _osrm_profile(mode)
        # OSRM uses lon,lat order
        coords_str = f"{lon1},{lat1};{lon2},{lat2}"
        url = f"{OSRM_BASE_URL}/route/v1/{profile}/{coords_str}"
        params = {
            "overview": "full",
            "geometries": "geojson",
            "steps": "true",
        }
        resp = await self._client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != "Ok" or not data.get("routes"):
            raise ValueError(f"OSRM no route: {data.get('code')}")
        # GeoJSON coordinates are [lon, lat] — flip to (lat, lon)
        geo_coords = data["routes"][0]["geometry"]["coordinates"]
        return [(c[1], c[0]) for c in geo_coords]

    @staticmethod
    def _straight_fallback(
        waypoints: list[tuple[float, float]],
        step_m: float = 25.0,
    ) -> list[tuple[float, float]]:
        result: list[tuple[float, float]] = [waypoints[0]]
        for i in range(len(waypoints) - 1):
            pts = RouteInterpolator.interpolate(
                waypoints[i][0], waypoints[i][1],
                waypoints[i + 1][0], waypoints[i + 1][1],
                step_m=step_m,
            )
            result.extend(pts)
        return result

    async def close(self) -> None:
        await self._client.aclose()

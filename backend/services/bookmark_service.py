"""JSON-file bookmark persistence with file locking."""
from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any

from backend.config import BOOKMARKS_FILE, DATA_DIR


CATEGORY_KEYS = ("base", "bigmush-early", "bigmush-late", "event-mush", "flower", "goldbowl")
DEFAULT_CATEGORY = "base"


def _normalize_category(c: Any) -> str:
    return c if isinstance(c, str) and c in CATEGORY_KEYS else DEFAULT_CATEGORY


def _ensure_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _load_raw() -> list[dict]:
    try:
        return json.loads(BOOKMARKS_FILE.read_text(encoding='utf-8'))
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _save_raw(data: list[dict]) -> None:
    _ensure_dir()
    BOOKMARKS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


_lock = asyncio.Lock()


async def list_bookmarks() -> list[dict]:
    async with _lock:
        loop = asyncio.get_running_loop()
        data = await loop.run_in_executor(None, _load_raw)
    for b in data:
        b.setdefault("category", DEFAULT_CATEGORY)
    return data


async def add_bookmark(name: str, lat: float, lng: float, **extra: Any) -> dict:
    extra["category"] = _normalize_category(extra.get("category"))
    async with _lock:
        loop = asyncio.get_running_loop()
        data = await loop.run_in_executor(None, _load_raw)
        entry = {
            "id": int(time.time() * 1000),
            "name": name,
            "lat": lat,
            "lng": lng,
            "created_at": int(time.time()),
            **extra,
        }
        # Deduplicate by (lat, lng, name)
        for existing in data:
            if (abs(existing.get("lat", 0) - lat) < 1e-7
                    and abs(existing.get("lng", 0) - lng) < 1e-7
                    and existing.get("name") == name):
                return existing
        data.append(entry)
        await loop.run_in_executor(None, _save_raw, data)
        return entry


async def delete_bookmark(bookmark_id: int) -> bool:
    async with _lock:
        loop = asyncio.get_running_loop()
        data = await loop.run_in_executor(None, _load_raw)
        new_data = [b for b in data if b.get("id") != bookmark_id]
        if len(new_data) == len(data):
            return False
        await loop.run_in_executor(None, _save_raw, new_data)
        return True


async def rename_bookmark(bookmark_id: int, new_name: str) -> bool:
    async with _lock:
        loop = asyncio.get_running_loop()
        data = await loop.run_in_executor(None, _load_raw)
        for b in data:
            if b.get("id") == bookmark_id:
                b["name"] = new_name
                await loop.run_in_executor(None, _save_raw, data)
                return True
        return False


async def update_category(bookmark_id: int, category: str) -> bool:
    cat = _normalize_category(category)
    async with _lock:
        loop = asyncio.get_running_loop()
        data = await loop.run_in_executor(None, _load_raw)
        for b in data:
            if b.get("id") == bookmark_id:
                b["category"] = cat
                await loop.run_in_executor(None, _save_raw, data)
                return True
        return False


async def migrate_from_client(bookmarks: list[dict]) -> int:
    """Import bookmarks from localStorage dump. Returns count added."""
    added = 0
    for b in bookmarks:
        try:
            await add_bookmark(
                name=b.get("name", "Unnamed"),
                lat=float(b["lat"]),
                lng=float(b.get("lon") or b.get("lng")),
                category=b.get("category", DEFAULT_CATEGORY),
            )
            added += 1
        except Exception:
            pass
    return added

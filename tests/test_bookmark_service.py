import json

import pytest


@pytest.fixture
def tmp_data_dir(monkeypatch, tmp_path):
    from backend import config
    from backend.services import bookmark_service as bs

    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "BOOKMARKS_FILE", tmp_path / "bookmarks.json")
    monkeypatch.setattr(bs, "DATA_DIR", tmp_path)
    monkeypatch.setattr(bs, "BOOKMARKS_FILE", tmp_path / "bookmarks.json")
    return tmp_path


@pytest.mark.asyncio
async def test_add_with_category(tmp_data_dir):
    from backend.services import bookmark_service as bs

    entry = await bs.add_bookmark("Base 1", 25.0, 121.5, category="goldbowl")
    assert entry["category"] == "goldbowl"


@pytest.mark.asyncio
async def test_add_invalid_category_falls_back(tmp_data_dir):
    from backend.services import bookmark_service as bs

    entry = await bs.add_bookmark("X", 25.0, 121.5, category="bogus")
    assert entry["category"] == "base"


@pytest.mark.asyncio
async def test_add_without_category_defaults_to_base(tmp_data_dir):
    from backend.services import bookmark_service as bs

    entry = await bs.add_bookmark("Y", 25.0, 121.5)
    assert entry["category"] == "base"


@pytest.mark.asyncio
async def test_list_defaults_legacy_to_base(tmp_data_dir):
    (tmp_data_dir / "bookmarks.json").write_text(
        json.dumps(
            [{"id": 1, "name": "Old", "lat": 1.0, "lng": 2.0, "created_at": 0}]
        ),
        encoding="utf-8",
    )
    from backend.services import bookmark_service as bs

    rows = await bs.list_bookmarks()
    assert rows[0]["category"] == "base"


@pytest.mark.asyncio
async def test_migrate_passes_category(tmp_data_dir):
    from backend.services import bookmark_service as bs

    count = await bs.migrate_from_client(
        [{"name": "A", "lat": 1, "lng": 2, "category": "flower"}]
    )
    assert count == 1
    rows = await bs.list_bookmarks()
    assert rows[0]["category"] == "flower"


@pytest.mark.asyncio
async def test_update_category(tmp_data_dir):
    from backend.services import bookmark_service as bs

    entry = await bs.add_bookmark("X", 1.0, 2.0)
    ok = await bs.update_category(entry["id"], "event-mush")
    assert ok
    rows = await bs.list_bookmarks()
    assert rows[0]["category"] == "event-mush"


@pytest.mark.asyncio
async def test_update_category_invalid_id(tmp_data_dir):
    from backend.services import bookmark_service as bs

    ok = await bs.update_category(99999, "flower")
    assert ok is False

import asyncio

import pytest

from app import main
from app.config import Settings


@pytest.mark.parametrize(
    "given",
    [
        "postgres://u:p@h:5432/db",
        "postgresql://u:p@h:5432/db",
        "postgresql+asyncpg://u:p@h:5432/db",
    ],
)
def test_database_url_always_uses_asyncpg(given):
    assert Settings(database_url=given).database_url == "postgresql+asyncpg://u:p@h:5432/db"


def test_railway_provides_address_and_volume(monkeypatch):
    monkeypatch.delenv("API_BASE_URL", raising=False)
    monkeypatch.delenv("LOCAL_MEDIA_DIR", raising=False)
    monkeypatch.setenv("RAILWAY_PUBLIC_DOMAIN", "cadence.up.railway.app")
    monkeypatch.setenv("RAILWAY_VOLUME_MOUNT_PATH", "/data")
    s = Settings(_env_file=None)
    assert (s.api_base_url, s.local_media_dir) == ("https://cadence.up.railway.app", "/data/media")


def test_explicit_settings_win_over_railway(monkeypatch):
    monkeypatch.setenv("RAILWAY_PUBLIC_DOMAIN", "cadence.up.railway.app")
    monkeypatch.setenv("API_BASE_URL", "https://api.mondomaine.com")
    assert Settings(_env_file=None).api_base_url == "https://api.mondomaine.com"


async def test_embedded_worker_runs_with_the_api_and_stops_with_it(monkeypatch):
    ticks = 0

    async def fake_run_once(session_factory):
        nonlocal ticks
        ticks += 1
        return 0

    class Embedded:
        embed_worker = True
        worker_poll_seconds = 0.01

    monkeypatch.setattr("app.worker.run_once", fake_run_once)
    monkeypatch.setattr("app.worker.get_settings", lambda: Embedded)
    monkeypatch.setattr(main, "get_settings", lambda: Embedded)

    class NoMcp:
        def run(self):
            return self

        async def __aenter__(self):
            return None

        async def __aexit__(self, *exc):
            return False

    monkeypatch.setattr(main.mcp, "_session_manager", NoMcp(), raising=False)
    monkeypatch.setattr(type(main.mcp), "session_manager", property(lambda self: NoMcp()))

    async with main.lifespan(main.app):
        await asyncio.sleep(0.1)
        assert ticks >= 2
    stopped_at = ticks
    await asyncio.sleep(0.05)
    assert ticks == stopped_at

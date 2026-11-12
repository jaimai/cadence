import asyncio
import os
import tempfile

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://cadence:cadence@localhost:5432/cadence_test"
)
os.environ["STORAGE_BACKEND"] = "local"
# Tests must not depend on the developer's .env: pin everything it could change.
os.environ.update(
    COOKIE_SECURE="false",
    COOKIE_SAMESITE="lax",
    COOKIE_DOMAIN="",
    ENCRYPTION_KEY="",
    API_BASE_URL="http://localhost:8000",
    WEB_BASE_URL="http://localhost:5173",
    ALLOW_SIGNUP="true",
    INSTAGRAM_APP_ID="",
    INSTAGRAM_APP_SECRET="",
    TIKTOK_CLIENT_KEY="",
    TIKTOK_CLIENT_SECRET="",
    TIKTOK_PRIVACY_LEVEL="SELF_ONLY",
)
os.environ["LOCAL_MEDIA_DIR"] = tempfile.mkdtemp(prefix="cadence-media-")
os.environ["SECRET_KEY"] = "test-secret-key-that-is-long-enough-for-hs256"
os.environ["META_APP_ID"] = "app-id"
os.environ["META_APP_SECRET"] = "app-secret"

import httpx  # noqa: E402
import pytest  # noqa: E402

from app.connectors import set_connector  # noqa: E402
from app.connectors.base import (  # noqa: E402
    AccountAuth,
    ConnectedAccount,
    PublishContent,
    PublishResult,
)
from app.connectors.facebook import FacebookConnector  # noqa: E402
from app.db import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base  # noqa: E402
from app.services.accounts import upsert_accounts  # noqa: E402


class FakeFacebook(FacebookConnector):
    """Real validation rules, no network."""

    def __init__(self) -> None:
        super().__init__()
        self.published: list[tuple[AccountAuth, PublishContent]] = []
        self.error: Exception | None = None

    async def publish(self, auth: AccountAuth, content: PublishContent) -> PublishResult:
        if self.error:
            raise self.error
        self.published.append((auth, content))
        return PublishResult("fb_1", "https://facebook.com/fb_1")


@pytest.fixture(scope="session", autouse=True)
async def schema():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    # The MCP session manager must enter and exit its task group in the same task.
    started, stop = asyncio.Event(), asyncio.Event()

    async def run_lifespan():
        async with app.router.lifespan_context(app):
            started.set()
            await stop.wait()

    task = asyncio.create_task(run_lifespan())
    await started.wait()
    yield
    stop.set()
    await task
    await engine.dispose()


@pytest.fixture(autouse=True)
async def clean():
    yield
    async with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(table.delete())


@pytest.fixture
def fake_fb():
    fake = FakeFacebook()
    set_connector("facebook", fake)
    yield fake
    set_connector("facebook", FacebookConnector())


def make_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


@pytest.fixture
async def client():
    async with make_client() as c:
        r = await c.post(
            "/api/auth/signup", json={"email": "a@example.com", "password": "password123"}
        )
        assert r.status_code == 200, r.text
        yield c


@pytest.fixture
async def workspace_id(client):
    return (await client.get("/api/auth/me")).json()["workspace"]["id"]


@pytest.fixture
async def account_id(client, workspace_id):
    async with SessionLocal() as session:
        await upsert_accounts(
            session,
            workspace_id,
            "facebook",
            [
                ConnectedAccount(
                    external_id="page_1", display_name="Ma Page", access_token="page-token"
                )
            ],
        )
    return (await client.get("/api/accounts")).json()[0]["id"]


async def upload(client: httpx.AsyncClient, name="a.jpg", content_type="image/jpeg") -> str:
    data = b"binary-content"
    r = await client.post(
        "/api/media/presign",
        json={"filename": name, "content_type": content_type, "size": len(data)},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert (await client.put(body["upload_url"], content=data)).status_code == 204
    r = await client.post(f"/api/media/{body['media']['id']}/complete")
    assert r.json()["status"] == "ready"
    return body["media"]["id"]

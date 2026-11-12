"""Token renewal by the worker, with a connector whose tokens expire."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.connectors import get_connector, set_connector
from app.connectors.base import (
    AccountAuth,
    ConnectedAccount,
    ConnectorError,
    PublishContent,
    PublishResult,
    TokenSet,
)
from app.connectors.tiktok import TikTokConnector
from app.db import SessionLocal
from app.models import SocialAccount
from app.security import decrypt
from app.services.accounts import upsert_accounts
from app.services.publisher import run_once
from tests.conftest import upload


class FakeTikTok(TikTokConnector):
    def __init__(self) -> None:
        super().__init__()
        self.refreshed: list[tuple[str, str | None]] = []
        self.used_tokens: list[str] = []
        self.refresh_error: Exception | None = None

    async def refresh(self, access_token, refresh_token):
        if self.refresh_error:
            raise self.refresh_error
        self.refreshed.append((access_token, refresh_token))
        n = len(self.refreshed) + 1
        return TokenSet(f"a{n}", f"r{n}", datetime.now(UTC) + timedelta(hours=2))

    async def publish(self, auth: AccountAuth, content: PublishContent) -> PublishResult:
        self.used_tokens.append(auth.access_token)
        return PublishResult("777", None)


@pytest.fixture
def fake_tt():
    original = get_connector("tiktok")
    fake = FakeTikTok()
    set_connector("tiktok", fake)
    yield fake
    set_connector("tiktok", original)


async def connect(workspace_id, expires_in: timedelta) -> None:
    async with SessionLocal() as session:
        await upsert_accounts(
            session,
            workspace_id,
            "tiktok",
            [
                ConnectedAccount(
                    external_id="open_1",
                    display_name="Mon App",
                    access_token="a1",
                    refresh_token="r1",
                    token_expires_at=datetime.now(UTC) + expires_in,
                )
            ],
        )


async def stored() -> SocialAccount:
    async with SessionLocal() as session:
        return (await session.execute(select(SocialAccount))).scalar_one()


async def test_idle_account_is_kept_alive(client, workspace_id, fake_tt):
    await connect(workspace_id, timedelta(minutes=20))  # inside the 30 min margin
    await run_once(SessionLocal)
    account = await stored()
    assert fake_tt.refreshed == [("a1", "r1")]
    # The rotated refresh token is saved, otherwise the next renewal would fail.
    assert (decrypt(account.access_token_enc), decrypt(account.refresh_token_enc)) == ("a2", "r2")
    await run_once(SessionLocal)
    assert len(fake_tt.refreshed) == 1  # fresh token is left alone


async def test_fresh_token_is_not_renewed(client, workspace_id, fake_tt):
    await connect(workspace_id, timedelta(hours=2))
    await run_once(SessionLocal)
    assert fake_tt.refreshed == []


async def test_expired_token_is_renewed_before_publishing(client, workspace_id, fake_tt):
    await connect(workspace_id, timedelta(minutes=-5))
    account_id = (await client.get("/api/accounts")).json()[0]["id"]
    video = await upload(client, "v.mp4", "video/mp4")
    post = (
        await client.post(
            "/api/posts",
            json={
                "caption": "x",
                "account_ids": [account_id],
                "media_ids": [video],
                "publish_now": True,
            },
        )
    ).json()
    await run_once(SessionLocal)
    assert fake_tt.used_tokens == ["a2"]
    assert (await client.get(f"/api/posts/{post['id']}")).json()["status"] == "published"


async def test_dead_refresh_token_flags_the_account(client, workspace_id, fake_tt):
    await connect(workspace_id, timedelta(minutes=-5))
    fake_tt.refresh_error = ConnectorError("expired", reauth=True)
    account_id = (await client.get("/api/accounts")).json()[0]["id"]
    video = await upload(client, "v.mp4", "video/mp4")
    post = (
        await client.post(
            "/api/posts",
            json={
                "caption": "x",
                "account_ids": [account_id],
                "media_ids": [video],
                "publish_now": True,
            },
        )
    ).json()
    await run_once(SessionLocal)
    assert fake_tt.used_tokens == []
    assert (await client.get("/api/accounts")).json()[0]["status"] == "needs_reauth"
    assert (await client.get(f"/api/posts/{post['id']}")).json()["status"] == "failed"
    # A post cannot be scheduled on an account that needs reconnecting.
    r = await client.post(
        "/api/posts",
        json={
            "caption": "x",
            "account_ids": [account_id],
            "media_ids": [video],
            "publish_now": True,
        },
    )
    assert r.status_code == 400 and "reconnecté" in r.json()["detail"]


async def test_platform_rules_are_enforced_when_scheduling(client, workspace_id, fake_tt):
    await connect(workspace_id, timedelta(hours=2))
    account_id = (await client.get("/api/accounts")).json()[0]["id"]
    r = await client.post(
        "/api/posts",
        json={"caption": "texte seul", "account_ids": [account_id], "publish_now": True},
    )
    assert r.status_code == 400 and "TikTok" in r.json()["detail"]

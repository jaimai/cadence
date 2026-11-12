from datetime import UTC, datetime, timedelta

from app.connectors.base import ConnectorError
from app.db import SessionLocal
from app.services.publisher import run_once
from tests.conftest import make_client, upload


async def test_auth_flow(client):
    assert (await client.get("/api/auth/me")).json()["email"] == "a@example.com"
    async with make_client() as anon:
        assert (await anon.get("/api/posts")).status_code == 401
        bad = await anon.post(
            "/api/auth/login", json={"email": "a@example.com", "password": "wrong-pass"}
        )
        assert bad.status_code == 401
        ok = await anon.post(
            "/api/auth/login", json={"email": "a@example.com", "password": "password123"}
        )
        assert ok.status_code == 200
        assert (await anon.get("/api/posts")).status_code == 200
    dup = await client.post(
        "/api/auth/signup", json={"email": "A@example.com", "password": "password123"}
    )
    assert dup.status_code == 409


async def test_tokens_are_encrypted_at_rest(client, account_id):
    from sqlalchemy import text

    async with SessionLocal() as session:
        stored = (
            await session.execute(text("select access_token_enc from social_accounts"))
        ).scalar()
    assert "page-token" not in stored
    assert "access_token" not in (await client.get("/api/accounts")).text


async def test_publish_now_end_to_end(client, account_id, fake_fb):
    media_id = await upload(client)
    r = await client.post(
        "/api/posts",
        json={
            "caption": "Bonjour",
            "account_ids": [account_id],
            "media_ids": [media_id],
            "publish_now": True,
        },
    )
    assert r.status_code == 201, r.text
    post = r.json()
    assert post["status"] == "scheduled"

    assert await run_once(SessionLocal) == 1
    auth, content = fake_fb.published[0]
    assert (auth.external_id, auth.access_token) == ("page_1", "page-token")
    assert content.caption == "Bonjour"
    assert content.media[0].kind == "image" and content.media[0].url.endswith(".jpg")

    post = (await client.get(f"/api/posts/{post['id']}")).json()
    assert post["status"] == "published"
    assert post["targets"][0]["permalink"] == "https://facebook.com/fb_1"
    assert await run_once(SessionLocal) == 0  # never published twice


async def test_future_post_waits_and_can_be_unscheduled(client, account_id, fake_fb):
    when = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    post = (
        await client.post(
            "/api/posts",
            json={
                "caption": "Demain",
                "account_ids": [account_id],
                "scheduled_at": when,
            },
        )
    ).json()
    assert post["status"] == "scheduled"
    assert await run_once(SessionLocal) == 0
    r = await client.post(f"/api/posts/{post['id']}/unschedule")
    assert r.json()["status"] == "draft"


async def test_caption_override_per_account(client, account_id, fake_fb):
    await client.post(
        "/api/posts",
        json={
            "caption": "Générique",
            "account_ids": [account_id],
            "publish_now": True,
            "caption_overrides": {account_id: "Spécial Facebook"},
        },
    )
    await run_once(SessionLocal)
    assert fake_fb.published[0][1].caption == "Spécial Facebook"


async def test_retryable_error_is_retried_then_fails(client, account_id, fake_fb):
    fake_fb.error = ConnectorError("Limite atteinte", retryable=True)
    post = (
        await client.post(
            "/api/posts",
            json={
                "caption": "x",
                "account_ids": [account_id],
                "publish_now": True,
            },
        )
    ).json()
    await run_once(SessionLocal)
    target = (await client.get(f"/api/posts/{post['id']}")).json()["targets"][0]
    assert target["status"] == "pending" and target["attempts"] == 1
    assert await run_once(SessionLocal) == 0  # backoff not elapsed

    fake_fb.error = ConnectorError("Jeton expiré", reauth=True)
    from sqlalchemy import text

    async with SessionLocal() as session:
        await session.execute(text("update post_targets set next_attempt_at = now()"))
        await session.commit()
    await run_once(SessionLocal)
    post = (await client.get(f"/api/posts/{post['id']}")).json()
    assert post["status"] == "failed"
    assert post["targets"][0]["error"] == "Jeton expiré"
    assert (await client.get("/api/accounts")).json()[0]["status"] == "needs_reauth"

    # Retry is refused while the account needs reconnecting... after fixing, it works.
    fake_fb.error = None
    r = await client.post(f"/api/posts/{post['id']}/retry")
    assert r.json()["status"] == "scheduled"
    await run_once(SessionLocal)
    assert (await client.get(f"/api/posts/{post['id']}")).json()["status"] == "published"


async def test_validation(client, account_id, fake_fb):
    r = await client.post("/api/posts", json={"caption": "x", "publish_now": True})
    assert r.status_code == 400 and "compte" in r.json()["detail"]

    img, vid = await upload(client), await upload(client, "v.mp4", "video/mp4")
    r = await client.post(
        "/api/posts",
        json={
            "caption": "x",
            "account_ids": [account_id],
            "media_ids": [img, vid],
            "publish_now": True,
        },
    )
    assert r.status_code == 400 and "mélanger" in r.json()["detail"]
    assert (await client.get("/api/posts")).json() == []  # nothing half-created

    r = await client.post(
        "/api/media/presign",
        json={"filename": "a.exe", "content_type": "application/x-msdownload", "size": 10},
    )
    assert r.status_code == 400

    draft = await client.post("/api/posts", json={"caption": "idée"})
    assert draft.status_code == 201 and draft.json()["status"] == "draft"


async def test_edit_rules(client, account_id, fake_fb):
    post = (
        await client.post("/api/posts", json={"caption": "v1", "account_ids": [account_id]})
    ).json()
    r = await client.patch(f"/api/posts/{post['id']}", json={"caption": "v2"})
    assert r.json()["caption"] == "v2" and len(r.json()["targets"]) == 1
    await client.post(f"/api/posts/{post['id']}/schedule", json={})
    await run_once(SessionLocal)
    r = await client.patch(f"/api/posts/{post['id']}", json={"caption": "v3"})
    assert r.status_code == 409


async def test_media_in_use_cannot_be_deleted(client, account_id):
    media_id = await upload(client)
    await client.post("/api/posts", json={"caption": "x", "media_ids": [media_id]})
    assert (await client.delete(f"/api/media/{media_id}")).status_code == 409
    other = await upload(client)
    assert (await client.delete(f"/api/media/{other}")).status_code == 204
    assert len((await client.get("/api/media")).json()) == 1


async def test_workspaces_are_isolated(client, account_id):
    media_id = await upload(client)
    post = (
        await client.post("/api/posts", json={"caption": "privé", "account_ids": [account_id]})
    ).json()
    async with make_client() as other:
        await other.post(
            "/api/auth/signup", json={"email": "b@example.com", "password": "password123"}
        )
        assert (await other.get("/api/posts")).json() == []
        assert (await other.get("/api/accounts")).json() == []
        assert (await other.get(f"/api/posts/{post['id']}")).status_code == 404
        assert (await other.delete(f"/api/accounts/{account_id}")).status_code == 404
        r = await other.post("/api/posts", json={"caption": "vol", "account_ids": [account_id]})
        assert r.status_code == 400
        r = await other.post("/api/posts", json={"caption": "vol", "media_ids": [media_id]})
        assert r.status_code == 400


async def test_oauth_start_and_callback(client, workspace_id, monkeypatch):
    from urllib.parse import parse_qs, urlparse

    from app.connectors import get_connector
    from app.connectors.base import ConnectedAccount

    url = (await client.get("/api/oauth/facebook/start")).json()["url"]
    query = parse_qs(urlparse(url).query)
    assert query["client_id"] == ["app-id"]
    assert query["redirect_uri"] == ["http://localhost:8000/api/oauth/facebook/callback"]

    async def fake_exchange(code, redirect_uri):
        assert code == "the-code"
        return [ConnectedAccount("p1", "Page 1", "t1"), ConnectedAccount("p2", "Page 2", "t2")]

    monkeypatch.setattr(get_connector("facebook"), "exchange_code", fake_exchange)
    state = query["state"][0]
    r = await client.get(f"/api/oauth/facebook/callback?code=the-code&state={state}")
    assert r.status_code == 307 and "connected=2" in r.headers["location"]
    assert len((await client.get("/api/accounts")).json()) == 2
    # Reconnecting updates instead of duplicating.
    await client.get(f"/api/oauth/facebook/callback?code=the-code&state={state}")
    assert len((await client.get("/api/accounts")).json()) == 2

    r = await client.get("/api/oauth/facebook/callback?code=x&state=forged")
    assert "error=" in r.headers["location"]
    assert (await client.get("/api/oauth/linkedin/start")).status_code == 404
    # Connector exists but its app keys are not configured.
    assert (await client.get("/api/oauth/tiktok/start")).status_code == 400


async def test_qr_link_connects_from_a_device_without_session(client, workspace_id, monkeypatch):
    from urllib.parse import parse_qs, urlparse

    from sqlalchemy import text

    from app.connectors import get_connector
    from app.connectors.base import ConnectedAccount

    link = (await client.post("/api/oauth/facebook/link")).json()
    assert link["reachable"] is False  # API runs on localhost in tests
    path = urlparse(link["url"]).path

    async def fake_exchange(code, redirect_uri):
        return [ConnectedAccount("p1", "Page <1>", "t1")]

    monkeypatch.setattr(get_connector("facebook"), "exchange_code", fake_exchange)

    async with make_client() as phone:  # no cookie
        r = await phone.get(path)
        assert r.status_code == 307 and "facebook.com" in r.headers["location"]
        state = parse_qs(urlparse(r.headers["location"]).query)["state"][0]
        done = await phone.get(f"/api/oauth/facebook/callback?code=c&state={state}")
        # The phone gets a result page, not a redirect into an app it is not signed in to.
        assert done.status_code == 200 and "Page &lt;1&gt; connecté" in done.text
        # The same QR code can be scanned again to add another account.
        assert (await phone.get(path)).status_code == 307
        refused = await phone.get(f"/api/oauth/facebook/callback?error=access_denied&state={state}")
        assert "Connexion annulée" in refused.text

        assert (await phone.get("/api/oauth/go/unknown")).status_code == 410
        async with SessionLocal() as session:
            await session.execute(
                text("update oauth_links set expires_at = now() - interval '1 minute'")
            )
            await session.commit()
        assert (await phone.get(path)).status_code == 410
        assert (await phone.post("/api/oauth/facebook/link")).status_code == 401

    assert [a["display_name"] for a in (await client.get("/api/accounts")).json()] == ["Page <1>"]

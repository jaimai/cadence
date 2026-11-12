from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from app.connectors.base import AccountAuth, ConnectorError, MediaItem, PublishContent
from app.connectors.instagram import InstagramConnector

AUTH = AccountAuth("ig_1", "ig-token")
JPG = MediaItem("https://cdn.test/a.jpg", "image", "image/jpeg")
PNG = MediaItem("https://cdn.test/a.png", "image", "image/png")
VID = MediaItem("https://cdn.test/v.mp4", "video", "video/mp4")


def form(request: httpx.Request) -> dict[str, str]:
    return {k: v[0] for k, v in parse_qs(request.content.decode()).items()}


def connector(handler):
    calls: list[httpx.Request] = []

    def wrapped(request):
        calls.append(request)
        return handler(request)

    ig = InstagramConnector(httpx.AsyncClient(transport=httpx.MockTransport(wrapped)))
    ig.poll_interval = 0
    return ig, calls


def api(statuses: list[str] | None = None):
    """Fake Graph API. `statuses` is what successive container polls return."""
    statuses = list(statuses or [])
    counter = iter(range(1, 100))

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if request.method == "POST" and path.endswith("/media"):
            return httpx.Response(200, json={"id": f"c{next(counter)}"})
        if request.method == "POST" and path.endswith("/media_publish"):
            return httpx.Response(200, json={"id": "media_9"})
        if "status_code" in request.url.params.get("fields", ""):
            return httpx.Response(
                200, json={"status_code": statuses.pop(0) if statuses else "FINISHED"}
            )
        return httpx.Response(200, json={"permalink": "https://www.instagram.com/p/abc/"})

    return handler


async def test_single_image():
    ig, calls = connector(api())
    result = await ig.publish(AUTH, PublishContent("Légende", [JPG]))
    posts = [c for c in calls if c.method == "POST"]
    assert posts[0].url.host == "graph.instagram.com" and posts[0].url.path.endswith("/ig_1/media")
    assert form(posts[0]) == {
        "access_token": "ig-token",
        "image_url": JPG.url,
        "caption": "Légende",
    }
    assert form(posts[1])["creation_id"] == "c1"
    assert (result.external_post_id, result.permalink) == (
        "media_9",
        "https://www.instagram.com/p/abc/",
    )


async def test_video_is_a_reel_and_waits_for_processing():
    ig, calls = connector(api(["IN_PROGRESS", "IN_PROGRESS", "FINISHED"]))
    await ig.publish(AUTH, PublishContent("Reel", [VID]))
    assert form(calls[0])["media_type"] == "REELS" and form(calls[0])["video_url"] == VID.url
    kinds = [c.method + ":" + c.url.path.rsplit("/", 1)[1] for c in calls]
    # Three status polls happen before media_publish.
    assert kinds[:5] == ["POST:media", "GET:c1", "GET:c1", "GET:c1", "POST:media_publish"]


async def test_carousel():
    ig, calls = connector(api())
    await ig.publish(AUTH, PublishContent("Album", [JPG, VID, JPG]))
    containers = [form(c) for c in calls if c.method == "POST" and c.url.path.endswith("/media")]
    assert [c.get("is_carousel_item") for c in containers] == ["true", "true", "true", None]
    assert containers[1]["media_type"] == "VIDEO" and "caption" not in containers[0]
    assert containers[3] == {
        "access_token": "ig-token",
        "media_type": "CAROUSEL",
        "children": "c1,c2,c3",
        "caption": "Album",
    }


async def test_processing_error_and_timeout():
    ig, _ = connector(api(["ERROR"]))
    with pytest.raises(ConnectorError) as e:
        await ig.publish(AUTH, PublishContent("x", [VID]))
    assert not e.value.retryable

    ig, calls = connector(api(["IN_PROGRESS"] * 50))
    ig.poll_timeout = 0
    with pytest.raises(ConnectorError) as e:
        await ig.publish(AUTH, PublishContent("x", [VID]))
    assert e.value.retryable  # nothing was published, safe to try again
    assert not any(c.url.path.endswith("/media_publish") for c in calls)


async def test_expired_token_asks_for_reconnection():
    ig, _ = connector(
        lambda r: httpx.Response(400, json={"error": {"code": 190, "message": "expired"}})
    )
    with pytest.raises(ConnectorError) as e:
        await ig.publish(AUTH, PublishContent("x", [JPG]))
    assert e.value.reauth


async def test_connect_and_refresh(monkeypatch):
    monkeypatch.setenv("INSTAGRAM_APP_ID", "ig-app")
    monkeypatch.setenv("INSTAGRAM_APP_SECRET", "ig-secret")
    from app.config import get_settings

    get_settings.cache_clear()

    def handler(request):
        if request.url.host == "api.instagram.com":
            body = form(request)
            assert body["code"] == "the-code" and body["client_secret"] == "ig-secret"
            return httpx.Response(200, json={"data": [{"access_token": "short", "user_id": "1"}]})
        q = request.url.params
        if request.url.path == "/access_token":
            assert q["grant_type"] == "ig_exchange_token" and q["access_token"] == "short"
            return httpx.Response(200, json={"access_token": "long", "expires_in": 5183944})
        if request.url.path == "/refresh_access_token":
            assert q["access_token"] == "long"
            return httpx.Response(200, json={"access_token": "long2", "expires_in": 5183944})
        assert q["access_token"] == "long"
        return httpx.Response(
            200, json={"user_id": "ig_1", "username": "monapp", "name": "Mon App"}
        )

    try:
        ig, _ = connector(handler)
        url = urlparse(ig.authorize_url("st", "https://api/cb"))
        query = parse_qs(url.query)
        assert url.netloc == "www.instagram.com" and query["client_id"] == ["ig-app"]
        assert query["scope"] == ["instagram_business_basic,instagram_business_content_publish"]

        [account] = await ig.exchange_code("the-code#_", "https://api/cb")
        assert (account.external_id, account.username, account.access_token) == (
            "ig_1",
            "monapp",
            "long",
        )
        assert (
            59
            <= (
                account.token_expires_at
                - __import__("datetime").datetime.now(account.token_expires_at.tzinfo)
            ).days
            <= 60
        )

        tokens = await ig.refresh("long", None)
        assert tokens.access_token == "long2" and tokens.token_expires_at is not None
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()


def test_validate():
    ig = InstagramConnector()
    assert ig.validate(PublishContent("x", [JPG])) == []
    assert ig.validate(PublishContent("", [VID])) == []
    assert ig.validate(PublishContent("texte seul"))
    assert ig.validate(PublishContent("x", [PNG]))
    assert ig.validate(PublishContent("x", [JPG] * 11))
    assert ig.validate(PublishContent("x" * 2201, [JPG]))
